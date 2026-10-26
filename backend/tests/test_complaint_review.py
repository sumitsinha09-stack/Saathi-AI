from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.models import Complaint
from backend.app.schemas.incident import Incident
from backend.app.services.complaint_service import ComplaintService, _in_memory_complaints, _in_memory_complaint_tokens


@pytest.fixture
def sample_incident():
    return Incident(
        incident_type="Unauthorized Debit / UPI Fraud",
        summary="Victim reported Rs 25,000 debited after fake electricity bill call.",
        description="I received a call threatening disconnection if I didn't pay. Rs 25,000 was debited from SBI account.",
        language="hi",
        reported_entity="State Bank of India",
        incident_date="2026-10-26",
        financial_loss=25000.0,
        currency="INR",
        phone_number="+919876543210",
        suspected_scam=True,
        evidence_description="UPI Transaction ID 482910284719",
        is_fallback=False,
        extraction_method="structured",
    )


@pytest.fixture
def sample_incomplete_incident():
    return Incident(
        incident_type=None,
        summary="Money missing from bank account.",
        description="I noticed money was gone from my account yesterday.",
        language="en",
        reported_entity=None,
        incident_date=None,
        financial_loss=None,
        currency=None,
        phone_number=None,
        suspected_scam=None,
        evidence_description=None,
        is_fallback=False,
        extraction_method="structured",
    )


@pytest.mark.asyncio
async def test_get_complaint_by_token(sample_incident):
    """Verifies GET /api/complaints/{token} returns structured fields, native transcript, and missing list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create complaint in service
        upload_tok = "tok_review_get_001"
        created = await ComplaintService.create_complaint(
            incident=sample_incident,
            upload_token=upload_tok,
            db=None,
        )
        access_tok = created["access_token"]
        ref_num = created["reference_number"]

        # Retrieve by raw access_token
        resp = await client.get(f"/api/complaints/{access_tok}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["reference_number"] == ref_num
        assert data["status"] == "awaiting_review"
        assert data["processing_status"] == "completed"
        assert data["language"] == "hi"
        assert data["structured_fields"]["financial_loss"] == 25000.0
        assert data["structured_fields"]["currency"] == "INR"
        assert data["structured_fields"]["reported_entity"] == "State Bank of India"
        assert "token_hash" not in data
        assert "access_token" not in data
        assert isinstance(data["missing_fields"], list)

        # Retrieve by upload_token as well
        resp_upload = await client.get(f"/api/complaints/{upload_tok}")
        assert resp_upload.status_code == 200
        assert resp_upload.json()["reference_number"] == ref_num


@pytest.mark.asyncio
async def test_missing_fields_detection(sample_incomplete_incident):
    """Verifies that null/empty fields are detected and returned in missing_fields."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(
            incident=sample_incomplete_incident,
            upload_token="tok_incomplete_002",
            db=None,
        )
        access_tok = created["access_token"]

        resp = await client.get(f"/api/complaints/{access_tok}")
        assert resp.status_code == 200
        data = resp.json()

        missing = data["missing_fields"]
        assert "incident_type" in missing
        assert "reported_entity" in missing
        assert "incident_date" in missing
        assert "financial_loss" in missing
        assert "phone_number" in missing
        assert "suspected_scam" in missing
        assert "evidence_description" in missing
        # Summary & description are provided, so they must not be in missing
        assert "summary" not in missing
        assert "description" not in missing


