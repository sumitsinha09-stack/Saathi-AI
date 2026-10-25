import logging
import os
import threading
from typing import Any, Dict, Optional

import av
from faster_whisper import WhisperModel

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Apply safe monkeypatch for av.open to maintain compatibility with PyAV 14+
# Faster-whisper calls av.open(..., metadata_errors="ignore"), which is unsupported in newer PyAV
_original_av_open = av.open


def _safe_av_open(*args, **kwargs):
    kwargs.pop("metadata_errors", None)
    return _original_av_open(*args, **kwargs)


av.open = _safe_av_open

# Mapping of Whisper language codes to user-friendly display names
SUPPORTED_LANGUAGE_MAP = {
    "hi": "Hindi",
    "ta": "Tamil",
    "en": "English",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
}


class TranscriptionService:
    """
    Local speech-to-text transcription service powered by Faster-Whisper.
    Employs a thread-safe singleton pattern to load the model once and reuse it across requests.
    Enforces local inference with strict language preservation (no auto-translation).
    """

    _model: Optional[WhisperModel] = None
    _lock = threading.Lock()
    _loaded_model_size: Optional[str] = None

    @classmethod
    def get_model(cls) -> WhisperModel:
        """
        Thread-safe singleton getter for the Faster-Whisper model.
        Loads once and reuses in memory. Supports upgrading to large-v3 via settings.
        """
        requested_size = settings.WHISPER_MODEL_SIZE

        # Check if model is already loaded with the requested size
        if cls._model is not None and cls._loaded_model_size == requested_size:
            return cls._model

        with cls._lock:
            # Double-check inside lock
            if cls._model is not None and cls._loaded_model_size == requested_size:
                return cls._model

            logger.info(
                f"Initializing Faster-Whisper model: size='{requested_size}', "
                f"device='{settings.WHISPER_DEVICE}', compute_type='{settings.WHISPER_COMPUTE_TYPE}'"
            )

            try:
                cls._model = WhisperModel(
                    requested_size,
                    device=settings.WHISPER_DEVICE,
                    compute_type=settings.WHISPER_COMPUTE_TYPE,
                )
                cls._loaded_model_size = requested_size
                logger.info(f"Faster-Whisper '{requested_size}' model loaded successfully.")
                return cls._model
            except Exception as e:
                logger.warning(
                    f"Failed to load configured Whisper model '{requested_size}': {e}. "
                    f"Attempting fallback to '{settings.WHISPER_FALLBACK_MODEL_SIZE}'."
                )

                # Fallback to lightweight model if configured size is unavailable/out of memory
                try:
                    cls._model = WhisperModel(
                        settings.WHISPER_FALLBACK_MODEL_SIZE,
                        device=settings.WHISPER_DEVICE,
                        compute_type=settings.WHISPER_COMPUTE_TYPE,
                    )
                    cls._loaded_model_size = settings.WHISPER_FALLBACK_MODEL_SIZE
                    logger.info(f"Fallback Faster-Whisper model '{cls._loaded_model_size}' loaded successfully.")
                    return cls._model
                except Exception as fallback_err:
                    logger.error(f"Critical: Failed to load fallback Whisper model: {fallback_err}")
                    raise RuntimeError(f"Speech recognition model unavailable: {fallback_err}")

    @classmethod
    def transcribe_audio(
        cls,
        file_path: str,
        beam_size: Optional[int] = None,
        vad_filter: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file locally.
        - Automatically detects language (Hindi, Tamil, English, etc.)
        - Strictly preserves the spoken language (task='transcribe', no translation)
        - Returns transcript, detected language code, human-readable name, and confidence score.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file for transcription not found at '{file_path}'")

        model = cls.get_model()
        eff_beam = beam_size if beam_size is not None else settings.WHISPER_BEAM_SIZE
        eff_vad = vad_filter if vad_filter is not None else settings.WHISPER_VAD_FILTER

        logger.info(f"Starting local transcription for: '{file_path}'")

        try:
            # task='transcribe' guarantees spoken language is preserved in its original script
            segments, info = model.transcribe(
                file_path,
                beam_size=eff_beam,
                vad_filter=eff_vad,
                task="transcribe",
            )

            # Accumulate transcribed segments
            transcript_parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    transcript_parts.append(text)

            full_transcript = " ".join(transcript_parts).strip()

            # If VAD filter yielded empty transcript, retry with vad_filter=False to avoid dropping valid audio
            if not full_transcript and eff_vad:
                logger.info("VAD filter yielded empty transcript; re-running with vad_filter=False")
                segments, info = model.transcribe(
                    file_path,
                    beam_size=eff_beam,
                    vad_filter=False,
                    task="transcribe",
                )
                transcript_parts = [s.text.strip() for s in segments if s.text.strip()]
                full_transcript = " ".join(transcript_parts).strip()

            detected_code = (info.language or "en").lower()
            language_name = SUPPORTED_LANGUAGE_MAP.get(detected_code, detected_code.title())
            language_probability = round(float(info.language_probability), 3) if info.language_probability else 0.0
            duration_val = round(float(info.duration), 2) if hasattr(info, "duration") and info.duration else None

            logger.info(
                f"Transcription complete: language='{detected_code}' ({language_name}, "
                f"prob={language_probability}), length={len(full_transcript)} chars"
            )

            return {
                "transcript": full_transcript,
                "language": detected_code,
                "language_name": language_name,
                "language_probability": language_probability,
                "duration_seconds": duration_val,
            }

        except Exception as e:
            logger.error(f"Error during audio transcription: {e}", exc_info=True)
            raise
