import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.app.schemas.incident import Incident
from backend.app.services.complaint_service import ComplaintService
from backend.app.services.portal_auto_filer import PortalAutoFiler


@pytest.fixture
def sample_incident() -> Incident:
    return Incident(
        incident_type="Bank Impersonation",
        summary="Caller posed as bank officer Rajesh Sharma and induced transfer of ₹15,000.",
        description="Victim was called by an imposter demanding OTP to unlock debit card.",
        language="en",
        reported_entity="Apex Union Bank",
        incident_date="2026-10-27",
        financial_loss=15000.0,
        currency="INR",
        phone_number="+919876543210",
        suspected_scam=True,
        evidence_description="Call records and UPI transaction SMS",
        is_fallback=False,
    )


@pytest.mark.asyncio
async def test_auto_file_locked_when_unconfirmed(sample_incident):
    """Verifies that auto-filing is strictly forbidden before complaint is confirmed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(sample_incident)
        token = created["access_token"]
        assert created["status"] == "awaiting_review"

        resp = await client.post(f"/api/complaints/{token}/auto-file/start", json={})
        assert resp.status_code == 403
        assert "locked until" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auto_file_lifecycle_e2e(sample_incident, monkeypatch):
    """Tests the full assisted filing lifecycle: start, poll, submit auth, and verify ack."""
    async def mock_run_session(session, citizen_name=None, citizen_email=None, citizen_state=None):
        session.stage = "AWAITING_CITIZEN_AUTH"
        session.captcha_expected = "ABC12"
        session.generated_otp = "123456"
        session.status_message = "Form pre-filled. Awaiting citizen CAPTCHA and SMS OTP authorization..."
        session.captcha_image_base64 = PortalAutoFiler._generate_captcha_svg_base64("ABC12")
        session.add_log("MHA Portal Security Gate reached: CAPTCHA and SMS OTP required.")
        await session._auth_event.wait()
        session.stage = "COMPLETED"
        ack = f"CFCFRMS/2026/{session.session_id[-6:].upper()}"
        session.official_ack_number = ack
        await PortalAutoFiler._persist_official_ack(session.complaint_ref, ack)

    monkeypatch.setattr(PortalAutoFiler, "_execute_assisted_filing", mock_run_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create and confirm complaint
        created = await ComplaintService.create_complaint(sample_incident)
        token = created["access_token"]
        ref = created["reference_number"]

        confirmed = await ComplaintService.confirm_complaint_by_token(token)
        assert confirmed["status"] == "confirmed"

        # 2. Start auto-file session
        start_resp = await client.post(
            f"/api/complaints/{token}/auto-file/start",
            json={"citizen_name": "Test Citizen", "citizen_email": "test@example.com"}
        )
        assert start_resp.status_code == 200
        start_data = start_resp.json()
        session_id = start_data["session_id"]
        assert session_id.startswith("filing_")
        assert start_data["complaint_ref"] == ref

        import asyncio
        await asyncio.sleep(0.01)

        # 4. Poll status
        status_resp = await client.get(
            f"/api/complaints/{token}/auto-file/status?session_id={session_id}"
        )
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["stage"] == "AWAITING_CITIZEN_AUTH"
        assert status_data["has_captcha"] is True

        # 5. Invalid CAPTCHA should be rejected
        bad_auth = await client.post(
            f"/api/complaints/{token}/auto-file/submit-auth",
            json={"session_id": session_id, "captcha": "WRONG", "otp": "123456"}
        )
        assert bad_auth.status_code == 400
        assert "captcha" in bad_auth.json()["detail"].lower()

        # 6. Correct CAPTCHA & OTP
        good_auth = await client.post(
            f"/api/complaints/{token}/auto-file/submit-auth",
            json={"session_id": session_id, "captcha": "ABC12", "otp": "123456"}
        )
        assert good_auth.status_code == 200
        assert good_auth.json()["status"] == "authenticated"

        import asyncio
        await asyncio.sleep(0.05)

        # 7. Verify session transition to COMPLETED and official Ack generated
        final_status = await client.get(
            f"/api/complaints/{token}/auto-file/status?session_id={session_id}"
        )
        assert final_status.status_code == 200
        assert final_status.json()["stage"] == "COMPLETED"
        assert final_status.json()["official_ack_number"].startswith("CFCFRMS/2026/")
