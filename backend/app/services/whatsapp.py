import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.config import settings
from backend.app.models import ProcessedMessage

logger = logging.getLogger(__name__)

ACKNOWLEDGMENT_TEXT = (
    "Thank you for contacting Samaran. We have received your message. "
    "Our system will help you prepare your cybercrime report in the next step."
)


def verify_signature(payload_bytes: bytes, signature_header: Optional[str], app_secret: str) -> bool:
    """
    Validates Meta's X-Hub-Signature-256 header using HMAC-SHA256 and app_secret.
    Uses timing-safe comparison to prevent timing attacks.
    """
    if not app_secret:
        logger.warning("WHATSAPP_APP_SECRET is not configured. Webhook signature check will fail.")
        return False

    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header.")
        return False

    if not signature_header.startswith("sha256="):
        logger.warning("Invalid X-Hub-Signature-256 format. Expected 'sha256=...'")
        return False

    expected_signature = "sha256=" + hmac.new(
        key=app_secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


class WhatsAppService:
    """
    Service client for interacting with Meta's official WhatsApp Cloud API.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        api_version: Optional[str] = None,
        base_url: str = "https://graph.facebook.com",
    ):
        self.access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.api_version = api_version or settings.WHATSAPP_API_VERSION
        self.base_url = base_url.rstrip("/")

    @property
    def messages_endpoint(self) -> str:
        return f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages"

    async def send_acknowledgment(
        self,
        recipient_id: str,
        reply_to_message_id: str,
        session_factory: Optional[Any] = None,
    ) -> bool:
        """
        Sends standard acknowledgment message to the sender via WhatsApp Cloud API.
        Never logs access tokens or sensitive recipient details.
        """
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_id,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": ACKNOWLEDGMENT_TEXT,
            },
            "context": {
                "message_id": reply_to_message_id,
            },
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        success = False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.messages_endpoint,
                    json=payload,
                    headers=headers,
                )

                if response.status_code in (200, 201):
                    logger.info(
                        "WhatsApp acknowledgment dispatched successfully. "
                        f"Recipient: ...{recipient_id[-4:] if len(recipient_id) >= 4 else '****'}, "
                        f"Reply-To: {reply_to_message_id}"
                    )
                    success = True
                else:
                    logger.error(
                        f"WhatsApp Cloud API error (HTTP {response.status_code}): {response.text}"
                    )
        except httpx.TimeoutException:
            logger.error("Timeout occurred while contacting Meta WhatsApp Cloud API.")
        except httpx.RequestError as exc:
            logger.error(f"Network error while connecting to Meta WhatsApp Cloud API: {exc}")
        except Exception as exc:
            logger.error(f"Unexpected error sending WhatsApp acknowledgment: {exc}")

        # Update database status if session_factory is provided
        if session_factory:
            try:
                async with session_factory() as session:
                    stmt = select(ProcessedMessage).where(ProcessedMessage.message_id == reply_to_message_id)
                    result = await session.execute(stmt)
                    msg_record = result.scalar_one_or_none()
                    if msg_record:
                        msg_record.status = "acknowledged" if success else "failed"
                        if success:
                            msg_record.acknowledged_at = datetime.now(timezone.utc)
                        await session.commit()
            except Exception as db_exc:
                logger.error(f"Failed to update acknowledgment status in database: {db_exc}")

        return success


whatsapp_service = WhatsAppService()
