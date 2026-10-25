import json
import os
import shutil
import tempfile
import pytest
from httpx import AsyncClient

from backend.app.config import settings
from backend.app.services.transcription_service import TranscriptionService
from backend.app.services.voice_service import VoiceService
from backend.app.routers.voice import process_voice_transcription

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data", "synthetic_scams")
MANIFEST_PATH = os.path.join(TEST_DATA_DIR, "manifest.json")


def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["samples"]


class TestSyntheticScamTranscription:
    """
    Evaluates Faster-Whisper local speech recognition against 5 synthetic scam voice note samples:
    1. Hindi Bank OTP Scam
    2. Hindi KYC Suspension Scam
    3. Tamil Lottery Prize Scam
    4. Tamil Account Freeze Scam
    5. English Customer Support PIN Request
    """

    def test_sample1_hindi_bank_otp(self):
        sample_path = os.path.join(TEST_DATA_DIR, "sample1_bank_otp_hindi.wav")
        assert os.path.isfile(sample_path), f"Sample file not found: {sample_path}"

        result = TranscriptionService.transcribe_audio(sample_path)
        assert result["language"] == "hi"
        assert result["language_name"] == "Hindi"
        assert result["language_probability"] > 0.8
        assert len(result["transcript"].strip()) > 10
        # Spoken language must NOT be translated into English (e.g., does not say 'Hello, I am...')
        assert "hello" not in result["transcript"].lower()
        # Non-English characters or native Hindustani script preserved
        assert any(ord(c) > 127 for c in result["transcript"])

    def test_sample2_hindi_kyc_suspension(self):
        sample_path = os.path.join(TEST_DATA_DIR, "sample2_kyc_suspension_hindi.wav")
        assert os.path.isfile(sample_path), f"Sample file not found: {sample_path}"

        result = TranscriptionService.transcribe_audio(sample_path)
        assert result["language"] == "hi"
        assert result["language_name"] == "Hindi"
        assert result["language_probability"] > 0.8
        assert len(result["transcript"].strip()) > 10
        assert "warning" not in result["transcript"].lower()
        assert any(ord(c) > 127 for c in result["transcript"])

    def test_sample3_tamil_lottery_prize(self):
        sample_path = os.path.join(TEST_DATA_DIR, "sample3_lottery_prize_tamil.wav")
        assert os.path.isfile(sample_path), f"Sample file not found: {sample_path}"

        result = TranscriptionService.transcribe_audio(sample_path)
        assert result["language"] == "ta"
        assert result["language_name"] == "Tamil"
        assert result["language_probability"] > 0.5
        assert len(result["transcript"].strip()) > 10
        # Spoken language must NOT be translated into English; Tamil script Unicode range: 0x0B80 - 0x0BFF
        assert any("\u0B80" <= char <= "\u0BFF" for char in result["transcript"]), (
            "Transcript should preserve native Tamil script"
        )

    def test_sample4_tamil_account_freeze(self):
        sample_path = os.path.join(TEST_DATA_DIR, "sample4_account_freeze_tamil.wav")
        assert os.path.isfile(sample_path), f"Sample file not found: {sample_path}"

        result = TranscriptionService.transcribe_audio(sample_path)
        assert result["language"] == "ta"
        assert result["language_name"] == "Tamil"
        assert result["language_probability"] > 0.5
        assert len(result["transcript"].strip()) > 10
        assert any("\u0B80" <= char <= "\u0BFF" for char in result["transcript"])

    def test_sample5_english_customer_support_pin(self):
        sample_path = os.path.join(TEST_DATA_DIR, "sample5_customer_support_pin_english.wav")
        assert os.path.isfile(sample_path), f"Sample file not found: {sample_path}"

        result = TranscriptionService.transcribe_audio(sample_path)
        assert result["language"] == "en"
        assert result["language_name"] == "English"
        assert result["language_probability"] > 0.8
        assert len(result["transcript"].strip()) > 10
        transcript_lower = result["transcript"].lower()
        assert any(kw in transcript_lower for kw in ["pin", "customer", "support", "card", "service", "transaction", "bank"])


