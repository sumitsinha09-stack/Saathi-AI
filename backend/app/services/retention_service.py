from datetime import datetime, timedelta, timezone
import logging
import os
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models import Complaint, ComplaintStatusHistory, VoiceUpload
from backend.app.services.complaint_service import (
    _in_memory_complaints,
    _in_memory_complaint_tokens,
    _in_memory_history,
)
from backend.app.services.voice_service import _in_memory_uploads

logger = logging.getLogger(__name__)


class RetentionService:
    """
    Automated retention enforcement and cleanup worker.
    - Cleans abandoned temporary audio files older than ABANDONED_AUDIO_CLEANUP_HOURS.
    - Cleans or redacts expired voice uploads/transcripts older than TRANSCRIPT_RETENTION_HOURS.
    - Purges abandoned/unconfirmed complaints older than UNCONFIRMED_COMPLAINT_RETENTION_HOURS.
    - Purges cancelled complaints older than CANCELLED_COMPLAINT_RETENTION_HOURS.
    - Retains confirmed complaints for CONFIRMED_COMPLAINT_RETENTION_DAYS without premature deletion.
    - Safe to run repeatedly (idempotent), never logs raw transcripts or personal data.
    """

    @classmethod
    def cleanup_abandoned_audio(cls, upload_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Scans temporary audio spool directory and deletes abandoned files older than ABANDONED_AUDIO_CLEANUP_HOURS.
        Does not touch files currently being written/processed (younger than threshold).
        """
        directory = upload_dir or settings.VOICE_UPLOAD_DIR
        now = time.time()
        max_age_seconds = settings.ABANDONED_AUDIO_CLEANUP_HOURS * 3600.0

        deleted_count = 0
        skipped_count = 0
        errors: List[str] = []

        if not os.path.exists(directory):
            return {"deleted": 0, "skipped": 0, "errors": []}

        for fname in os.listdir(directory):
            # Only target audio spool files
            if not any(fname.endswith(ext) for ext in [".wav", ".webm", ".ogg", ".mp3", ".m4a", ".tmp"]):
                continue

            file_path = os.path.join(directory, fname)
            try:
                stat = os.stat(file_path)
                age = now - stat.st_mtime
                if age > max_age_seconds:
                    os.remove(file_path)
                    deleted_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                err_msg = f"Failed to prune file {fname}: {type(e).__name__}"
                logger.warning(err_msg)
                errors.append(err_msg)

        logger.info(
            f"Abandoned audio cleanup complete: {deleted_count} deleted, {skipped_count} active/skipped, {len(errors)} errors"
        )
        return {"deleted": deleted_count, "skipped": skipped_count, "errors": errors}

    @staticmethod
    def _parse_timestamp(val: Any) -> Optional[datetime]:
        if val is None:
            return None
        if isinstance(val, str):
            try:
                dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        if isinstance(val, datetime):
            if val.tzinfo is None:
                return val.replace(tzinfo=timezone.utc)
            return val
        return None

    @classmethod
    async def cleanup_expired_voice_records(cls, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Applies transcript and voice metadata retention rules.
        Redacts or deletes voice uploads where age exceeds TRANSCRIPT_RETENTION_HOURS.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=settings.TRANSCRIPT_RETENTION_HOURS)
        purged_mem = 0
        purged_db = 0
        errors: List[str] = []

        # 1. In-memory uploads cleanup
        to_delete_keys = []
        for token, record in list(_in_memory_uploads.items()):
            created = cls._parse_timestamp(record.get("created_at"))
            if created and created < cutoff:
                to_delete_keys.append(token)

        for k in to_delete_keys:
            _in_memory_uploads.pop(k, None)
            purged_mem += 1

        # 2. Database records cleanup
        if db is not None:
            try:
                # Find confirmed complaint tokens to avoid deleting voice records linked to confirmed complaints if needed
                confirmed_tokens_stmt = select(Complaint.upload_token).where(
                    Complaint.status == "confirmed"
                )
                res = await db.execute(confirmed_tokens_stmt)
                confirmed_tokens = {r[0] for r in res.all() if r[0]}

                # Delete expired uploads not linked to confirmed complaints
                stmt = delete(VoiceUpload).where(
                    VoiceUpload.created_at < cutoff,
                    VoiceUpload.token.not_in(confirmed_tokens),
                )
                result = await db.execute(stmt)
                purged_db = result.rowcount or 0
                await db.commit()
            except Exception as e:
                err_msg = f"DB VoiceUpload cleanup error: {type(e).__name__}"
                logger.error(err_msg, exc_info=True)
                errors.append(err_msg)
                try:
                    await db.rollback()
                except Exception:
                    pass

        return {
            "purged_memory": purged_mem,
            "purged_db": purged_db,
            "total_purged": purged_mem + purged_db,
            "errors": errors,
        }

    @classmethod
    async def cleanup_expired_complaints(cls, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Applies complaint retention rules:
        - Unconfirmed / draft complaints older than UNCONFIRMED_COMPLAINT_RETENTION_HOURS are purged.
        - Cancelled complaints older than CANCELLED_COMPLAINT_RETENTION_HOURS are purged.
        - Confirmed complaints are preserved for CONFIRMED_COMPLAINT_RETENTION_DAYS.
        """
        now = datetime.now(timezone.utc)
        unconfirmed_cutoff = now - timedelta(hours=settings.UNCONFIRMED_COMPLAINT_RETENTION_HOURS)
        cancelled_cutoff = now - timedelta(hours=settings.CANCELLED_COMPLAINT_RETENTION_HOURS)
        confirmed_cutoff = now - timedelta(days=settings.CONFIRMED_COMPLAINT_RETENTION_DAYS)

        purged_unconfirmed = 0
        purged_cancelled = 0
        purged_expired_confirmed = 0
        preserved_confirmed = 0
        errors: List[str] = []

        # 1. In-memory complaints cleanup
        for ref, comp in list(_in_memory_complaints.items()):
            comp_status = (comp.get("status") or "").lower()
            created = cls._parse_timestamp(comp.get("created_at"))
            cancelled = cls._parse_timestamp(comp.get("cancelled_at"))
            confirmed = cls._parse_timestamp(comp.get("confirmed_at"))

            # Check unconfirmed
            if comp_status in ("awaiting_review", "processing", "draft") and created and created < unconfirmed_cutoff:
                _in_memory_complaints.pop(ref, None)
                _in_memory_history.pop(ref, None)
                token = comp.get("upload_token")
                if token:
                    _in_memory_complaint_tokens.pop(token, None)
                purged_unconfirmed += 1
            # Check cancelled
            elif comp_status == "cancelled" and cancelled and cancelled < cancelled_cutoff:
                _in_memory_complaints.pop(ref, None)
                _in_memory_history.pop(ref, None)
                token = comp.get("upload_token")
                if token:
                    _in_memory_complaint_tokens.pop(token, None)
                purged_cancelled += 1
            # Check confirmed
            elif comp_status == "confirmed":
                if confirmed and confirmed < confirmed_cutoff:
                    _in_memory_complaints.pop(ref, None)
                    _in_memory_history.pop(ref, None)
                    token = comp.get("upload_token")
                    if token:
                        _in_memory_complaint_tokens.pop(token, None)
                    purged_expired_confirmed += 1
                else:
                    preserved_confirmed += 1

        # 2. Database records cleanup
        if db is not None:
            try:
                # Purge unconfirmed
                stmt_unconf = delete(Complaint).where(
                    Complaint.status.in_(["awaiting_review", "processing", "draft"]),
                    Complaint.created_at < unconfirmed_cutoff,
                )
                r_unconf = await db.execute(stmt_unconf)
                purged_unconfirmed += (r_unconf.rowcount or 0)

                # Purge cancelled
                stmt_canc = delete(Complaint).where(
                    Complaint.status == "cancelled",
                    Complaint.cancelled_at < cancelled_cutoff,
                )
                r_canc = await db.execute(stmt_canc)
                purged_cancelled += (r_canc.rowcount or 0)

                # Count active confirmed preserved
                stmt_pres = select(Complaint).where(
                    Complaint.status == "confirmed",
                    Complaint.confirmed_at >= confirmed_cutoff,
                )
                r_pres = await db.execute(stmt_pres)
                preserved_confirmed += len(r_pres.scalars().all())

                # Purge confirmed exceeding 30-day retention
                stmt_conf = delete(Complaint).where(
                    Complaint.status == "confirmed",
                    Complaint.confirmed_at < confirmed_cutoff,
                )
                r_conf = await db.execute(stmt_conf)
                purged_expired_confirmed += (r_conf.rowcount or 0)

                await db.commit()
            except Exception as e:
                err_msg = f"DB Complaint cleanup error: {type(e).__name__}"
                logger.error(err_msg, exc_info=True)
                errors.append(err_msg)
                try:
                    await db.rollback()
                except Exception:
                    pass

        return {
            "purged_unconfirmed": purged_unconfirmed,
            "purged_cancelled": purged_cancelled,
            "purged_expired_confirmed": purged_expired_confirmed,
            "preserved_confirmed": preserved_confirmed,
            "errors": errors,
        }

    @classmethod
    async def run_full_retention_cycle(
        cls,
        upload_dir: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Executes a complete retention cycle across audio spool files, voice records, and complaints.
        Returns a sanitized audit dictionary of actions taken.
        """
        start_time = time.time()
        logger.info("Initiating automated Saathi AI data retention cycle...")

        audio_res = cls.cleanup_abandoned_audio(upload_dir=upload_dir)
        voice_res = await cls.cleanup_expired_voice_records(db=db)
        complaint_res = await cls.cleanup_expired_complaints(db=db)

        duration = round(time.time() - start_time, 3)
        summary = {
            "status": "completed",
            "duration_seconds": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "abandoned_audio": audio_res,
            "voice_records": voice_res,
            "complaints": complaint_res,
        }
        logger.info(
            f"Retention cycle complete in {duration}s: audio_deleted={audio_res['deleted']}, "
            f"voice_purged={voice_res['total_purged']}, unconfirmed_purged={complaint_res['purged_unconfirmed']}, "
            f"cancelled_purged={complaint_res['purged_cancelled']}, confirmed_preserved={complaint_res['preserved_confirmed']}"
        )
        return summary
