import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from backend.app.models import Complaint, ComplaintStatusHistory
from backend.app.schemas.incident import Incident
from backend.app.services.complaint_service import ComplaintService
from backend.app.services.extraction_service import ExtractionService
from backend.app.services.redaction_service import RedactionService


# -----------------------------------------------------------------------------
# 1. Redaction Service Tests
# -----------------------------------------------------------------------------
class TestRedactionService:
    def test_redact_otp_patterns_hindi_english_tamil(self):
        # English
        t1 = "The scammer called and asked for my OTP is 482910."
        r1 = RedactionService.redact_text(t1)
        assert "482910" not in r1
        assert "[REDACTED]" in r1

        # Hindi
        t2 = "उसने बोला 6 अंकों का OTP 908123 बता दो।"
        r2 = RedactionService.redact_text(t2)
        assert "908123" not in r2
        assert "[REDACTED]" in r2

        # Tamil
        t3 = "எனது ஓடிபி 654321 ஐ கேட்டார்கள்."
        r3 = RedactionService.redact_text(t3)
        assert "654321" not in r3
        assert "[REDACTED]" in r3

    def test_redact_pin_cvv_password_and_card_numbers(self):
        sample = (
            "My ATM PIN was 4321 and UPI PIN was 987654. "
            "Card number was 4111 2222 3333 4444 with CVV 392. "
            "My password is MySecurePass123! and Aadhaar 2345 6789 0123."
        )
        redacted = RedactionService.redact_text(sample)
        assert "4321" not in redacted
        assert "987654" not in redacted
        assert "4111 2222 3333 4444" not in redacted
        assert "392" not in redacted
        assert "MySecurePass123!" not in redacted
        assert "2345 6789 0123" not in redacted
        assert "[REDACTED]" in redacted

    def test_preserve_non_sensitive_amounts_and_dates(self):
        sample = "On 24th October 2026, I lost 25,000 rupees from account ending in 100."
        redacted = RedactionService.redact_text(sample)
        assert "25,000" in redacted
        assert "24th October 2026" in redacted


# -----------------------------------------------------------------------------
# 2. Pydantic Incident Model Validation Tests
# -----------------------------------------------------------------------------
class TestIncidentSchemaValidation:
    def test_valid_incident_schema(self):
        data = {
            "incident_type": "Bank Fraud",
            "summary": "Fraud call impersonating bank manager.",
            "description": "Scammer claimed account would freeze and debited 10,000 rupees.",
            "language": "hi",
            "reported_entity": "Bharat Development Bank",
            "incident_date": "2026-10-25",
            "financial_loss": "10,000",
            "currency": "INR",
            "phone_number": "+91 9876543210",
            "suspected_scam": "true",
            "evidence_description": "SMS alert with UTR 48291048",
        }
        incident = Incident(**data)
        assert incident.incident_type == "Bank Fraud"
        assert incident.financial_loss == 10000.0
        assert incident.currency == "INR"
        assert incident.suspected_scam is True
        assert incident.is_fallback is False

    def test_missing_fields_default_to_none(self):
        data = {
            "summary": "Brief summary",
            "description": "Detailed description of incident without financial loss or entity.",
            "language": "en",
        }
        incident = Incident(**data)
        assert incident.incident_type is None
        assert incident.reported_entity is None
        assert incident.financial_loss is None
        assert incident.currency is None
        assert incident.phone_number is None
        assert incident.suspected_scam is None


# -----------------------------------------------------------------------------
# 3. Extraction Retry & Deterministic Fallback Tests
# -----------------------------------------------------------------------------
class TestExtractionServiceRetriesAndFallback:
    def test_retry_on_invalid_json_then_success(self):
        call_count = 0

        def mock_call_ollama(messages):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "This is not JSON at all."
            return json.dumps({
                "incident_type": "OTP Fraud",
                "summary": "Victim gave OTP and lost 5,000 rupees.",
                "description": "Scammer deceived victim into sharing OTP [REDACTED].",
                "language": "hi",
                "financial_loss": 5000.0,
                "currency": "INR",
                "suspected_scam": True,
            })

        with patch.object(ExtractionService, "_call_ollama", side_effect=mock_call_ollama):
            incident = ExtractionService.extract_incident("Fake transcript", language="hi", max_retries=3)
            assert call_count == 2
            assert incident.incident_type == "OTP Fraud"
            assert incident.financial_loss == 5000.0
            assert incident.is_fallback is False

    def test_fallback_summary_after_all_retries_fail(self):
        with patch.object(ExtractionService, "_call_ollama", return_value="Malformed JSON syntax {{{"):
            transcript = "मेरे बैंक खाते से 10,000 रुपये कट गए। उसने OTP 482910 मांगा था।"
            incident = ExtractionService.extract_incident(transcript, language="hi", max_retries=3)

            assert incident.is_fallback is True
            assert incident.extraction_method == "fallback_summary"
            assert incident.financial_loss == 10000.0
            assert incident.currency == "INR"
            assert incident.suspected_scam is True
            # Assert sensitive OTP was redacted even in fallback summary
            assert "482910" not in incident.description
            assert "482910" not in incident.summary


