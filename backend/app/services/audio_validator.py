import io
import logging
import os
import secrets
from typing import Optional, Tuple
from fastapi import HTTPException, status
from tinytag import TinyTag
import mutagen

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Standard allowed formats
SUPPORTED_FORMATS = {"webm", "ogg", "mp3", "wav", "m4a"}

# Allowed MIME types mapping
MIME_FORMAT_MAP = {
    # WebM
    "audio/webm": "webm",
    "video/webm": "webm",
    # Ogg
    "audio/ogg": "ogg",
    "application/ogg": "ogg",
    "audio/opus": "ogg",
    "audio/vorbis": "ogg",
    # MP3
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mpg": "mp3",
    # WAV
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    # M4A / MP4 Audio
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/aac": "m4a",
}

# Generic / Fallback MIME types often sent by mobile browsers or FormData
PERMISSIVE_MIME_TYPES = {
    "application/octet-stream",
    "binary/octet-stream",
    "",
}


def detect_audio_format_from_bytes(header_bytes: bytes) -> Optional[str]:
    """
    Inspect the binary header (magic bytes) of an audio file to determine
    its actual format, independent of client filename or MIME header.
    """
    if len(header_bytes) < 4:
        return None

    # 1. WAV (RIFF....WAVE)
    if header_bytes[:4] == b"RIFF" and len(header_bytes) >= 12 and header_bytes[8:12] == b"WAVE":
        return "wav"

    # 2. Ogg (OggS)
    if header_bytes[:4] == b"OggS":
        return "ogg"

    # 3. WebM / Matroska (\x1a\x45\xdf\xa3)
    if header_bytes[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"

    # 4. MP3: ID3v2 tag (ID3) or MPEG audio frame sync (\xff\xfb, \xff\xf3, \xff\xf2, \xff\xe3)
    if header_bytes[:3] == b"ID3":
        return "mp3"
    if header_bytes[0] == 0xFF and (header_bytes[1] & 0xE0) == 0xE0:
        return "mp3"

    # 5. M4A / MP4: offset 4 contains 'ftyp'
    if len(header_bytes) >= 12 and header_bytes[4:8] == b"ftyp":
        major_brand = header_bytes[8:12]
        if major_brand in (b"M4A ", b"M4B ", b"mp41", b"mp42", b"isom", b"dash", b"qt  "):
            return "m4a"

    return None


def get_webm_duration_from_file(file_path: str) -> Optional[float]:
    """
    Extract duration from WebM / Matroska EBML container.
    Parses Segment Info Duration and TimecodeScale or Cluster timestamps.
    """
    try:
        import ebmlite
        schema = ebmlite.loadSchema("matroska.xml")
        doc = schema.load(file_path)
        for el in doc:
            if el.name == "Segment":
                timecode_scale = 1_000_000  # Default 1ms in nanoseconds
                duration_val = None
                last_cluster_time = None
                for child in el:
                    if child.name == "Info":
                        for info_child in child:
                            if info_child.name in ("TimestampScale", "TimecodeScale"):
                                timecode_scale = info_child.value
                            elif info_child.name == "Duration":
                                duration_val = info_child.value
                    elif child.name == "Cluster":
                        for cluster_child in child:
                            if cluster_child.name in ("Timestamp", "Timecode"):
                                last_cluster_time = cluster_child.value
                if duration_val is not None:
                    return float(duration_val) * (timecode_scale / 1_000_000_000.0)
                if last_cluster_time is not None:
                    return float(last_cluster_time) * (timecode_scale / 1_000_000_000.0)
    except Exception as e:
        logger.debug(f"EBML duration inspection error: {e}")
    return None


def extract_audio_duration(file_path: str, detected_format: str) -> Optional[float]:
    """
    Extract audio duration in seconds using TinyTag, Mutagen, or WebM EBML parsing.
    """
    # 1. Try TinyTag for standard audio formats (WAV, MP3, OGG, M4A)
    try:
        tag = TinyTag.get(file_path)
        if tag.duration is not None and tag.duration > 0:
            return float(tag.duration)
    except Exception:
        pass

    # 2. Try Mutagen as secondary reader
    try:
        mut_audio = mutagen.File(file_path)
        if mut_audio is not None and mut_audio.info and hasattr(mut_audio.info, "length"):
            if mut_audio.info.length > 0:
                return float(mut_audio.info.length)
    except Exception:
        pass

    # 3. For WebM recordings
    if detected_format == "webm":
        webm_dur = get_webm_duration_from_file(file_path)
        if webm_dur is not None and webm_dur > 0:
            return float(webm_dur)

    return None


class AudioValidationResult:
    def __init__(
        self,
        token: str,
        detected_format: str,
        mime_type: str,
        file_size_bytes: int,
        duration_seconds: Optional[float],
        file_path: str,
        filename: str,
    ):
        self.token = token
        self.detected_format = detected_format
        self.mime_type = mime_type
        self.file_size_bytes = file_size_bytes
        self.duration_seconds = duration_seconds
        self.file_path = file_path
        self.filename = filename


def validate_and_save_audio(
    file_bytes: bytes,
    content_type: Optional[str] = None,
    client_duration: Optional[float] = None,
    storage_dir: Optional[str] = None,
) -> AudioValidationResult:
    """
    Performs comprehensive validation on uploaded audio:
    1. Rejects empty files (400 Bad Request)
    2. Rejects files exceeding max size (5 MB) (413 Payload Too Large)
    3. Validates actual format via binary magic bytes (415 Unsupported Media Type)
    4. Validates MIME type consistency (415 Unsupported Media Type)
    5. Saves audio temporarily with a cryptographically secure token
    6. Validates duration <= 120s (2 minutes) (400 Bad Request)
    """
    file_size = len(file_bytes)

    # 1. Check for empty file
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty. Please record or upload a valid audio note.",
        )

    # 2. Check maximum size (5 MB)
    max_size = settings.MAX_AUDIO_SIZE_BYTES
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Audio file exceeds maximum allowed limit of {max_size // (1024 * 1024)} MB.",
        )

    # 3. Detect actual format from binary magic bytes
    detected_format = detect_audio_format_from_bytes(file_bytes[:32])
    if not detected_format or detected_format not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invalid or unsupported audio format. Allowed formats: .webm, .ogg, .mp3, .wav, .m4a.",
        )

    # 4. Check MIME type if provided
    normalized_content_type = (content_type or "").split(";")[0].strip().lower()
    if normalized_content_type and normalized_content_type not in PERMISSIVE_MIME_TYPES:
        expected_format = MIME_FORMAT_MAP.get(normalized_content_type)
        if expected_format is None or (expected_format != detected_format and not (expected_format in ("m4a", "mp4") and detected_format == "m4a")):
            logger.warning(
                f"MIME type mismatch: declared '{normalized_content_type}' but detected format is '{detected_format}'"
            )
            # If the declared MIME is completely outside allowed audio types, reject
            if normalized_content_type not in MIME_FORMAT_MAP:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Unsupported MIME type '{normalized_content_type}'. Allowed types: webm, ogg, mp3, wav, m4a.",
                )

    # 5. Check client-reported duration if provided
    max_duration = settings.MAX_AUDIO_DURATION_SECONDS
    if client_duration is not None and client_duration > max_duration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio recording duration ({client_duration:.1f}s) exceeds maximum limit of {int(max_duration)} seconds (2 minutes).",
        )

    # 6. Generate cryptographically secure token and safe filename
    # Uses 32 bytes of secure entropy (43 URL-safe characters)
    token = secrets.token_urlsafe(32)
    safe_filename = f"{token}.{detected_format}"

    # Determine storage directory
    target_dir = storage_dir or settings.VOICE_UPLOAD_DIR
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, safe_filename)

    # Write file securely
    try:
        with open(target_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        logger.error(f"Failed to write audio file to storage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to safely store audio recording. Please try again.",
        )

    # 7. Extract actual duration from saved audio file
    detected_duration = extract_audio_duration(target_path, detected_format)
    final_duration = detected_duration if detected_duration is not None else client_duration

    # If duration exceeds 2 minutes, delete file and reject
    if final_duration is not None and final_duration > max_duration:
        try:
            if os.path.exists(target_path):
                os.remove(target_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio recording duration ({final_duration:.1f}s) exceeds maximum limit of {int(max_duration)} seconds (2 minutes).",
        )

    effective_mime = normalized_content_type if normalized_content_type in MIME_FORMAT_MAP else f"audio/{detected_format}"

    return AudioValidationResult(
        token=token,
        detected_format=detected_format,
        mime_type=effective_mime,
        file_size_bytes=file_size,
        duration_seconds=round(final_duration, 2) if final_duration is not None else None,
        file_path=target_path,
        filename=safe_filename,
    )
