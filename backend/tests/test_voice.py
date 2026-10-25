import io
import os
import struct
import wave
import pytest
from httpx import AsyncClient

from backend.app.config import settings
from backend.app.services.voice_service import VoiceService


def generate_wav_bytes(duration_seconds: float = 2.0, sample_rate: int = 8000) -> bytes:
    """Helper to generate valid WAV bytes in-memory for testing."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        num_frames = int(sample_rate * duration_seconds)
        data = struct.pack("<h", 0) * num_frames
        wav.writeframes(data)
    return buf.getvalue()


def generate_mp3_mock_bytes(size: int = 1024) -> bytes:
    """Mock MP3 bytes with valid ID3v2 header and MPEG frame sync."""
    # ID3v2 header: ID3 + version (3,0) + flags (0) + syncsafe size (10)
    id3 = b"ID3\x03\x00\x00\x00\x00\x00\x0a" + b"\x00" * 10
    # MPEG frame sync \xff\xfb
    body = (b"\xff\xfb\x90\x64" + b"\x00" * 200) * ((size // 204) + 1)
    return id3 + body[:size]


def generate_ogg_mock_bytes(size: int = 1024) -> bytes:
    """Mock OGG bytes with OggS magic header."""
    header = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x1e"
    body = b"\x01vorbis" + b"\x00" * (size - len(header) - 7)
    return header + body


def generate_webm_mock_bytes(size: int = 1024) -> bytes:
    """Mock WebM bytes with EBML magic header \x1a\x45\xdf\xa3."""
    ebml = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81\x04\x42\xf3\x81\x08\x42\x82\x84webm"
    return ebml + b"\x00" * (size - len(ebml))


@pytest.mark.asyncio
async def test_upload_voice_valid_wav(client: AsyncClient):
    """Test successful upload of valid WAV audio."""
    wav_bytes = generate_wav_bytes(duration_seconds=3.0)
    files = {"audio": ("test_recording.wav", wav_bytes, "audio/wav")}

    response = await client.post("/api/voice", files=files)
    assert response.status_code == 201

    data = response.json()
    assert "token" in data
    assert len(data["token"]) >= 32
    assert data["status"] == "received"
    assert data["format"] == "wav"
    assert data["size_bytes"] == len(wav_bytes)
    assert data["duration_seconds"] is not None
    assert 2.9 <= data["duration_seconds"] <= 3.1
    # Ensure internal file path is NEVER exposed
    assert "file_path" not in data
    assert "/storage/" not in str(data)
    assert "/Users/" not in str(data)


@pytest.mark.asyncio
async def test_get_voice_status_success(client: AsyncClient):
    """Test retrieving upload status using valid token."""
    wav_bytes = generate_wav_bytes(duration_seconds=2.0)
    files = {"audio": ("test_recording.wav", wav_bytes, "audio/wav")}

    upload_resp = await client.post("/api/voice", files=files)
    assert upload_resp.status_code == 201
    token = upload_resp.json()["token"]

    status_resp = await client.get(f"/api/voice/status/{token}")
    assert status_resp.status_code == 200

    status_data = status_resp.json()
    assert status_data["token"] == token
    assert status_data["status"] in ("received", "transcribing", "completed")
    assert status_data["format"] == "wav"
    assert status_data["size_bytes"] == len(wav_bytes)
    assert "file_path" not in status_data


@pytest.mark.asyncio
async def test_get_voice_status_not_found(client: AsyncClient):
    """Test 404 when polling non-existent token."""
    response = await client.get("/api/voice/status/non_existent_token_1234567890abcdef")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_empty_audio_file(client: AsyncClient):
    """Test rejection of empty audio files (0 bytes)."""
    files = {"audio": ("empty.wav", b"", "audio/wav")}
    response = await client.post("/api/voice", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_unsupported_format(client: AsyncClient):
    """Test rejection of non-audio / unsupported files."""
    files = {"audio": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00This is a binary", "application/x-msdownload")}
    response = await client.post("/api/voice", files=files)
    assert response.status_code == 415
    assert "unsupported" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_oversized_file(client: AsyncClient):
    """Test rejection of audio files exceeding 5 MB limit."""
    oversized_bytes = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * (5 * 1024 * 1024 + 100)
    files = {"audio": ("large.wav", oversized_bytes, "audio/wav")}
    response = await client.post("/api/voice", files=files)
    assert response.status_code == 413
    assert "5 mb" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_excessive_client_duration(client: AsyncClient):
    """Test rejection when recording exceeds 2 minutes (120 seconds)."""
    wav_bytes = generate_wav_bytes(duration_seconds=1.0)
    files = {"audio": ("recording.wav", wav_bytes, "audio/wav")}
    data = {"duration": "125.0"}  # 125 seconds > 120s limit

    response = await client.post("/api/voice", files=files, data=data)
    assert response.status_code == 400
    assert "exceeds maximum limit of 120 seconds" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_excessive_wav_duration(client: AsyncClient):
    """Test rejection when actual audio file duration > 2 minutes."""
    # Generate 125s of WAV audio
    wav_bytes = generate_wav_bytes(duration_seconds=125.0, sample_rate=4000)
    files = {"audio": ("long.wav", wav_bytes, "audio/wav")}

    response = await client.post("/api/voice", files=files)
    assert response.status_code == 400
    assert "exceeds maximum limit" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_valid_webm_mock(client: AsyncClient):
    """Test upload of valid WebM audio."""
    webm_bytes = generate_webm_mock_bytes(2048)
    files = {"audio": ("recording.webm", webm_bytes, "audio/webm")}
    data = {"duration": "15.5"}

    response = await client.post("/api/voice", files=files, data=data)
    assert response.status_code == 201
    resp_data = response.json()
    assert resp_data["format"] == "webm"
    assert resp_data["status"] == "received"
    assert resp_data["duration_seconds"] == 15.5


@pytest.mark.asyncio
async def test_upload_valid_ogg_mock(client: AsyncClient):
    """Test upload of valid OGG audio."""
    ogg_bytes = generate_ogg_mock_bytes(2048)
    files = {"audio": ("recording.ogg", ogg_bytes, "audio/ogg")}
    data = {"duration": "22.0"}

    response = await client.post("/api/voice", files=files, data=data)
    assert response.status_code == 201
    assert response.json()["format"] == "ogg"


@pytest.mark.asyncio
async def test_upload_valid_mp3_mock(client: AsyncClient):
    """Test upload of valid MP3 audio."""
    mp3_bytes = generate_mp3_mock_bytes(4096)
    files = {"audio": ("recording.mp3", mp3_bytes, "audio/mpeg")}
    data = {"duration": "45.0"}

    response = await client.post("/api/voice", files=files, data=data)
    assert response.status_code == 201
    assert response.json()["format"] == "mp3"


@pytest.mark.asyncio
async def test_upload_missing_audio_payload(client: AsyncClient):
    """Test 400 when no audio file is provided in request."""
    response = await client.post("/api/voice", data={"duration": "10.0"})
    assert response.status_code == 400
    assert "no audio file" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_status_lifecycle_updates(client: AsyncClient):
    """Test updating upload status through pipeline states (received -> transcribing -> completed)."""
    from backend.app.services.audio_validator import AudioValidationResult
    import secrets

    test_token = secrets.token_hex(24)
    val = AudioValidationResult(
        token=test_token,
        detected_format="wav",
        mime_type="audio/wav",
        file_size_bytes=1024,
        duration_seconds=1.5,
        file_path="/storage/voice_notes/dummy.wav",
        filename="dummy.wav",
    )
    await VoiceService.record_upload(val)
    token = test_token

    # Initial state
    stat1 = await client.get(f"/api/voice/status/{token}")
    assert stat1.json()["status"] == "received"

    # Transition to transcribing
    await VoiceService.update_status(token, "transcribing")
    stat2 = await client.get(f"/api/voice/status/{token}")
    assert stat2.json()["status"] == "transcribing"

    # Transition to completed
    await VoiceService.update_status(token, "completed")
    stat3 = await client.get(f"/api/voice/status/{token}")
    assert stat3.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_root_serves_html_for_browser(client: AsyncClient):
    """Test GET / returns HTML landing page with voice studio when requested by a browser."""
    response = await client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "voice-studio" in response.text
    assert "Record or Upload Your Incident Voice Note" in response.text


@pytest.mark.asyncio
async def test_root_serves_json_for_api_client(client: AsyncClient):
    """Test GET / returns API metadata JSON when requested by API clients."""
    response = await client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "voice_api" in data


@pytest.mark.asyncio
async def test_static_css_and_js_served(client: AsyncClient):
    """Test styles.css and script.js are served with appropriate MIME types."""
    css_resp = await client.get("/styles.css")
    assert css_resp.status_code == 200
    assert "text/css" in css_resp.headers.get("content-type", "")
    assert "voice-studio" in css_resp.text

    js_resp = await client.get("/script.js")
    assert js_resp.status_code == 200
    assert "javascript" in js_resp.headers.get("content-type", "")
    assert "startRecording" in js_resp.text