@pytest.mark.asyncio
async def test_patch_complaint_edits_and_redaction(sample_incident):
    """Verifies PATCH /api/complaints/{token} updates permitted fields and redacts sensitive credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(
            incident=sample_incident,
            upload_token="tok_patch_003",
            db=None,
        )
        access_tok = created["access_token"]

        # Attempt to edit fields including sensitive OTP and payment card
        patch_payload = {
            "financial_loss": 35000.0,
            "reported_entity": "HDFC Bank",
            "summary": "Fraudster called asking for OTP 482910 to reverse charge",
            "description": "Caller said my card 4111222233334444 was blocked. I gave OTP: 482910.",
        }

        resp = await client.patch(f"/api/complaints/{access_tok}", json=patch_payload)
        assert resp.status_code == 200
        data = resp.json()

        # Check updated values
        assert data["structured_fields"]["financial_loss"] == 35000.0
        assert data["structured_fields"]["reported_entity"] == "HDFC Bank"

        # Check sensitive credentials were REDACTED
        summary = data["structured_fields"]["summary"]
        desc = data["structured_fields"]["description"]
        assert "482910" not in summary
        assert "[REDACTED]" in summary
        assert "4111222233334444" not in desc
        assert "[REDACTED]" in desc


@pytest.mark.asyncio
async def test_confirm_complaint_workflow(sample_incident):
    """Verifies POST /api/complaints/{token}/confirm finalizes complaint and is idempotent."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(
            incident=sample_incident,
            upload_token="tok_confirm_004",
            db=None,
        )
        access_tok = created["access_token"]
        ref_num = created["reference_number"]

        # 1. Confirm complaint
        confirm_resp = await client.post(
            f"/api/complaints/{access_tok}/confirm",
            json={"notes": "Victim verified and approved report."},
        )
        assert confirm_resp.status_code == 200
        confirm_data = confirm_resp.json()
        assert confirm_data["status"] == "confirmed"
        assert confirm_data["reference_number"] == ref_num
        assert confirm_data["confirmed_at"] is not None

        # Verify status is now confirmed in GET
        get_resp = await client.get(f"/api/complaints/{access_tok}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "confirmed"
        assert get_resp.json()["confirmed_at"] is not None

        # 2. Idempotency test: confirming again should succeed without creating duplicate events
        confirm_again = await client.post(
            f"/api/complaints/{access_tok}/confirm",
            json={"notes": "Duplicate confirmation attempt."},
        )
        assert confirm_again.status_code == 200
        assert confirm_again.json()["status"] == "confirmed"

        # 3. Edits rejected after confirmation
        patch_resp = await client.patch(
            f"/api/complaints/{access_tok}",
            json={"financial_loss": 99999.0},
        )
        assert patch_resp.status_code == 400
        assert "Cannot edit a complaint with status" in patch_resp.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_complaint_workflow(sample_incident):
    """Verifies POST /api/complaints/{token}/cancel transitions to cancelled and prevents confirmation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(
            incident=sample_incident,
            upload_token="tok_cancel_005",
            db=None,
        )
        access_tok = created["access_token"]

        # Cancel complaint
        cancel_resp = await client.post(
            f"/api/complaints/{access_tok}/cancel",
            json={"reason": "Resolved directly with bank."},
        )
        assert cancel_resp.status_code == 200
        cancel_data = cancel_resp.json()
        assert cancel_data["status"] == "cancelled"
        assert cancel_data["cancelled_at"] is not None

        # Verify status in GET
        get_resp = await client.get(f"/api/complaints/{access_tok}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "cancelled"

        # Attempt to confirm cancelled complaint must be rejected
        confirm_resp = await client.post(
            f"/api/complaints/{access_tok}/confirm",
            json={},
        )
        assert confirm_resp.status_code == 400
        assert "Cannot confirm a cancelled complaint" in confirm_resp.json()["detail"]

        # Attempt to edit cancelled complaint must be rejected
        patch_resp = await client.patch(
            f"/api/complaints/{access_tok}",
            json={"financial_loss": 1000.0},
        )
        assert patch_resp.status_code == 400
        assert "Cannot edit a complaint with status" in patch_resp.json()["detail"]


@pytest.mark.asyncio
async def test_review_html_page_route():
    """Verifies GET /c/{token} serves the frontend review HTML page."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/c/test-token-12345")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Review & Confirm Complaint" in resp.text
        assert "Structured Complaint Fields" in resp.text