# -----------------------------------------------------------------------------
# 4. Reference Number, Cryptographic Tokens, and Database Storage Tests
# -----------------------------------------------------------------------------
class TestComplaintStorageAndTokens:
    def test_reference_number_format(self):
        for _ in range(50):
            ref = ComplaintService.generate_reference_number()
            assert ref.startswith("SAI-")
            assert len(ref) == 10  # 'SAI-' + 6 chars
            suffix = ref[4:]
            assert suffix.isupper() or suffix.isdigit()

    def test_token_generation_and_hashing(self):
        raw_token, token_hash = ComplaintService.generate_access_token()
        assert len(raw_token) >= 32
        assert len(token_hash) == 64
        # Verify hash match
        assert ComplaintService.hash_token(raw_token) == token_hash

    @pytest.mark.asyncio
    async def test_create_and_retrieve_complaint(self, test_db):
        incident = Incident(
            incident_type="Bank Fraud",
            summary="Fraud call claiming account suspension.",
            description="Scammer asked for OTP [REDACTED] and debited 15,000 INR.",
            language="hi",
            reported_entity="State Bank",
            financial_loss=15000.0,
            currency="INR",
            suspected_scam=True,
        )

        complaint_res = await ComplaintService.create_complaint(
            incident=incident,
            upload_token="test_voice_token_abc123",
            db=test_db,
        )

        assert complaint_res["reference_number"].startswith("SAI-")
        assert complaint_res["status"] in ("PENDING_REVIEW", "awaiting_review")
        assert complaint_res["financial_loss"] == 15000.0
        assert "access_token" in complaint_res

        raw_token = complaint_res["access_token"]
        ref = complaint_res["reference_number"]

        # Retrieve complaint with valid token
        retrieved = await ComplaintService.get_complaint(
            reference_number=ref,
            access_token=raw_token,
            db=test_db,
        )
        assert retrieved is not None
        assert retrieved["reference_number"] == ref

        # Attempt retrieval with wrong token
        wrong = await ComplaintService.get_complaint(
            reference_number=ref,
            access_token="invalid_token_999",
            db=test_db,
        )
        assert wrong is None

        # Check status history
        history = await ComplaintService.get_complaint_history(
            reference_number=ref,
            access_token=raw_token,
            db=test_db,
        )
        assert len(history) >= 1
        assert history[0]["status"] in ("PENDING_REVIEW", "awaiting_review")

    @pytest.mark.asyncio
    async def test_idempotency_prevents_duplicate_complaints(self, test_db):
        incident = Incident(
            incident_type="Lottery Scam",
            summary="Scam lottery prize notification.",
            description="Asked to deposit 5,000 INR processing fee.",
            language="ta",
            financial_loss=5000.0,
            currency="INR",
        )

        upload_token = "unique_voice_note_tok_777"

        first = await ComplaintService.create_complaint(
            incident=incident,
            upload_token=upload_token,
            db=test_db,
        )

        # Second creation with identical upload_token must return existing record
        second = await ComplaintService.create_complaint(
            incident=incident,
            upload_token=upload_token,
            db=test_db,
        )

        assert first["reference_number"] == second["reference_number"]


# -----------------------------------------------------------------------------
# 5. API Endpoints Integration Tests
# -----------------------------------------------------------------------------
class TestComplaintAPIEndpoints:
    @pytest.mark.asyncio
    async def test_complaint_api_flow(self, client: AsyncClient, test_db):
        incident = Incident(
            incident_type="KYC Phishing",
            summary="SMS threat of SIM deactivation.",
            description="Victim clicked APK link and lost 8,000 INR.",
            language="en",
            financial_loss=8000.0,
            currency="INR",
            suspected_scam=True,
        )

        record = await ComplaintService.create_complaint(
            incident=incident,
            upload_token="test_api_voice_token_456",
            db=test_db,
        )

        ref = record["reference_number"]
        token = record["access_token"]

        # 1. Unauthenticated request should fail (401)
        resp_unauth = await client.get(f"/api/complaints/{ref}")
        assert resp_unauth.status_code == 401

        # 2. Authenticated request with Bearer token
        resp_auth = await client.get(
            f"/api/complaints/{ref}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_auth.status_code == 200
        data = resp_auth.json()
        assert data["reference_number"] == ref
        assert data["incident_type"] == "KYC Phishing"
        assert "token_hash" not in data  # Token hash must never be leaked

        # 3. Retrieve history
        resp_hist = await client.get(
            f"/api/complaints/{ref}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_hist.status_code == 200
        hist_data = resp_hist.json()
        assert len(hist_data) >= 1
        assert hist_data[0]["status"] in ("PENDING_REVIEW", "awaiting_review")

        # 4. Confirm complaint review
        resp_confirm = await client.post(
            f"/api/complaints/{ref}/confirm?token={token}",
            json={"notes": "Confirmed by victim in Voice Studio."},
        )
        assert resp_confirm.status_code == 200
        confirmed_data = resp_confirm.json()
        assert confirmed_data["status"].lower() == "confirmed"