class TestZeroRetentionCleanup:
    """
    Verifies that audio files saved during upload are strictly and immediately purged
    from the filesystem upon completion of background processing (both success and failure).
    """

    @pytest.mark.asyncio
    async def test_file_deleted_after_successful_transcription(self):
        # Create a temp copy of sample5 audio
        sample_path = os.path.join(TEST_DATA_DIR, "sample5_customer_support_pin_english.wav")
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "temp_voice_sample.wav")
        shutil.copyfile(sample_path, temp_file)
        assert os.path.exists(temp_file)

        # Pre-register upload in VoiceService
        from backend.app.services.audio_validator import AudioValidationResult
        import secrets

        token = secrets.token_hex(24)
        val = AudioValidationResult(
            token=token,
            detected_format="wav",
            mime_type="audio/wav",
            file_size_bytes=os.path.getsize(temp_file),
            duration_seconds=5.0,
            file_path=temp_file,
            filename="temp_voice_sample.wav",
        )
        await VoiceService.record_upload(val)

        # Run background transcription
        await process_voice_transcription(token, temp_file)

        # Verify file is deleted on disk (Zero-Retention Privacy Guarantee)
        assert not os.path.exists(temp_file), "Audio file must be purged from disk after transcription!"

        # Verify DB status updated to completed
        status_info = await VoiceService.get_status(token)
        assert status_info is not None
        assert status_info["status"] == "completed"
        assert status_info["transcript"] is not None
        assert status_info["language"] == "en"

        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_file_deleted_after_failed_transcription(self):
        # Create a corrupted non-audio file
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "corrupted.wav")
        with open(temp_file, "wb") as f:
            f.write(b"NOT_A_VALID_AUDIO_FILE_DATA_CORRUPT")
        assert os.path.exists(temp_file)

        from backend.app.services.audio_validator import AudioValidationResult
        import secrets

        token = secrets.token_hex(24)
        val = AudioValidationResult(
            token=token,
            detected_format="wav",
            mime_type="audio/wav",
            file_size_bytes=len(b"NOT_A_VALID_AUDIO_FILE_DATA_CORRUPT"),
            duration_seconds=1.0,
            file_path=temp_file,
            filename="corrupted.wav",
        )
        await VoiceService.record_upload(val)

        # Run background transcription on corrupted file
        await process_voice_transcription(token, temp_file)

        # Verify file is deleted on disk even on failure!
        assert not os.path.exists(temp_file), "Corrupted file must still be purged from disk on failure!"

        # Verify DB status is failed with sanitized message
        status_info = await VoiceService.get_status(token)
        assert status_info is not None
        assert status_info["status"] == "failed"
        assert status_info["error_message"] is not None
        assert "/Users/" not in status_info["error_message"]
        assert "traceback" not in status_info["error_message"].lower()

        shutil.rmtree(temp_dir, ignore_errors=True)


class TestTranscriptionAPIIntegration:
    """
    Tests end-to-end integration via the HTTP API.
    """

    @pytest.mark.asyncio
    async def test_end_to_end_upload_and_poll_status(self, client: AsyncClient):
        sample_path = os.path.join(TEST_DATA_DIR, "sample1_bank_otp_hindi.wav")
        with open(sample_path, "rb") as f:
            audio_bytes = f.read()

        files = {"audio": ("sample1_bank_otp_hindi.wav", audio_bytes, "audio/wav")}
        upload_resp = await client.post("/api/voice", files=files)
        assert upload_resp.status_code == 201

        token = upload_resp.json()["token"]
        assert token is not None

        # Fetch status
        status_resp = await client.get(f"/api/voice/status/{token}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["token"] == token
        assert data["status"] in ("received", "transcribing", "completed")

        # If completed, check transcript and language properties
        if data["status"] == "completed":
            assert data["language"] == "hi"
            assert data["language_name"] == "Hindi"
            assert data["transcript"] is not None
            assert len(data["transcript"]) > 0
            assert "file_path" not in data
