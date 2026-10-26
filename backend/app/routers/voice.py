import asyncio
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import AsyncSessionLocal, get_db
from backend.app.models import Complaint
from backend.app.services.audio_validator import validate_and_save_audio
from backend.app.services.complaint_service import ComplaintService
from backend.app.services.extraction_service import ExtractionService
from backend.app.services.transcription_service import TranscriptionService
from backend.app.services.translation_service import TranslationService
from backend.app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["Voice Recording & Ingestion"])


class TranslateRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=128, description="Cryptographic tracking token")
    force_refresh: bool = Field(default=False, description="Whether to re-translate if already cached")


async def process_voice_transcription(token: str, file_path: str) -> None:
    """
    Background worker that performs local speech-to-text transcription.
    1. Updates job status to 'transcribing'.
    2. Runs Faster-Whisper inference asynchronously via thread pool.
    3. Saves detected language and transcript, transitioning to 'completed'.
    4. Phase 4: Triggers automated AI complaint extraction & persistence.
    5. MANDATORY PRIVACY POLICY: Unconditionally deletes temporary audio file in finally block.
    """
    logger.info(f"Background transcription job initiated for token: {token}")
    await VoiceService.update_status(token=token, status_value="transcribing")

    try:
        # Run local Faster-Whisper transcription without blocking async event loop
        result = await asyncio.to_thread(
            TranscriptionService.transcribe_audio,
            file_path=file_path,
        )

        await VoiceService.update_transcription(
            token=token,
            transcript=result["transcript"],
            language=result["language"],
            language_name=result["language_name"],
            language_probability=result["language_probability"],
            status_value="completed",
        )
        logger.info(
            f"Transcription successfully completed for token: {token} "
            f"(Language: {result['language_name']}, Probability: {result['language_probability']})"
        )

        # Phase 4 Pipeline: Trigger Complaint Extraction & Persistence
        try:
            logger.info(f"Initiating complaint extraction for token: {token}")
            incident = await asyncio.to_thread(
                ExtractionService.extract_incident,
                transcript=result["transcript"],
                language=result["language"],
            )

            try:
                async with AsyncSessionLocal() as session:
                    complaint = await ComplaintService.create_complaint(
                        incident=incident,
                        upload_token=token,
                        db=session,
                    )
            except Exception as db_sess_err:
                logger.debug(f"Direct DB session failed ({db_sess_err}); falling back to memory store")
                complaint = await ComplaintService.create_complaint(
                    incident=incident,
                    upload_token=token,
                    db=None,
                )
            logger.info(f"Complaint {complaint.get('reference_number')} successfully generated for token {token}")
        except Exception as extract_err:
            logger.error(f"Complaint extraction failed for token {token}: {extract_err}", exc_info=True)

    except Exception as e:
        logger.error(f"Transcription failed for token {token}: {e}", exc_info=True)
        await VoiceService.update_status(
            token=token,
            status_value="failed",
            error_message="Audio transcription processing failed.",
        )

    finally:
        # ZERO RETENTION ENFORCEMENT:
        # File must be permanently deleted immediately post-transcription
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Transient audio spool file permanently deleted for token: {token}")
        except OSError as cleanup_err:
            logger.warning(f"Error purging temporary audio file for token {token}: {cleanup_err}")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Upload and validate a voice note or audio file",
    description="Accepts multipart/form-data audio uploads up to 5 MB and 2 minutes in duration. Validates binary headers, MIME type, and duration. Returns a secure token and processes audio asynchronously in background.",
)
async def upload_voice_note(
    background_tasks: BackgroundTasks,
    audio: Optional[UploadFile] = File(None, description="Audio file payload (audio or file field)"),
    file: Optional[UploadFile] = File(None, description="Alternative field name for audio file"),
    duration: Optional[float] = Form(None, description="Optional client-measured recording duration in seconds"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Accepts audio upload via 'audio' or 'file' form-data field.
    Performs multi-layer validation (size <= 5MB, duration <= 120s, magic bytes check).
    Temporarily saves valid audio file with a cryptographically secure token.
    Dispatches asynchronous local Faster-Whisper transcription.
    Never exposes internal file paths or server details.
    """
    upload_file = audio or file
    if upload_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file was provided. Please include an audio file in the 'audio' or 'file' field.",
        )

    try:
        file_bytes = await upload_file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded audio file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded audio stream. Please try again.",
        )

    # Validate audio format, size, MIME type, and duration
    validation = validate_and_save_audio(
        file_bytes=file_bytes,
        content_type=upload_file.content_type,
        client_duration=duration,
    )

    # Record initial receipt in database / memory cache
    response = await VoiceService.record_upload(validation=validation, db=db)

    # Dispatch background transcription job
    background_tasks.add_task(
        process_voice_transcription,
        token=validation.token,
        file_path=validation.file_path,
    )

    return response


@router.get(
    "/status/{token}",
    status_code=status.HTTP_200_OK,
    summary="Poll status of an uploaded voice note",
    description="Returns current status (received, transcribing, completed, failed) of a voice upload using its secure token, including transcript and detected language when finished.",
)
async def get_voice_status(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Poll upload and ingestion progress using the returned token.
    Safe against unauthorized access and hides internal paths.
    """
    # Sanitize token input
    if not token or len(token) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token format provided.",
        )

    status_data = await VoiceService.get_status(token=token, db=db)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice upload not found or token has expired.",
        )

    # Attach AI Complaint metadata if available
    complaint_data = ComplaintService.get_complaint_by_upload_token(token)
    if not complaint_data and db is not None:
        try:
            stmt = select(Complaint).where(Complaint.upload_token == token)
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            if record:
                complaint_data = ComplaintService._model_to_dict(record)
        except Exception:
            pass

    if complaint_data:
        status_data["complaint_reference"] = complaint_data.get("reference_number")
        status_data["complaint_status"] = complaint_data.get("status")
        status_data["complaint_access_token"] = complaint_data.get("access_token")
        status_data["complaint_is_fallback"] = complaint_data.get("is_fallback")
        safe_complaint = dict(complaint_data)
        safe_complaint.pop("token_hash", None)
        status_data["complaint"] = safe_complaint
    else:
        status_data["complaint_reference"] = None
        status_data["complaint_status"] = None
        status_data["complaint_access_token"] = None
        status_data["complaint_is_fallback"] = None
        status_data["complaint"] = None

    return status_data


