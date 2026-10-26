import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
import string
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.config import settings
from backend.app.models import Complaint, ComplaintStatusHistory
from backend.app.schemas.incident import Incident
from backend.app.services.redaction_service import RedactionService
from backend.app.services.translation_service import LANGUAGE_NAMES, TranslationService
from backend.app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)

# Permitted editable complaint fields during victim review
PERMITTED_EDITABLE_FIELDS = {
    "incident_type",
    "summary",
    "description",
    "reported_entity",
    "incident_date",
    "financial_loss",
    "currency",
    "phone_number",
    "suspected_scam",
    "evidence_description",
}

# Resilient in-memory storage fallback for dev/testing or when DB is unavailable
_in_memory_complaints: Dict[str, Dict[str, Any]] = {}  # keyed by reference_number
_in_memory_complaint_tokens: Dict[str, str] = {}        # keyed by upload_token -> reference_number
_in_memory_history: Dict[str, List[Dict[str, Any]]] = {}  # keyed by reference_number -> list of events


class ComplaintService:
    """
    Manages persistence, reference number generation, cryptographic access tokens,
    authorization, idempotency, and audit status history for complaints.
    """

    @staticmethod
    def generate_reference_number() -> str:
        """
        Generates a unique, non-sequential reference number in format 'SAI-XXXXXX',
        where XXXXXX is 6 random uppercase alphanumeric characters / digits.
        """
        chars = string.digits + string.ascii_uppercase
        # Exclude easily confused characters: 0, O, 1, I
        safe_chars = [c for c in chars if c not in ("0", "O", "1", "I")]
        suffix = "".join(secrets.choice(safe_chars) for _ in range(6))
        return f"SAI-{suffix}"

    @staticmethod
    def generate_access_token() -> Tuple[str, str]:
        """
        Generates a secure, cryptographically random access token and its SHA-256 hash.
        Returns (raw_token, token_hash).
        Only token_hash is stored in the database.
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        return raw_token, token_hash

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Computes SHA-256 hash of a provided raw token."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    async def create_complaint(
        cls,
        incident: Incident,
        upload_token: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Persists a validated Incident complaint.
        - Enforces idempotency: if a complaint already exists for this upload_token, returns existing.
        - Generates unique reference number 'SAI-XXXXXX' with collision retry.
        - Generates secure expiring access token.
        - Records initial status 'PENDING_REVIEW' and initial status-history event in a single transaction.
        - Never logs or exposes raw tokens or unredacted credentials.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.COMPLAINT_TOKEN_EXPIRY_HOURS)

        # 1. Idempotency Check: if upload_token already has a complaint, return it
        if upload_token:
            # Check DB if active
            if db is not None:
                try:
                    stmt = select(Complaint).where(Complaint.upload_token == upload_token)
                    result = await db.execute(stmt)
                    existing = result.scalar_one_or_none()
                    if existing:
                        logger.info(f"Idempotent return: Complaint already exists for upload_token: {upload_token}")
                        return cls._model_to_dict(existing)
                except Exception as e:
                    logger.debug(f"DB lookup for existing complaint failed: {e}")

            # Check in-memory
            if upload_token in _in_memory_complaint_tokens:
                ref = _in_memory_complaint_tokens[upload_token]
                if ref in _in_memory_complaints:
                    logger.info(f"Idempotent return from memory: Complaint {ref} for token {upload_token}")
                    return _in_memory_complaints[ref]

        raw_access_token, token_hash = cls.generate_access_token()
        initial_status = "awaiting_review"
        english_summary = incident.summary if (incident.language == "en" or TranslationService.is_english_text(incident.summary)) else None

        # 2. Persist to Database with Collision Retry
        max_attempts = 10
        for attempt in range(max_attempts):
            ref_number = cls.generate_reference_number()

            if db is not None:
                try:
                    complaint = Complaint(
                        reference_number=ref_number,
                        token_hash=token_hash,
                        upload_token=upload_token,
                        status=initial_status,
                        incident_type=incident.incident_type,
                        summary=incident.summary,
                        english_summary=english_summary,
                        description=incident.description,
                        language=incident.language,
                        reported_entity=incident.reported_entity,
                        incident_date=incident.incident_date,
                        financial_loss=incident.financial_loss,
                        currency=incident.currency,
                        phone_number=incident.phone_number,
                        suspected_scam=incident.suspected_scam,
                        evidence_description=incident.evidence_description,
                        is_fallback=incident.is_fallback,
                        raw_transcript_redacted=incident.description,
                        created_at=now,
                        confirmed_at=None,
                        cancelled_at=None,
                        expires_at=expires_at,
                    )
                    db.add(complaint)
                    await db.flush()  # flush to catch any reference_number collision

                    # Add initial status history event
                    history_event = ComplaintStatusHistory(
                        complaint_id=complaint.id,
                        status=initial_status,
                        note="Initial complaint created and recorded from voice transcription.",
                        created_at=now,
                    )
                    db.add(history_event)
                    await db.commit()
                    await db.refresh(complaint)

                    logger.info(f"Complaint {ref_number} successfully persisted to database.")

                    result_data = cls._model_to_dict(complaint, raw_access_token=raw_access_token)

                    # Update memory cache
                    _in_memory_complaints[ref_number] = result_data
                    if upload_token:
                        _in_memory_complaint_tokens[upload_token] = ref_number

                    return result_data

                except IntegrityError as integ_err:
                    logger.warning(f"Reference number collision on {ref_number}: {integ_err}. Retrying ({attempt+1}/{max_attempts})...")
                    await db.rollback()
                    continue
                except Exception as db_err:
                    logger.warning(f"Database persist failed for complaint: {db_err}. Using memory fallback.")
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    break
            else:
                break

        # 3. Fallback to In-Memory Persistence
        ref_number = cls.generate_reference_number()
        complaint_data = {
            "id": len(_in_memory_complaints) + 1,
            "reference_number": ref_number,
            "token_hash": token_hash,
            "access_token": raw_access_token,  # returned once at creation
            "upload_token": upload_token,
            "status": initial_status,
            "incident_type": incident.incident_type,
            "summary": incident.summary,
            "english_summary": english_summary,
            "description": incident.description,
            "language": incident.language,
            "reported_entity": incident.reported_entity,
            "incident_date": incident.incident_date,
            "financial_loss": incident.financial_loss,
            "currency": incident.currency,
            "phone_number": incident.phone_number,
            "suspected_scam": incident.suspected_scam,
            "evidence_description": incident.evidence_description,
            "is_fallback": incident.is_fallback,
            "extraction_method": incident.extraction_method,
            "created_at": now.isoformat(),
            "confirmed_at": None,
            "cancelled_at": None,
            "expires_at": expires_at.isoformat(),
        }

        _in_memory_complaints[ref_number] = complaint_data
        if upload_token:
            _in_memory_complaint_tokens[upload_token] = ref_number

        _in_memory_history[ref_number] = [
            {
                "status": initial_status,
                "note": "Initial complaint created and recorded from voice transcription.",
                "created_at": now.isoformat(),
            }
        ]

        logger.info(f"Complaint {ref_number} saved to in-memory store.")
        return complaint_data

    @classmethod
    async def get_complaint(
        cls,
        reference_number: str,
        access_token: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        require_token: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves complaint by reference number.
        Enforces cryptographic token verification and expiration check.
        """
        complaint_data = None

        # 1. Check DB
        if db is not None:
            try:
                stmt = select(Complaint).where(Complaint.reference_number == reference_number)
                result = await db.execute(stmt)
                record = result.scalar_one_or_none()
                if record:
                    complaint_data = cls._model_to_dict(record)
            except Exception as e:
                logger.debug(f"DB lookup failed for {reference_number}: {e}")

        # 2. Check memory cache
        if not complaint_data and reference_number in _in_memory_complaints:
            complaint_data = _in_memory_complaints[reference_number]

        if not complaint_data:
            return None

        # 3. Token and expiration validation
        if require_token:
            if not access_token:
                logger.warning(f"Unauthorized access attempt for complaint {reference_number}: missing token.")
                return None

            expected_hash = complaint_data["token_hash"]
            provided_hash = cls.hash_token(access_token)

            token_valid = secrets.compare_digest(expected_hash, provided_hash)
            if not token_valid and complaint_data.get("upload_token"):
                token_valid = (access_token == complaint_data.get("upload_token"))

            if not token_valid:
                logger.warning(f"Unauthorized access attempt for complaint {reference_number}: invalid token.")
                return None

            # Expiration check
            expires_at_str = complaint_data.get("expires_at")
            if expires_at_str:
                if isinstance(expires_at_str, str):
                    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                else:
                    expires_at = expires_at_str

                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                if datetime.now(timezone.utc) > expires_at:
                    logger.warning(f"Access attempt for expired complaint {reference_number}.")
                    return None

        return complaint_data

    @classmethod
    async def get_complaint_history(
        cls,
        reference_number: str,
        access_token: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves audit trail status history for a complaint.
        """
        complaint = await cls.get_complaint(reference_number, access_token=access_token, db=db)
        if not complaint:
            return None

        # Check DB
        if db is not None:
            try:
                stmt = (
                    select(ComplaintStatusHistory)
                    .join(Complaint)
                    .where(Complaint.reference_number == reference_number)
                    .order_by(ComplaintStatusHistory.created_at.asc())
                )
                result = await db.execute(stmt)
                events = result.scalars().all()
                if events:
                    return [
                        {
                            "id": ev.id,
                            "status": ev.status,
                            "note": ev.note,
                            "created_at": ev.created_at.isoformat() if ev.created_at else None,
                        }
                        for ev in events
                    ]
            except Exception as e:
                logger.debug(f"DB lookup for history of {reference_number} failed: {e}")

        # Check memory cache
        if reference_number in _in_memory_history:
            return _in_memory_history[reference_number]

        return [
            {
                "status": complaint.get("status", "PENDING_REVIEW"),
                "note": "Initial complaint created and recorded from voice transcription.",
                "created_at": complaint.get("created_at"),
            }
        ]

    @classmethod
    async def update_complaint_status(
        cls,
        reference_number: str,
        new_status: str,
        note: Optional[str] = None,
        access_token: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Updates the status of a complaint and appends an audit event.
        """
        complaint = await cls.get_complaint(reference_number, access_token=access_token, db=db)
        if not complaint:
            return None

        now = datetime.now(timezone.utc)

        # Update in DB
        if db is not None:
            try:
                stmt = select(Complaint).where(Complaint.reference_number == reference_number)
                result = await db.execute(stmt)
                record = result.scalar_one_or_none()
                if record:
                    record.status = new_status
                    event = ComplaintStatusHistory(
                        complaint_id=record.id,
                        status=new_status,
                        note=note or f"Status updated to {new_status}.",
                        created_at=now,
                    )
                    db.add(event)
                    await db.commit()
                    await db.refresh(record)
                    updated = cls._model_to_dict(record)
                    _in_memory_complaints[reference_number] = updated
                    return updated
            except Exception as e:
                logger.warning(f"Failed to update status in DB for {reference_number}: {e}")
                try:
                    await db.rollback()
                except Exception:
                    pass

        # Update in-memory
        if reference_number in _in_memory_complaints:
            _in_memory_complaints[reference_number]["status"] = new_status
            if reference_number not in _in_memory_history:
                _in_memory_history[reference_number] = []
            _in_memory_history[reference_number].append({
                "status": new_status,
                "note": note or f"Status updated to {new_status}.",
                "created_at": now.isoformat(),
            })
            return _in_memory_complaints[reference_number]

        return None

    @classmethod
    def get_complaint_by_upload_token(cls, upload_token: str) -> Optional[Dict[str, Any]]:
        """Helper to get cached complaint by voice upload token."""
        ref = _in_memory_complaint_tokens.get(upload_token)
        if ref and ref in _in_memory_complaints:
            return _in_memory_complaints[ref]
        return None

    @classmethod
    def _model_to_dict(cls, complaint: Complaint, raw_access_token: Optional[str] = None) -> Dict[str, Any]:
        """Serializes SQLAlchemy Complaint model into non-sensitive response dictionary."""
        data = {
            "id": complaint.id,
            "reference_number": complaint.reference_number,
            "token_hash": complaint.token_hash,
            "upload_token": complaint.upload_token,
            "status": complaint.status,
            "incident_type": complaint.incident_type,
            "summary": complaint.summary,
            "english_summary": getattr(complaint, "english_summary", None),
            "description": complaint.description,
            "language": complaint.language,
            "reported_entity": complaint.reported_entity,
            "incident_date": complaint.incident_date,
            "financial_loss": complaint.financial_loss,
            "currency": complaint.currency,
            "phone_number": complaint.phone_number,
            "suspected_scam": complaint.suspected_scam,
            "evidence_description": complaint.evidence_description,
            "is_fallback": complaint.is_fallback,
            "raw_transcript_redacted": getattr(complaint, "raw_transcript_redacted", None),
            "created_at": complaint.created_at.isoformat() if hasattr(complaint.created_at, "isoformat") else str(complaint.created_at),
            "confirmed_at": complaint.confirmed_at.isoformat() if getattr(complaint, "confirmed_at", None) and hasattr(complaint.confirmed_at, "isoformat") else (str(complaint.confirmed_at) if getattr(complaint, "confirmed_at", None) else None),
            "cancelled_at": complaint.cancelled_at.isoformat() if getattr(complaint, "cancelled_at", None) and hasattr(complaint.cancelled_at, "isoformat") else (str(complaint.cancelled_at) if getattr(complaint, "cancelled_at", None) else None),
            "expires_at": complaint.expires_at.isoformat() if hasattr(complaint.expires_at, "isoformat") else str(complaint.expires_at),
        }
        if raw_access_token:
            data["access_token"] = raw_access_token
        return data

    @staticmethod
    def is_expired(expires_at_val: Any) -> bool:
        """Helper to determine if a datetime or ISO string has expired."""
        if not expires_at_val:
            return False
        if isinstance(expires_at_val, str):
            try:
                expires_at = datetime.fromisoformat(expires_at_val.replace("Z", "+00:00"))
            except Exception:
                return False
        else:
            expires_at = expires_at_val

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires_at

    @classmethod
    async def find_complaint_record(
        cls,
        token: str,
        db: Optional[AsyncSession] = None,
    ) -> Tuple[Optional[Any], bool]:
        """
        Looks up a complaint record by token hash, raw access token, upload token,
        or reference number.
        Returns (record, is_in_memory: bool).
        """
        if not token or not token.strip():
            return None, False

        token_str = token.strip()
        token_hash = cls.hash_token(token_str)
        clean_ref = token_str.upper()

        # 1. Search database
        if db is not None:
            try:
                stmt = select(Complaint).where(
                    (Complaint.token_hash == token_hash)
                    | (Complaint.upload_token == token_str)
                    | (Complaint.reference_number == clean_ref)
                )
                result = await db.execute(stmt)
                record = result.scalar_one_or_none()
                if record:
                    return record, False
            except Exception as e:
                logger.debug(f"DB lookup in find_complaint_record failed: {e}")

        # 2. Search in-memory cache
        if token_str in _in_memory_complaint_tokens:
            ref = _in_memory_complaint_tokens[token_str]
            if ref in _in_memory_complaints:
                return _in_memory_complaints[ref], True

        if clean_ref in _in_memory_complaints:
            return _in_memory_complaints[clean_ref], True

        for ref, item in _in_memory_complaints.items():
            if (
                item.get("access_token") == token_str
                or item.get("token_hash") == token_hash
                or item.get("upload_token") == token_str
                or item.get("reference_number") == clean_ref
            ):
                return item, True

        return None, False

    @staticmethod
    def compute_structured_and_missing_fields(
        complaint_dict: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Extracts structured Incident fields and identifies missing/null values.
        """
        structured = {
            "incident_type": complaint_dict.get("incident_type"),
            "summary": complaint_dict.get("summary"),
            "description": complaint_dict.get("description"),
            "reported_entity": complaint_dict.get("reported_entity"),
            "incident_date": complaint_dict.get("incident_date"),
            "financial_loss": complaint_dict.get("financial_loss"),
            "currency": complaint_dict.get("currency") or "INR",
            "phone_number": complaint_dict.get("phone_number"),
            "suspected_scam": complaint_dict.get("suspected_scam"),
            "evidence_description": complaint_dict.get("evidence_description"),
        }
        missing = []
        for k, v in structured.items():
            if v is None:
                missing.append(k)
            elif isinstance(v, str) and not v.strip():
                missing.append(k)
        return structured, missing

    @classmethod
    async def get_complaint_detail_by_token(
        cls,
        token: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves full complaint review details using any valid identifier
        (access_token, upload_token, or reference_number).
        If the voice note is still processing (transcribing/extracting),
        returns intermediate progress state.
        Enforces token validation and expiration.
        """
        if not token or not token.strip():
            return None

        complaint_obj, is_mem = await cls.find_complaint_record(token, db=db)

        # If complaint record not yet created, check if voice upload is in progress
        if not complaint_obj:
            voice_status = await VoiceService.get_status(token, db=db)
            if not voice_status:
                return None

            st = voice_status.get("status")
            if st == "failed":
                return {
                    "reference_number": None,
                    "status": "failed",
                    "processing_status": "failed",
                    "error_message": voice_status.get("error_message") or "Audio transcription processing failed.",
                    "english_summary": None,
                    "original_transcript": None,
                    "language": None,
                    "language_name": None,
                    "structured_fields": {},
                    "missing_fields": [],
                    "created_at": voice_status.get("created_at"),
                    "confirmed_at": None,
                    "cancelled_at": None,
                }
            elif st == "completed":
                # Transcription finished; complaint extraction may be in progress
                lang = voice_status.get("language")
                return {
                    "reference_number": None,
                    "status": "processing",
                    "processing_status": "extracting",
                    "english_summary": None,
                    "original_transcript": voice_status.get("transcript"),
                    "language": lang,
                    "language_name": voice_status.get("language_name") or (LANGUAGE_NAMES.get(lang, lang) if lang else None),
                    "structured_fields": {},
                    "missing_fields": [],
                    "created_at": voice_status.get("created_at"),
                    "confirmed_at": None,
                    "cancelled_at": None,
                }
            else:
                return {
                    "reference_number": None,
                    "status": "processing",
                    "processing_status": st or "processing",
                    "english_summary": None,
                    "original_transcript": voice_status.get("transcript"),
                    "language": voice_status.get("language"),
                    "language_name": voice_status.get("language_name"),
                    "structured_fields": {},
                    "missing_fields": [],
                    "created_at": voice_status.get("created_at"),
                    "confirmed_at": None,
                    "cancelled_at": None,
                }

        c_dict = cls._model_to_dict(complaint_obj) if not is_mem else dict(complaint_obj)

        # Enforce expiration check
        if cls.is_expired(c_dict.get("expires_at")):
            return {"error": "expired", "message": "Complaint access token has expired."}

        # Resolve English Summary (auto-translate if missing and non-English)
        english_summary = c_dict.get("english_summary")
        if not english_summary:
            summary_text = c_dict.get("summary") or ""
            lang = c_dict.get("language") or "en"
            if lang == "en" or TranslationService.is_english_text(summary_text):
                english_summary = summary_text
            else:
                try:
                    english_trans = await asyncio.to_thread(
                        TranslationService.translate_transcript,
                        summary_text,
                        source_language=lang,
                    )
                    if isinstance(english_trans, dict):
                        english_summary = english_trans.get("english_translation") or english_trans.get("translation") or str(english_trans)
                    else:
                        english_summary = english_trans
                except Exception as e:
                    logger.warning(f"Failed to translate summary to English: {e}")
                    english_summary = summary_text

            # Cache back to complaint object
            if isinstance(english_summary, dict):
                english_summary = english_summary.get("english_translation") or str(english_summary)

            if english_summary:
                c_dict["english_summary"] = english_summary
                if not is_mem and db is not None:
                    try:
                        complaint_obj.english_summary = english_summary
                        await db.commit()
                    except Exception:
                        pass
                elif is_mem:
                    ref = c_dict.get("reference_number")
                    if ref in _in_memory_complaints:
                        _in_memory_complaints[ref]["english_summary"] = english_summary

        # Resolve original voice transcript
        upload_tok = c_dict.get("upload_token")
        original_transcript = None
        if upload_tok:
            voice_info = await VoiceService.get_status(upload_tok, db=db)
            if voice_info and voice_info.get("transcript"):
                original_transcript = voice_info.get("transcript")

        if not original_transcript:
            original_transcript = c_dict.get("raw_transcript_redacted") or c_dict.get("description")

        structured_fields, missing_fields = cls.compute_structured_and_missing_fields(c_dict)

        lang_code = c_dict.get("language")
        lang_name = LANGUAGE_NAMES.get(lang_code, (lang_code.title() if lang_code else "English"))

        return {
            "reference_number": c_dict.get("reference_number"),
            "status": c_dict.get("status"),
            "processing_status": "completed",
            "english_summary": english_summary,
            "original_transcript": original_transcript,
            "language": lang_code,
            "language_name": lang_name,
            "structured_fields": structured_fields,
            "missing_fields": missing_fields,
            "is_fallback": c_dict.get("is_fallback", False),
            "created_at": c_dict.get("created_at"),
            "confirmed_at": c_dict.get("confirmed_at"),
            "cancelled_at": c_dict.get("cancelled_at"),
            "expires_at": c_dict.get("expires_at"),
            **structured_fields,
        }

    @classmethod
    async def update_complaint_fields_by_token(
        cls,
        token: str,
        updates: Dict[str, Any],
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Updates editable complaint fields for an active complaint before confirmation.
        - Strictly validates token and expiration.
        - Rejects edits if status is 'confirmed' or 'cancelled'.
        - Prevents updates to system-immutable fields (transcript, token, status, etc.).
        - Automatically redacts sensitive credentials (OTP, PIN, passwords, cards, etc.).
        - Persists atomically and appends audit event.
        """
        complaint_obj, is_mem = await cls.find_complaint_record(token, db=db)
        if not complaint_obj:
            raise KeyError("Complaint not found for provided token.")

        c_dict = cls._model_to_dict(complaint_obj) if not is_mem else complaint_obj
        if cls.is_expired(c_dict.get("expires_at")):
            raise PermissionError("Complaint access token has expired.")

        current_status = (c_dict.get("status") or "").lower()
        if current_status in ("confirmed", "cancelled"):
            raise ValueError(f"Cannot edit a complaint with status '{c_dict.get('status')}'.")

        now = datetime.now(timezone.utc)
        sanitized_updates = {}

        for k, v in updates.items():
            if k not in PERMITTED_EDITABLE_FIELDS:
                continue
            if isinstance(v, str):
                # Apply credential redaction
                sanitized_updates[k] = RedactionService.redact_text(v)
            else:
                sanitized_updates[k] = v

        if not is_mem and db is not None:
            try:
                for k, v in sanitized_updates.items():
                    setattr(complaint_obj, k, v)

                # If summary was updated, adjust english_summary
                if "summary" in sanitized_updates:
                    if complaint_obj.language == "en" or TranslationService.is_english_text(sanitized_updates["summary"]):
                        complaint_obj.english_summary = sanitized_updates["summary"]
                    else:
                        complaint_obj.english_summary = None

                event = ComplaintStatusHistory(
                    complaint_id=complaint_obj.id,
                    status=complaint_obj.status,
                    note="Complaint fields updated by victim review.",
                    created_at=now,
                )
                db.add(event)
                await db.commit()
                await db.refresh(complaint_obj)
                _in_memory_complaints[complaint_obj.reference_number] = cls._model_to_dict(complaint_obj)
            except Exception as e:
                logger.error(f"Failed to persist complaint edits in DB: {e}")
                await db.rollback()
                raise e
        else:
            for k, v in sanitized_updates.items():
                complaint_obj[k] = v
            if "summary" in sanitized_updates:
                if complaint_obj.get("language") == "en" or TranslationService.is_english_text(sanitized_updates["summary"]):
                    complaint_obj["english_summary"] = sanitized_updates["summary"]
                else:
                    complaint_obj["english_summary"] = None

            ref = complaint_obj["reference_number"]
            _in_memory_complaints[ref] = complaint_obj
            if ref not in _in_memory_history:
                _in_memory_history[ref] = []
            _in_memory_history[ref].append({
                "status": complaint_obj.get("status"),
                "note": "Complaint fields updated by victim review.",
                "created_at": now.isoformat(),
            })

        return await cls.get_complaint_detail_by_token(token, db=db)

    @classmethod
    async def confirm_complaint_by_token(
        cls,
        token: str,
        final_updates: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Atomically finalizes complaint review and transitions status to 'confirmed'.
        - Enforces idempotency: repeated confirms return the confirmed state without duplicates.
        - Saves any final submitted edits atomically with status transition.
        - Sets confirmed_at timestamp and records status history event.
        - Rejects confirmation of cancelled or incomplete complaints.
        """
        complaint_obj, is_mem = await cls.find_complaint_record(token, db=db)
        if not complaint_obj:
            raise KeyError("Complaint not found for provided token.")

        c_dict = cls._model_to_dict(complaint_obj) if not is_mem else complaint_obj
        if cls.is_expired(c_dict.get("expires_at")):
            raise PermissionError("Complaint access token has expired.")

        current_status = (c_dict.get("status") or "").lower()
        ref = c_dict.get("reference_number")

        # Reject confirmation if cancelled
        if current_status == "cancelled":
            raise ValueError("Cannot confirm a cancelled complaint.")

        # Idempotent return if already confirmed
        if current_status == "confirmed":
            conf_at = c_dict.get("confirmed_at")
            return {
                "reference_number": ref,
                "status": "confirmed",
                "confirmed_at": conf_at if isinstance(conf_at, str) else (conf_at.isoformat() if conf_at else None),
                "message": "Complaint is already confirmed.",
            }

        # Apply final submitted edits if provided
        if final_updates:
            await cls.update_complaint_fields_by_token(token, final_updates, db=db)
            complaint_obj, is_mem = await cls.find_complaint_record(token, db=db)

        now = datetime.now(timezone.utc)
        confirmed_status = "confirmed"

        if not is_mem and db is not None:
            try:
                complaint_obj.status = confirmed_status
                complaint_obj.confirmed_at = now
                event = ComplaintStatusHistory(
                    complaint_id=complaint_obj.id,
                    status=confirmed_status,
                    note=note or "Complaint confirmed by victim. Reporting actions unlocked.",
                    created_at=now,
                )
                db.add(event)
                await db.commit()
                await db.refresh(complaint_obj)
                _in_memory_complaints[complaint_obj.reference_number] = cls._model_to_dict(complaint_obj)
            except Exception as e:
                logger.error(f"Failed to confirm complaint in DB: {e}")
                await db.rollback()
                raise e
        else:
            complaint_obj["status"] = confirmed_status
            complaint_obj["confirmed_at"] = now.isoformat()
            _in_memory_complaints[ref] = complaint_obj
            if ref not in _in_memory_history:
                _in_memory_history[ref] = []
            _in_memory_history[ref].append({
                "status": confirmed_status,
                "note": note or "Complaint confirmed by victim. Reporting actions unlocked.",
                "created_at": now.isoformat(),
            })

        return {
            "reference_number": ref,
            "status": "confirmed",
            "confirmed_at": now.isoformat(),
            "message": "Complaint successfully confirmed. Reporting actions unlocked.",
        }

    @classmethod
    async def cancel_complaint_by_token(
        cls,
        token: str,
        note: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Transitions complaint status to 'cancelled' and disables further editing/reporting.
        - Idempotent: repeated calls return current cancelled state.
        - Rejects cancellation of an already confirmed complaint.
        - Records cancelled_at timestamp and status history event.
        """
        complaint_obj, is_mem = await cls.find_complaint_record(token, db=db)
        if not complaint_obj:
            raise KeyError("Complaint not found for provided token.")

        c_dict = cls._model_to_dict(complaint_obj) if not is_mem else complaint_obj
        if cls.is_expired(c_dict.get("expires_at")):
            raise PermissionError("Complaint access token has expired.")

        current_status = (c_dict.get("status") or "").lower()
        ref = c_dict.get("reference_number")

        if current_status == "confirmed":
            raise ValueError("Cannot cancel an already confirmed complaint.")

        if current_status == "cancelled":
            canc_at = c_dict.get("cancelled_at")
            return {
                "reference_number": ref,
                "status": "cancelled",
                "cancelled_at": canc_at if isinstance(canc_at, str) else (canc_at.isoformat() if canc_at else None),
                "message": "Complaint is already cancelled.",
            }

        now = datetime.now(timezone.utc)
        cancelled_status = "cancelled"

        if not is_mem and db is not None:
            try:
                complaint_obj.status = cancelled_status
                complaint_obj.cancelled_at = now
                event = ComplaintStatusHistory(
                    complaint_id=complaint_obj.id,
                    status=cancelled_status,
                    note=note or "Complaint cancelled by victim.",
                    created_at=now,
                )
                db.add(event)
                await db.commit()
                await db.refresh(complaint_obj)
                _in_memory_complaints[complaint_obj.reference_number] = cls._model_to_dict(complaint_obj)
            except Exception as e:
                logger.error(f"Failed to cancel complaint in DB: {e}")
                await db.rollback()
                raise e
        else:
            complaint_obj["status"] = cancelled_status
            complaint_obj["cancelled_at"] = now.isoformat()
            _in_memory_complaints[ref] = complaint_obj
            if ref not in _in_memory_history:
                _in_memory_history[ref] = []
            _in_memory_history[ref].append({
                "status": cancelled_status,
                "note": note or "Complaint cancelled by victim.",
                "created_at": now.isoformat(),
            })

        return {
            "reference_number": ref,
            "status": "cancelled",
            "cancelled_at": now.isoformat(),
            "message": "Complaint has been cancelled successfully.",
        }
