import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.services.translation_service import TranslationService
from backend.app.services.voice_service import VoiceService


class TestTranslationServiceUnit:
    """
    Unit tests for TranslationService (Hindi, Tamil, English passthrough).
    """

    def test_english_passthrough(self):
        english_text = (
            "Hello, this is the Cyber Security Fraud Investigation Desk of Metro Trust Bank. "
            "We detected an unauthorized debit card transaction of forty-five thousand rupees."
        )
        result = TranslationService.translate_transcript(english_text, source_language="en")
        assert result["is_already_english"] is True
        assert result["english_translation"] == english_text
        assert "unnecessary" in result["message"].lower()

    def test_hindi_translation(self):
        hindi_text = (
            "नमस्कार, आपके बचत खाते से अभी पच्चीस हज़ार रुपये का संदिग्ध यूपीआई भुगतान करने का प्रयास किया गया है।"
        )
        result = TranslationService.translate_transcript(hindi_text, source_language="hi")
        assert result["is_already_english"] is False
        assert len(result["english_translation"]) > 10
        # English translation should contain English letters
        assert any("a" <= c <= "z" or "A" <= c <= "Z" for c in result["english_translation"])
        # Should not contain untranslated Devanagari bulk
        assert sum(1 for c in result["english_translation"] if "\u0900" <= c <= "\u097f") < 5

    def test_tamil_translation(self):
        tamil_text = (
            "வணக்கம்! உங்கள் தொலைபேசி எண் தேர்ந்தெடுக்கப்பட்டு இருபத்தைந்து லட்சம் ரூபாய் பரிசு வென்றுள்ளது."
        )
        result = TranslationService.translate_transcript(tamil_text, source_language="ta")
        assert result["is_already_english"] is False
        assert len(result["english_translation"]) > 10
        # English translation should contain English letters
        assert any("a" <= c <= "z" or "A" <= c <= "Z" for c in result["english_translation"])


@pytest.mark.asyncio
class TestTranslationAPI:
    """
    API integration tests for POST /api/voice/translate.
    """

    async def test_translate_missing_or_invalid_token(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Non-existent token
            res = await client.post("/api/voice/translate", json={"token": "non_existent_token_12345"})
            assert res.status_code == 404
            data = res.json()
            assert "detail" in data
            assert "/Users/" not in data["detail"]

    async def test_translate_before_transcription_complete(self):
        # Register a pending/transcribing job in memory
        fake_token = "test_pending_token_abc"
        from backend.app.services.voice_service import _in_memory_uploads
        from datetime import datetime, timezone
        _in_memory_uploads[fake_token] = {
            "token": fake_token,
            "filename": "pending.wav",
            "file_path": "/tmp/test.wav",
            "file_size_bytes": 1024,
            "mime_type": "audio/wav",
            "format": "wav",
            "duration_seconds": 5.0,
            "status": "transcribing",
            "transcript": None,
            "english_translation": None,
            "language": None,
            "language_name": None,
            "language_probability": None,
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
            "expires_at": None,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/voice/translate", json={"token": fake_token})
            assert res.status_code == 400
            assert "not yet available" in res.json()["detail"].lower()

    async def test_translate_hindi_transcript_and_caching(self):
        fake_token = "test_hindi_complete_token_999"
        hindi_transcript = "नमस्कार, मेरे खाते से 35,000 रुपये धोखे से निकाल लिए गए हैं।"
        from backend.app.services.voice_service import _in_memory_uploads
        from datetime import datetime, timezone
        _in_memory_uploads[fake_token] = {
            "token": fake_token,
            "filename": "hindi_note.wav",
            "file_path": "/tmp/hindi_note.wav",
            "file_size_bytes": 2048,
            "mime_type": "audio/wav",
            "format": "wav",
            "duration_seconds": 6.0,
            "status": "completed",
            "transcript": hindi_transcript,
            "english_translation": None,
            "language": "hi",
            "language_name": "Hindi",
            "language_probability": 0.98,
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
            "expires_at": None,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First call: computes translation
            res1 = await client.post("/api/voice/translate", json={"token": fake_token})
            assert res1.status_code == 200
            data1 = res1.json()
            assert data1["token"] == fake_token
            assert data1["transcript"] == hindi_transcript
            assert data1["language"] == "hi"
            assert len(data1["english_translation"]) > 0
            assert data1["cached"] is False
            assert "35,000" in data1["english_translation"] or "35000" in data1["english_translation"]
            # No internal path leak
            assert "/Users/" not in str(data1)
            assert "/tmp/" not in str(data1)

            # Second call: returns cached translation immediately
            res2 = await client.post("/api/voice/translate", json={"token": fake_token})
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["cached"] is True
            assert data2["english_translation"] == data1["english_translation"]

            # GET status also reflects the English translation
            status_res = await client.get(f"/api/voice/status/{fake_token}")
            assert status_res.status_code == 200
            status_data = status_res.json()
            assert status_data["english_translation"] == data1["english_translation"]

    async def test_translate_english_speech_passthrough(self):
        fake_token = "test_english_complete_token_888"
        english_transcript = "Hello, this is Cyber Fraud unit. Do not share your OTP with anyone."
        from backend.app.services.voice_service import _in_memory_uploads
        from datetime import datetime, timezone
        _in_memory_uploads[fake_token] = {
            "token": fake_token,
            "filename": "english_note.wav",
            "file_path": "/tmp/english_note.wav",
            "file_size_bytes": 2048,
            "mime_type": "audio/wav",
            "format": "wav",
            "duration_seconds": 4.0,
            "status": "completed",
            "transcript": english_transcript,
            "english_translation": None,
            "language": "en",
            "language_name": "English",
            "language_probability": 0.99,
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
            "expires_at": None,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/voice/translate", json={"token": fake_token})
            assert res.status_code == 200
            data = res.json()
            assert data["is_already_english"] is True
            assert data["english_translation"] == english_transcript
            assert "already in english" in data["message"].lower()