@router.post(
    "/{token}/extract",
    status_code=status.HTTP_200_OK,
    summary="Trigger AI complaint extraction on completed transcript",
    description="Extracts structured complaint fields using local Qwen3 from completed speech transcript with sensitive information redaction.",
)
async def extract_complaint_for_voice(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    On-demand endpoint to extract and persist an Incident complaint from a completed transcript.
    - Idempotent: returns existing complaint if already generated.
    - Requires completed transcription.
    - Runs 100% locally with redaction of sensitive credentials.
    """
    token = token.strip()
    status_data = await VoiceService.get_status(token=token, db=db)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice upload not found or token has expired.",
        )

    if status_data.get("status") != "completed" or not status_data.get("transcript"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcription must be completed before extracting complaint (current status: '{status_data.get('status')}').",
        )

    # Idempotent check
    existing = ComplaintService.get_complaint_by_upload_token(token)
    if existing:
        safe_c = dict(existing)
        safe_c.pop("token_hash", None)
        return {
            "token": token,
            "complaint": safe_c,
            "message": "Complaint retrieved from existing record.",
        }

    # Run extraction via thread pool
    try:
        incident = await asyncio.to_thread(
            ExtractionService.extract_incident,
            transcript=status_data["transcript"],
            language=status_data.get("language") or "hi",
        )

        complaint = await ComplaintService.create_complaint(
            incident=incident,
            upload_token=token,
            db=db,
        )

        safe_c = dict(complaint)
        safe_c.pop("token_hash", None)
        return {
            "token": token,
            "complaint": safe_c,
            "message": "Complaint successfully extracted and stored.",
        }
    except Exception as e:
        logger.error(f"Manual complaint extraction failed for token {token}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Complaint extraction failed. Please try again.",
        )



@router.post(
    "/translate",
    status_code=status.HTTP_200_OK,
    summary="Translate transcript into English",
    description="Translates the stored transcript for a voice upload token into natural English locally. Preserves original speech and does not re-translate if already available unless force_refresh is requested.",
)
async def translate_voice_transcript(
    payload: TranslateRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Accepts secure token, retrieves transcript, and generates natural English translation.
    - Caches translation on the record so subsequent calls return without re-computing.
    - Keeps original transcript unmodified.
    - Automatically identifies if original speech is already in English.
    - Runs 100% locally with zero external translation API leaks.
    """
    token = payload.token.strip()
    if not token or len(token) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token format provided.",
        )

    status_data = await VoiceService.get_status(token=token, db=db)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice upload not found or token has expired.",
        )

    if status_data.get("status") != "completed" or not status_data.get("transcript"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcript is not yet available for translation (current status: '{status_data.get('status')}').",
        )

    # Return cached translation if already generated and force_refresh is False
    cached_translation = status_data.get("english_translation")
    if cached_translation and not payload.force_refresh:
        is_already_en = status_data.get("language") == "en"
        return {
            "token": token,
            "transcript": status_data["transcript"],
            "language": status_data.get("language"),
            "language_name": status_data.get("language_name"),
            "english_translation": cached_translation,
            "is_already_english": is_already_en,
            "cached": True,
            "message": "Speech is already in English. Translation unnecessary." if is_already_en else "Translation retrieved from cache.",
        }

    # Run local translation asynchronously without blocking event loop
    try:
        translation_result = await asyncio.to_thread(
            TranslationService.translate_transcript,
            text=status_data["transcript"],
            source_language=status_data.get("language"),
        )
    except Exception as e:
        logger.error(f"Translation failed for token {token}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Local speech translation failed. Please try again.",
        )

    # Save translation to DB and cache
    await VoiceService.update_translation(
        token=token,
        english_translation=translation_result["english_translation"],
        db=db,
    )

    return {
        "token": token,
        "transcript": status_data["transcript"],
        "language": status_data.get("language"),
        "language_name": status_data.get("language_name"),
        "english_translation": translation_result["english_translation"],
        "is_already_english": translation_result["is_already_english"],
        "engine_used": translation_result.get("engine_used"),
        "cached": False,
        "message": translation_result.get("message", "Translation generated successfully."),
    }
