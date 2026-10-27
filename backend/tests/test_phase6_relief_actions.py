import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.app.schemas.incident import Incident
from backend.app.services.complaint_service import ComplaintService


@pytest.fixture
def sample_incident() -> Incident:
    return Incident(
        incident_type="Unauthorized Debit / UPI Fraud",
        summary="Victim received a call asking for OTP and ₹25,000 was debited.",
        description="Caller posed as SBI manager stating KYC was expired. Money debited immediately.",
        language="en",
        reported_entity="State Bank of India",
        incident_date="2026-10-25 14:30",
        financial_loss=25000.0,
        currency="INR",
        phone_number="+919876543210",
        suspected_scam=True,
        evidence_description="UPI Ref 429384920384, SMS from VM-SBIINB",
        is_fallback=False,
    )


@pytest.mark.asyncio
async def test_actions_locked_until_confirmed(sample_incident):
    """
    Ensure all post-confirmation reporting actions are strictly locked (HTTP 403)
    while the complaint is awaiting review.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create complaint
        created = await ComplaintService.create_complaint(sample_incident)
        token = created["access_token"]
        assert created["status"] == "awaiting_review"

        # Attempt to trigger actions before confirmation
        actions_to_test = ["notify_bank", "call_1930", "download_pdf", "copy_filing_guide", "fir_simulation", "view_status"]
        for act in actions_to_test:
            resp = await client.post(f"/api/complaints/{token}/actions/{act}", json={})
            assert resp.status_code == 403, f"Action {act} should be locked before confirmation"
            assert "locked until" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_pdf_download_locked_until_confirmed(sample_incident):
    """
    Ensure PDF download endpoint is locked (HTTP 403) before confirmation.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(sample_incident)
        token = created["access_token"]

        resp = await client.get(f"/api/complaints/{token}/pdf")
        assert resp.status_code == 403
        assert "locked until" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cancelled_complaint_ineligible_for_actions(sample_incident):
    """
    Ensure cancelled complaints are permanently barred (HTTP 403) from relief actions.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(sample_incident)
        token = created["access_token"]

        # Cancel complaint
        cancel_resp = await client.post(f"/api/complaints/{token}/cancel", json={"reason": "Cancelled by user."})
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

        # Action attempt
        act_resp = await client.post(f"/api/complaints/{token}/actions/notify_bank", json={})
        assert act_resp.status_code == 403
        assert "ineligible" in act_resp.json()["detail"] or "Cancelled" in act_resp.json()["detail"]

        # PDF attempt
        pdf_resp = await client.get(f"/api/complaints/{token}/pdf")
        assert pdf_resp.status_code == 403


@pytest.mark.asyncio
async def test_invalid_action_rejected(sample_incident):
    """
    Ensure unknown or unapproved action strings return HTTP 400 Bad Request.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(sample_incident)
        token = created["access_token"]
        await ComplaintService.confirm_complaint_by_token(token)

        resp = await client.post(f"/api/complaints/{token}/actions/hack_system", json={})
        assert resp.status_code == 400
        assert "Unsupported action" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_all_six_actions_recorded_after_confirmation(sample_incident):
    """
    Confirm complaint and execute all six authorized Phase 6 relief actions.
    Verify each action is recorded with proper metadata, reference number, and timestamp.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(sample_incident)
        token = created["access_token"]
        ref = created["reference_number"]

        # Confirm complaint
        conf_resp = await client.post(f"/api/complaints/{token}/confirm", json={})
        assert conf_resp.status_code == 200
        assert conf_resp.json()["status"] == "confirmed"

        # 1. notify_bank
        r1 = await client.post(f"/api/complaints/{token}/actions/notify_bank", json={"metadata": {"channel": "email"}})
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["success"] is True
        assert d1["reference_number"] == ref
        assert d1["action"] == "notify_bank"
        assert "recorded_at" in d1

        # 2. call_1930
        r2 = await client.post(f"/api/complaints/{token}/actions/call_1930", json={})
        assert r2.status_code == 200
        assert r2.json()["action"] == "call_1930"

        # 3. download_pdf (via action endpoint)
        r3 = await client.post(f"/api/complaints/{token}/actions/download_pdf", json={})
        assert r3.status_code == 200
        assert r3.json()["action"] == "download_pdf"

        # 4. copy_filing_guide
        r4 = await client.post(f"/api/complaints/{token}/actions/copy_filing_guide", json={})
        assert r4.status_code == 200
        assert r4.json()["action"] == "copy_filing_guide"

        # 5. fir_simulation (explicit demo mode)
        r5 = await client.post(f"/api/complaints/{token}/actions/fir_simulation", json={})
        assert r5.status_code == 200
        assert r5.json()["action"] == "fir_simulation"

        # 6. view_status
        r6 = await client.post(f"/api/complaints/{token}/actions/view_status", json={})
        assert r6.status_code == 200
        assert r6.json()["action"] == "view_status"

        # Retrieve audit history and verify recorded action events
        hist_resp = await client.get(f"/api/complaints/{token}/history")
        assert hist_resp.status_code == 200
        history = hist_resp.json()

        actions_in_hist = [h.get("action_type") for h in history if h.get("action_type")]
        for expected in ["notify_bank", "call_1930", "download_pdf", "copy_filing_guide", "fir_simulation", "view_status"]:
            assert expected in actions_in_hist

        # Verify demo classification for fir_simulation
        demo_events = [h for h in history if h.get("is_demo") is True]
        assert len(demo_events) >= 1
        for dev in demo_events:
            assert dev["action_type"] == "fir_simulation"
            assert "Demo" in dev["note"] or "simulation" in dev["note"]


@pytest.mark.asyncio
async def test_pdf_download_endpoint_success(sample_incident):
    """
    Ensure GET /api/complaints/{token}/pdf generates a valid PDF with correct
    MIME type and Content-Disposition header.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(sample_incident)
        token = created["access_token"]
        ref = created["reference_number"]

        await client.post(f"/api/complaints/{token}/confirm", json={})

        pdf_resp = await client.get(f"/api/complaints/{token}/pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert f"{ref}-complaint.pdf" in pdf_resp.headers["content-disposition"]
        assert pdf_resp.content.startswith(b"%PDF")
        assert len(pdf_resp.content) > 1000


@pytest.mark.asyncio
async def test_public_helpline_lookup_privacy_and_data(sample_incident):
    """
    Verify /api/complaints/public-lookup/{reference_number}:
    - Returns minimal public status for valid reference
    - Strictly hides private narratives, financial loss numbers, phone numbers, and tokens
    - Formats timeline and marks demo events
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await ComplaintService.create_complaint(sample_incident)
        token = created["access_token"]
        ref = created["reference_number"]

        await client.post(f"/api/complaints/{token}/confirm", json={})
        await client.post(f"/api/complaints/{token}/actions/fir_simulation", json={})

        lookup_resp = await client.get(f"/api/complaints/public-lookup/{ref}")
        assert lookup_resp.status_code == 200
        data = lookup_resp.json()

        # Permitted fields
        assert data["reference_number"] == ref
        assert data["status"] == "confirmed"
        assert "created_at" in data
        assert "confirmed_at" in data
        assert "timeline" in data
        assert "relief_guidance" in data

        # STRICT PRIVACY: Forbidden fields must NOT be present!
        assert "summary" not in data
        assert "description" not in data
        assert "original_transcript" not in data
        assert "financial_loss" not in data
        assert "phone_number" not in data
        assert "reported_entity" not in data
        assert "access_token" not in data
        assert "token_hash" not in data

        # Check demo events in public timeline
        timeline = data["timeline"]
        demo_items = [t for t in timeline if t.get("is_demo") is True]
        assert len(demo_items) > 0


@pytest.mark.asyncio
async def test_public_helpline_lookup_invalid_or_nonexistent():
    """
    Verify public lookup returns generic 404 for invalid or nonexistent reference numbers.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid format
        r1 = await client.get("/api/complaints/public-lookup/INVALID-REF")
        assert r1.status_code == 404
        assert "Complaint not found or invalid reference number." in r1.json()["detail"]

        # Valid format but doesn't exist
        r2 = await client.get("/api/complaints/public-lookup/SAI-ZZ9999")
        assert r2.status_code == 404
        assert "Complaint not found or invalid reference number." in r2.json()["detail"]


@pytest.mark.asyncio
async def test_helpline_page_serves_html():
    """
    Verify /helpline route serves HTML content.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/helpline")
        assert resp.status_code == 200
        assert "Track Complaint Status" in resp.text
        assert "SAI-" in resp.text
