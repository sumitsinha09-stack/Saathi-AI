import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from sqlalchemy import select

from backend.app.models import ProcessedMessage
from backend.app.services.whatsapp import ACKNOWLEDGMENT_TEXT, WhatsAppService


def generate_signature(body: bytes, secret: str = "test_secret_key_456") -> str:
    """Generate Meta X-Hub-Signature-256 for a raw payload."""
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_get_webhook_verification_success(client):
    """Test successful Meta webhook GET handshake."""
    response = await client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token_123",
            "hub.challenge": "challenge_code_999888",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge_code_999888"


@pytest.mark.asyncio
async def test_get_webhook_verification_incorrect_token(client):
    """Test GET verification failure with incorrect token."""
    response = await client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "challenge_code_999888",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Verification token mismatch"


@pytest.mark.asyncio
async def test_get_webhook_verification_missing_params(client):
    """Test GET verification failure when parameters are missing."""
    response = await client.get("/webhook")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_post_webhook_missing_or_invalid_signature(client):
    """Test POST webhook rejection with missing or invalid signature."""
    payload = json.dumps({"test": "data"}).encode("utf-8")

    # Missing signature
    resp1 = await client.post("/webhook", content=payload)
    assert resp1.status_code == 403

    # Invalid signature
    resp2 = await client.post(
        "/webhook",
        content=payload,
        headers={"X-Hub-Signature-256": "sha256=invalid_hex_signature"},
    )
    assert resp2.status_code == 403


@pytest.mark.asyncio
async def test_post_webhook_valid_text_message(client, test_db):
    """Test valid incoming text message payload triggers DB save and acknowledgment."""
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15550254444"},
                            "contacts": [{"wa_id": "919876543210"}],
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": "wamid.test_text_msg_001",
                                    "timestamp": "1730000000",
                                    "type": "text",
                                    "text": {"body": "My bank account was hacked"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    signature = generate_signature(raw_bytes)

    with patch("backend.app.routers.webhook.whatsapp_service.send_acknowledgment", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        response = await client.post(
            "/webhook",
            content=raw_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["processed"] == 1
        assert data["duplicates_ignored"] == 0

    # Verify message was stored in database
    stmt = select(ProcessedMessage).where(ProcessedMessage.message_id == "wamid.test_text_msg_001")
    result = await test_db.execute(stmt)
    msg = result.scalar_one_or_none()
    assert msg is not None
    assert msg.sender_id == "919876543210"
    assert msg.message_type == "text"


@pytest.mark.asyncio
async def test_post_webhook_valid_voice_message(client, test_db):
    """Test valid incoming voice/audio message is acknowledged without transcription."""
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "919123456789",
                                    "id": "wamid.test_audio_msg_002",
                                    "timestamp": "1730000001",
                                    "type": "audio",
                                    "audio": {
                                        "id": "media_id_audio_123",
                                        "mime_type": "audio/ogg; codecs=opus",
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    signature = generate_signature(raw_bytes)

    with patch("backend.app.routers.webhook.whatsapp_service.send_acknowledgment", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        response = await client.post(
            "/webhook",
            content=raw_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )
        assert response.status_code == 200
        assert response.json()["processed"] == 1

    # Verify voice message stored in database with type 'audio'
    stmt = select(ProcessedMessage).where(ProcessedMessage.message_id == "wamid.test_audio_msg_002")
    result = await test_db.execute(stmt)
    msg = result.scalar_one_or_none()
    assert msg is not None
    assert msg.message_type == "audio"


@pytest.mark.asyncio
async def test_post_webhook_status_update_only(client):
    """Test webhook ignores status updates (e.g., delivered/read receipts) without error."""
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": "wamid.msg_status_update",
                                    "status": "delivered",
                                    "timestamp": "1730000005",
                                    "recipient_id": "919876543210",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    signature = generate_signature(raw_bytes)

    response = await client.post(
        "/webhook",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["processed"] == 0


@pytest.mark.asyncio
async def test_post_webhook_malformed_json(client):
    """Test webhook gracefully handles malformed JSON."""
    raw_bytes = b"invalid_malformed_json_content{["
    signature = generate_signature(raw_bytes)

    response = await client.post(
        "/webhook",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Malformed JSON payload"


@pytest.mark.asyncio
async def test_post_webhook_duplicate_message_deduplication(client, test_db):
    """Test idempotent processing: duplicate message IDs are safely ignored."""
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": "wamid.unique_msg_dedup_003",
                                    "timestamp": "1730000010",
                                    "type": "text",
                                    "text": {"body": "First submission"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    signature = generate_signature(raw_bytes)

    with patch("backend.app.routers.webhook.whatsapp_service.send_acknowledgment", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        # First delivery
        resp1 = await client.post(
            "/webhook",
            content=raw_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )
        assert resp1.status_code == 200
        assert resp1.json()["processed"] == 1
        assert resp1.json()["duplicates_ignored"] == 0
        assert mock_send.call_count == 1

        # Second delivery (duplicate retry from Meta)
        resp2 = await client.post(
            "/webhook",
            content=raw_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["processed"] == 0
        assert resp2.json()["duplicates_ignored"] == 1
        # Crucial: Outbound send should NOT have been invoked a second time
        assert mock_send.call_count == 1


@pytest.mark.asyncio
async def test_whatsapp_service_send_acknowledgment_success():
    """Test WhatsAppService constructs payload and dispatches successfully."""
    service = WhatsAppService(
        access_token="fake_token",
        phone_number_id="12345678",
        api_version="v21.0",
        base_url="https://mock.graph.facebook.com",
    )

    async def mock_post(url, **kwargs):
        assert url == "https://mock.graph.facebook.com/v21.0/12345678/messages"
        json_data = kwargs.get("json", {})
        assert json_data["messaging_product"] == "whatsapp"
        assert json_data["to"] == "919999999999"
        assert json_data["text"]["body"] == "Saathi AI received your message: Hello"
        assert json_data["context"]["message_id"] == "wamid.inbound123"
        return httpx.Response(status_code=200, json={"messages": [{"id": "wamid.outbound456"}]})

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await service.send_acknowledgment(
            recipient_id="919999999999",
            reply_to_message_id="wamid.inbound123",
            incoming_text="Hello",
        )
        assert result is True


@pytest.mark.asyncio
async def test_whatsapp_service_failed_graph_api():
    """Test WhatsAppService handles Graph API error without raising unhandled exceptions."""
    service = WhatsAppService(
        access_token="invalid_token",
        phone_number_id="12345678",
        api_version="v21.0",
        base_url="https://mock.graph.facebook.com",
    )

    async def mock_post(url, **kwargs):
        return httpx.Response(
            status_code=401,
            json={"error": {"message": "Invalid OAuth access token", "type": "OAuthException"}},
        )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await service.send_acknowledgment(
            recipient_id="919999999999",
            reply_to_message_id="wamid.inbound123",
        )
        assert result is False


@pytest.mark.asyncio
async def test_health_check_endpoint(client):
    """Test GET /health endpoint reports service statuses."""
    response = await client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "backend" in data["services"]
