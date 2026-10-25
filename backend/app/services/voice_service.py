from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models import VoiceUpload
from backend.app.services.audio_validator import AudioValidationResult

logger = logging.getLogger(__name__)

# Resilient in-memory fallback cache for development or when DB is disconnected
_in_memory_uploads: Dict[str, Dict[str, Any]] = {}


class VoiceService:
    @staticmethod
    async def record_upload(
        validation: AudioValidationResult,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Record the validated audio upload into the database.
        Falls back to in-memory store if DB is disconnected.
        Strictly sanitizes and returns non-sensitive metadata for API responses.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.VOICE_RETENTION_HOURS)

        upload_data = {
            "token": validation.token,
            "filename": validation.filename,
            "file_path": validation.file_path,
            "file_size_bytes": validation.file_size_bytes,
            "mime_type": validation.mime_type,
            "format": validation.detected_format,
            "duration_seconds": validation.duration_seconds,
            "status": "received",
            "transcript": None,
            "english_translation": None,
            "language": None,
            "language_name": None,
            "language_probability": None,
            "error_message": None,
            "created_at": now,
            "expires_at": expires_at,
        }

        # Cache in memory for quick retrieval
        _in_memory_uploads[validation.token] = upload_data

        # Persist to database if session is provided and active
        if db is not None:
            try:
                record = VoiceUpload(
                    token=validation.token,
                    filename=validation.filename,
                    file_path=validation.file_path,
                    file_size_bytes=validation.file_size_bytes,
                    mime_type=validation.mime_type,
                    format=validation.detected_format,
                    duration_seconds=validation.duration_seconds,
                    status="received",
                    transcript=None,
                    english_translation=None,
                    language=None,
                    language_name=None,
                    language_probability=None,
                    created_at=now,
                    expires_at=expires_at,
                )
                db.add(record)
                await db.commit()
                await db.refresh(record)
            except Exception as e:
                logger.warning(f"Database persist failed for upload {validation.token}: {e}. Retained in memory cache.")
                try:
                    await db.rollback()
                except Exception:
                    pass

        return {
            "token": validation.token,
            "status": "received",
            "format": validation.detected_format,
            "size_bytes": validation.file_size_bytes,
            "duration_seconds": validation.duration_seconds,
            "message": "Voice note uploaded and validated successfully.",
        }

    @staticmethod
    async def get_status(
        token: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve upload status by token.
        Never exposes internal file paths or sensitive system fields.
        """
        # Check memory cache if present and actively updated
        cached = _in_memory_uploads.get(token)
        if cached and cached.get("status") in ("processing", "transcribing", "completed", "failed"):
            created_at = cached["created_at"]
            return {
                "token": cached["token"],
                "status": cached["status"],
                "format": cached["format"],
                "size_bytes": cached["file_size_bytes"],
                "duration_seconds": cached["duration_seconds"],
                "transcript": cached.get("transcript"),
                "english_translation": cached.get("english_translation"),
                "language": cached.get("language"),
                "language_name": cached.get("language_name"),
                "language_probability": cached.get("language_probability"),
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                "error_message": cached.get("error_message"),
            }

        # Check database if available
        if db is not None:
            try:
                stmt = select(VoiceUpload).where(VoiceUpload.token == token)
                result = await db.execute(stmt)
                record = result.scalar_one_or_none()
                if record:
                    return {
                        "token": record.token,
                        "status": record.status,
                        "format": record.format,
                        "size_bytes": record.file_size_bytes,
                        "duration_seconds": record.duration_seconds,
                        "transcript": record.transcript,
                        "english_translation": record.english_translation,
                        "language": record.language,
                        "language_name": record.language_name,
                        "language_probability": record.language_probability,
                        "created_at": record.created_at.isoformat() if record.created_at else None,
                        "error_message": record.error_message,
                    }
            except Exception as e:
                logger.debug(f"DB lookup failed for token {token}: {e}. Checking memory fallback.")

        # Fallback to memory cache
        if cached:
            created_at = cached["created_at"]
            return {
                "token": cached["token"],
                "status": cached["status"],
                "format": cached["format"],
                "size_bytes": cached["file_size_bytes"],
                "duration_seconds": cached["duration_seconds"],
                "transcript": cached.get("transcript"),
                "english_translation": cached.get("english_translation"),
                "language": cached.get("language"),
                "language_name": cached.get("language_name"),
                "language_probability": cached.get("language_probability"),
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                "error_message": cached.get("error_message"),
            }

        return None

    @staticmethod
    async def update_translation(
        token: str,
        english_translation: str,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """
        Record the English translation without modifying the original transcript.
        """
        if token in _in_memory_uploads:
            _in_memory_uploads[token]["english_translation"] = english_translation

        if db is not None:
            try:
                stmt = select(VoiceUpload).where(VoiceUpload.token == token)
                result = await db.execute(stmt)
                record = result.scalar_one_or_none()
                if record:
                    record.english_translation = english_translation
                    await db.commit()
                    return True
            except Exception as e:
                logger.warning(f"Failed to save translation to DB for {token}: {e}")
                try:
                    await db.rollback()
                except Exception:
                    pass

        return token in _in_memory_uploads

    @staticmethod
    async def update_status(
        token: str,
        status_value: str,
        error_message: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """
        Update the processing status of a voice upload.
        """
        if token in _in_memory_uploads:
            _in_memory_uploads[token]["status"] = status_value
            _in_memory_uploads[token]["error_message"] = error_message

        if db is not None:
            try:
                stmt = select(VoiceUpload).where(VoiceUpload.token == token)
                result = await db.execute(stmt)
                record = result.scalar_one_or_none()
                if record:
                    record.status = status_value
                    record.error_message = error_message
                    await db.commit()
                    return True
            except Exception as e:
                logger.warning(f"Failed to update status in DB for {token}: {e}")
                try:
                    await db.rollback()
                except Exception:
                    pass

        return token in _in_memory_uploads

    @staticmethod
    async def update_transcription(
        token: str,
        transcript: str,
        language: str,
        language_name: str,
        language_probability: float,
        status_value: str = "completed",
        error_message: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """
        Record the successful speech-to-text transcript and detected language.
        """
        if token in _in_memory_uploads:
            _in_memory_uploads[token]["status"] = status_value
            _in_memory_uploads[token]["transcript"] = transcript
            _in_memory_uploads[token]["language"] = language
            _in_memory_uploads[token]["language_name"] = language_name
            _in_memory_uploads[token]["language_probability"] = language_probability
            _in_memory_uploads[token]["error_message"] = error_message

        if db is not None:
            try:
                stmt = select(VoiceUpload).where(VoiceUpload.token == token)
                result = await db.execute(stmt)
                record = result.scalar_one_or_none()
                if record:
                    record.status = status_value
                    record.transcript = transcript
                    record.language = language
                    record.language_name = language_name
                    record.language_probability = language_probability
                    record.error_message = error_message
                    await db.commit()
                    return True
            except Exception as e:
                logger.warning(f"Failed to save transcript to DB for {token}: {e}")
                try:
                    await db.rollback()
                except Exception:
                    pass

        return token in _in_memory_uploads

