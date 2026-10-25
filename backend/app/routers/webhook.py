import hmac
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.database import AsyncSessionLocal, get_db
from backend.app.models import ProcessedMessage
from backend.app.services.whatsapp import verify_signature, whatsapp_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["WhatsApp Webhook"])


@router.get("", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    """
    Meta Webhook Verification Handshake (GET /webhook).
    Verifies that the webhook request is genuinely from Meta using the configured verify token.
    """
    if not hub_mode or not hub_verify_token or hub_challenge is None:
        logger.warning("GET /webhook called with missing verification parameters.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required query parameters: hub.mode, hub.verify_token, hub.challenge",
        )

    if hub_mode != "subscribe":
        logger.warning(f"Unexpected hub.mode received: {hub_mode}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid hub.mode",
        )

    # Timing-safe token comparison against WHATSAPP_VERIFY_TOKEN
    if not hmac.compare_digest(hub_verify_token, settings.WHATSAPP_VERIFY_TOKEN):
        logger.warning("GET /webhook token mismatch.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification token mismatch",
        )

    logger.info("WhatsApp webhook verified successfully by Meta.")
    return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)


@router.post("")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
) -> Dict[str, Any]:
    """
    WhatsApp Event Receiver & Echo Bot (POST /webhook).
    - Verifies HMAC-SHA256 signature against META_APP_SECRET.
    - Idempotently processes incoming messages with PostgreSQL deduplication.
    - Queues 'Saathi AI received your message: <message>' echo reply asynchronously.
    - Promptly returns HTTP 200 OK to Meta.
    """
    raw_body = await request.body()
    app_secret = settings.effective_app_secret

    # 1. Validate X-Hub-Signature-256 if app secret is configured
    if app_secret:
        if not verify_signature(raw_body, x_hub_signature_256, app_secret):
            logger.warning("Rejected POST /webhook: Invalid X-Hub-Signature-256 header.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook signature",
            )
    else:
        logger.warning(
            "META_APP_SECRET not configured. Webhook running without signature verification."
        )

    # 2. Parse JSON payload safely
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        logger.error(f"Malformed JSON in webhook request: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload",
        )

    # 3. Inspect webhook structure for incoming messages
    entries = payload.get("entry", [])
    if not entries:
        return {"status": "ignored_no_entries"}

    processed_count = 0
    duplicate_count = 0

    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            # Ignore status update events (sent, delivered, read) without incoming messages
            if not messages:
                continue

            for msg in messages:
                message_id = msg.get("id")
                sender_id = msg.get("from")
                msg_type = msg.get("type", "unknown")
                timestamp = msg.get("timestamp")

                if not message_id or not sender_id:
                    continue

                # Extract text body if type is text
                incoming_text = None
                if msg_type == "text":
                    incoming_text = msg.get("text", {}).get("body", "")

                logger.info(
                    f"Received incoming WhatsApp message: id={message_id}, "
                    f"from=...{sender_id[-4:] if len(sender_id) >= 4 else '****'}, "
                    f"type={msg_type}, timestamp={timestamp}"
                )

                # 4. Idempotency Check with PostgreSQL
                stmt = select(ProcessedMessage).where(ProcessedMessage.message_id == message_id)
                result = await db.execute(stmt)
                existing_message = result.scalar_one_or_none()

                if existing_message:
                    logger.info(f"Duplicate message ignored: {message_id}")
                    duplicate_count += 1
                    continue

                # Store message_id in database atomically
                try:
                    record = ProcessedMessage(
                        message_id=message_id,
                        sender_id=sender_id,
                        message_type=msg_type,
                        status="received",
                    )
                    db.add(record)
                    await db.commit()
                except Exception as db_exc:
                    await db.rollback()
                    logger.error(f"Database error saving processed message {message_id}: {db_exc}")
                    continue

                # 5. Dispatch Echo Acknowledgment Asynchronously
                background_tasks.add_task(
                    whatsapp_service.send_acknowledgment,
                    recipient_id=sender_id,
                    reply_to_message_id=message_id,
                    incoming_text=incoming_text,
                    message_type=msg_type,
                    session_factory=AsyncSessionLocal,
                )
                processed_count += 1

    return {
        "status": "ok",
        "processed": processed_count,
        "duplicates_ignored": duplicate_count,
    }
