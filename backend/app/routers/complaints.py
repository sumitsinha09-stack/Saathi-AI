import time
from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.complaint_update import ComplaintUpdateRequest
from backend.app.services.complaint_service import ComplaintService
from backend.app.services.pdf_service import PDFService
from backend.app.services.rate_limiter import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/complaints", tags=["Complaints & Incident Management"])

# Rate limit tracking for public helpline lookups (IP -> timestamps)
_lookup_rate_limits: Dict[str, List[float]] = {}
LOOKUP_RATE_LIMIT_MAX = 10
LOOKUP_RATE_LIMIT_WINDOW = 60.0  # seconds


def check_lookup_rate_limit(client_ip: str) -> None:
    """Enforces rate limiting on unauthenticated public reference lookups."""
    now = time.time()
    if client_ip not in _lookup_rate_limits:
        _lookup_rate_limits[client_ip] = []
    _lookup_rate_limits[client_ip] = [ts for ts in _lookup_rate_limits[client_ip] if now - ts < LOOKUP_RATE_LIMIT_WINDOW]
    if len(_lookup_rate_limits[client_ip]) >= LOOKUP_RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Lookup rate limit exceeded. Please wait 60 seconds before querying again.",
        )
    _lookup_rate_limits[client_ip].append(now)


def extract_token_from_header_or_query(
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
) -> Optional[str]:
    """Helper to extract access token from Authorization: Bearer <token> or ?token=<token>."""
    if query_token and query_token.strip():
        return query_token.strip()
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return authorization.strip()
    return None


class ActionRequestPayload(BaseModel):
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional sanitized action context (never credentials)")


class ConfirmComplaintPayload(BaseModel):
    notes: Optional[str] = Field(None, max_length=500, description="Optional victim confirmation note or correction")
    token: Optional[str] = Field(None, description="Optional access token if not passed in header")
    incident_type: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    reported_entity: Optional[str] = None
    incident_date: Optional[str] = None
    financial_loss: Optional[float] = None
    currency: Optional[str] = None
    phone_number: Optional[str] = None
    suspected_scam: Optional[bool] = None
    evidence_description: Optional[str] = None


class CancelComplaintPayload(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Optional cancellation explanation")


@router.get(
    "/public-lookup/{reference_number}",
    status_code=status.HTTP_200_OK,
    summary="Public unauthenticated complaint status tracker (/helpline)",
    description=(
        "Retrieves minimal public status information for a given Saathi AI reference number. "
        "Strictly safeguards private victim narrative, loss details, and access credentials. "
        "Protected by client rate limiting."
    ),
    dependencies=[Depends(rate_limit("public_lookup", "RATE_LIMIT_PUBLIC_LOOKUP"))],
)
async def public_lookup_status(
    reference_number: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Public minimal status tracker for citizens and helpline inquiries.
    """
    res = await ComplaintService.get_public_helpline_status(reference_number, db=db)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or invalid reference number.",
        )
    return res


@router.get(
    "/{token}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve complaint review details by token or reference number",
    description=(
        "Retrieves the complaint review state, English summary, native voice transcript, "
        "structured fields, and missing-field indicators. When querying by reference number "
        "(SAI-XXXXXX), Authorization Bearer token or ?token= is strictly required."
    ),
    dependencies=[Depends(rate_limit("complaint_read", "RATE_LIMIT_COMPLAINT_READ"))],
)
async def get_complaint_by_token(
    token: str,
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns full complaint details for review:
    - Reference number and status (awaiting_review, confirmed, cancelled, failed, processing)
    - Processing status of background pipeline
    - English summary (generated locally if not already translated)
    - Original voice transcript in native script (Devanagari, Tamil, English)
    - Structured complaint fields and missing-information indicators
    - Timestamps (created_at, confirmed_at, cancelled_at)
    """
    clean_token = token.strip()
    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token cannot be empty.",
        )

    # If queried by reference number (SAI-XXXXXX), enforce authentication token
    if clean_token.upper().startswith("SAI-"):
        auth_token = extract_token_from_header_or_query(authorization=authorization, query_token=query_token)
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing access token. Please provide Authorization: Bearer <token> or ?token=<token>.",
            )
        # Verify access token matches reference number
        complaint = await ComplaintService.get_complaint(
            reference_number=clean_token.upper(),
            access_token=auth_token,
            db=db,
            require_token=True,
        )
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Complaint not found, token is invalid, or access period has expired.",
            )
        clean_token = auth_token

    detail = await ComplaintService.get_complaint_detail_by_token(token=clean_token, db=db)

    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or token is invalid.",
        )

    if detail.get("error") == "expired":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Complaint access token has expired.",
        )

    return detail


@router.patch(
    "/{token}",
    status_code=status.HTTP_200_OK,
    summary="Update editable complaint fields before confirmation",
    description=(
        "Accepts partial updates to permitted complaint fields. Validates input values, "
        "applies sensitive credential redaction (OTPs, PINs, card numbers), and rejects "
        "modifications if the complaint is already confirmed or cancelled."
    ),
    dependencies=[Depends(rate_limit("complaint_write", "RATE_LIMIT_COMPLAINT_WRITE"))],
)
async def update_complaint(
    token: str,
    payload: ComplaintUpdateRequest,
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Updates editable fields on an active complaint.
    Returns the updated complaint detail and refreshed missing fields.
    """
    clean_token = token.strip()
    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token cannot be empty.",
        )

    if clean_token.upper().startswith("SAI-"):
        auth_token = extract_token_from_header_or_query(authorization=authorization, query_token=query_token)
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing access token.",
            )
        clean_token = auth_token

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return await get_complaint_by_token(token=clean_token, db=db)

    try:
        updated = await ComplaintService.update_complaint_fields_by_token(
            token=clean_token,
            updates=updates,
            db=db,
        )
        return updated
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or token is invalid.",
        )
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(pe),
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"Error updating complaint for token {token}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update complaint fields.",
        )


@router.post(
    "/{token}/confirm",
    status_code=status.HTTP_200_OK,
    summary="Confirm and finalize complaint review",
    description=(
        "Atomically saves any final edits, transitions complaint status to 'confirmed', "
        "records the confirmation timestamp and audit status event, and unlocks reporting actions. "
        "Idempotent: duplicate requests return confirmed status without creating duplicate events."
    ),
    dependencies=[Depends(rate_limit("complaint_confirm", "RATE_LIMIT_COMPLAINT_CONFIRM"))],
)
async def confirm_complaint(
    token: str,
    payload: Optional[ConfirmComplaintPayload] = None,
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Confirms the complaint and unlocks reporting actions.
    Does NOT automatically submit to external organizations.
    """
    clean_token = token.strip()
    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token cannot be empty.",
        )

    if clean_token.upper().startswith("SAI-"):
        body_tok = payload.token if payload else None
        auth_token = extract_token_from_header_or_query(authorization=authorization, query_token=query_token or body_tok)
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing access token. Please provide Authorization: Bearer <token> or ?token=<token>.",
            )
        clean_token = auth_token

    final_updates = None
    note = None

    if payload:
        note = payload.notes
        data = payload.model_dump(exclude_unset=True)
        data.pop("notes", None)
        data.pop("token", None)
        if data:
            try:
                validated_model = ComplaintUpdateRequest(**data)
                final_updates = validated_model.model_dump(exclude_unset=True)
            except Exception as ve:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Validation failed for submitted edits: {ve}",
                )

    try:
        result = await ComplaintService.confirm_complaint_by_token(
            token=clean_token,
            final_updates=final_updates,
            note=note,
            db=db,
        )
        return result
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or token is invalid.",
        )
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(pe),
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"Error confirming complaint for token {token}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm complaint.",
        )


@router.post(
    "/{token}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel a complaint and close the review workflow",
    description=(
        "Transitions complaint status to 'cancelled', records cancelled_at timestamp, "
        "appends an audit event, and disables reporting actions. Cannot be undone."
    ),
    dependencies=[Depends(rate_limit("complaint_write", "RATE_LIMIT_COMPLAINT_WRITE"))],
)
async def cancel_complaint(
    token: str,
    payload: Optional[CancelComplaintPayload] = None,
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Cancels an active complaint.
    """
    clean_token = token.strip()
    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token cannot be empty.",
        )

    if clean_token.upper().startswith("SAI-"):
        auth_token = extract_token_from_header_or_query(authorization=authorization, query_token=query_token)
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing access token.",
            )
        clean_token = auth_token

    note = payload.reason if payload and payload.reason else "Complaint cancelled by victim."

    try:
        result = await ComplaintService.cancel_complaint_by_token(
            token=clean_token,
            note=note,
            db=db,
        )
        return result
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or token is invalid.",
        )
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(pe),
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"Error cancelling complaint for token {token}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel complaint.",
        )


@router.get(
    "/{token}/history",
    status_code=status.HTTP_200_OK,
    summary="Retrieve audit status history for a complaint",
    description="Retrieves chronological status events and timeline history for a complaint by token or reference number.",
    dependencies=[Depends(rate_limit("complaint_read", "RATE_LIMIT_COMPLAINT_READ"))],
)
async def get_complaint_history(
    token: str,
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Returns audit trail events for the given complaint.
    """
    clean_token = token.strip()
    if clean_token.upper().startswith("SAI-"):
        auth_token = extract_token_from_header_or_query(authorization=authorization, query_token=query_token)
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing access token.",
            )
        complaint = await ComplaintService.get_complaint(
            reference_number=clean_token.upper(),
            access_token=auth_token,
            db=db,
            require_token=True,
        )
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Complaint not found or token is invalid.",
            )
        clean_token = auth_token

    record, is_mem = await ComplaintService.find_complaint_record(clean_token, db=db)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or token is invalid.",
        )

    ref = getattr(record, "reference_number", None) if not is_mem else record.get("reference_number")
    history = await ComplaintService.get_complaint_history(
        reference_number=ref,
        access_token=clean_token,
        db=db,
    )

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint history not found.",
        )

    return history


@router.post(
    "/{token}/actions/{action}",
    status_code=status.HTTP_200_OK,
    summary="Record post-confirmation relief action",
    description=(
        "Records authorized post-confirmation actions: notify_bank, call_1930, download_pdf, "
        "copy_filing_guide, fir_simulation, view_status. "
        "Strictly locked until complaint is confirmed. Ineligible for cancelled complaints."
    ),
    dependencies=[Depends(rate_limit("complaint_action", "RATE_LIMIT_ACTIONS"))],
)
async def record_complaint_action(
    token: str,
    action: str,
    payload: Optional[ActionRequestPayload] = None,
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Executes and records authorized one-tap relief actions.
    Validates token and requires confirmed status.
    """
    clean_token = token.strip()
    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token cannot be empty.",
        )

    if clean_token.upper().startswith("SAI-"):
        auth_token = extract_token_from_header_or_query(authorization=authorization, query_token=query_token)
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing access token. Please provide Authorization: Bearer <token> or ?token=<token>.",
            )
        complaint = await ComplaintService.get_complaint(
            reference_number=clean_token.upper(),
            access_token=auth_token,
            db=db,
            require_token=True,
        )
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Complaint not found or token is invalid.",
            )
        clean_token = auth_token

    clean_action = action.strip().lower()
    meta = payload.metadata if payload else None

    try:
        result = await ComplaintService.record_action_by_token(
            token=clean_token,
            action=clean_action,
            metadata=meta,
            db=db,
        )
        return result
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or token is invalid.",
        )
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(pe),
        )
    except ValueError as ve:
        err_msg = str(ve)
        # Check if error is due to unconfirmed or cancelled status -> HTTP 403 Forbidden
        if "locked until" in err_msg or "ineligible" in err_msg or "cancelled" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error(f"Error recording action '{action}' for token {token}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record action event.",
        )


@router.get(
    "/{token}/pdf",
    status_code=status.HTTP_200_OK,
    summary="Download formal Complaint Summary PDF",
    description=(
        "Generates a professional, mobile-readable PDF document containing incident summary, "
        "factual particulars, original transcript, status timeline, and citizen disclaimer. "
        "Available only after complaint confirmation."
    ),
    dependencies=[Depends(rate_limit("complaint_read", "RATE_LIMIT_COMPLAINT_READ"))],
)
async def download_complaint_pdf(
    token: str,
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Generates and downloads the complaint PDF for confirmed complaints.
    Records the 'download_pdf' action upon successful generation.
    """
    clean_token = token.strip()
    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token cannot be empty.",
        )

    if clean_token.upper().startswith("SAI-"):
        auth_token = extract_token_from_header_or_query(authorization=authorization, query_token=query_token)
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing access token.",
            )
        complaint = await ComplaintService.get_complaint(
            reference_number=clean_token.upper(),
            access_token=auth_token,
            db=db,
            require_token=True,
        )
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Complaint not found or token is invalid.",
            )
        clean_token = auth_token

    detail = await ComplaintService.get_complaint_detail_by_token(token=clean_token, db=db)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or token is invalid.",
        )

    if detail.get("error") == "expired":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Complaint access token has expired.",
        )

    current_status = (detail.get("status") or "").lower()
    if current_status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cancelled complaints are ineligible for PDF generation.",
        )
    if current_status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"PDF download is locked until the complaint is confirmed. Current status: '{detail.get('status')}'.",
        )

    ref = detail.get("reference_number", "SAI-XXXXXX")

    # Retrieve history
    history = await ComplaintService.get_complaint_history(
        reference_number=ref,
        access_token=clean_token,
        db=db,
    )

    try:
        pdf_bytes = PDFService.generate_complaint_pdf(complaint=detail, history=history)
    except Exception as e:
        logger.error(f"Failed to generate PDF for complaint {ref}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate complaint PDF.",
        )

    # Record download_pdf action
    try:
        await ComplaintService.record_action_by_token(
            token=clean_token,
            action="download_pdf",
            db=db,
        )
    except Exception as act_err:
        logger.warning(f"Failed to record download_pdf action for {ref}: {act_err}")

    filename = f"{ref}-complaint.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )


# -------------------------------------------------------------------------
# Assisted Portal Auto-Filing Endpoints (Option A: Citizen-in-the-Loop RPA)
# -------------------------------------------------------------------------
from backend.app.services.portal_auto_filer import PortalAutoFiler


class AutoFileStartPayload(BaseModel):
    citizen_name: Optional[str] = Field(None, max_length=120)
    citizen_email: Optional[str] = Field(None, max_length=120)
    citizen_state: Optional[str] = Field(None, max_length=64)


class AutoFileAuthPayload(BaseModel):
    session_id: str = Field(..., min_length=1)
    captcha: str = Field(..., min_length=1, max_length=10)
    otp: str = Field(..., min_length=6, max_length=6)


@router.post(
    "/{token}/auto-file/start",
    status_code=status.HTTP_200_OK,
    summary="Start assisted robotic portal filing session",
    description="Launches automated form pre-filling on cybercrime.gov.in and pauses at the citizen CAPTCHA / OTP security checkpoint.",
    dependencies=[Depends(rate_limit("complaint_action", "RATE_LIMIT_ACTIONS"))],
)
async def start_portal_auto_file(
    token: str,
    payload: Optional[AutoFileStartPayload] = None,
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    clean_token = token.strip()
    if clean_token.upper().startswith("SAI-"):
        auth_token = extract_token_from_header_or_query(authorization=authorization, query_token=query_token)
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing access token. Please provide Authorization: Bearer <token> or ?token=<token>.",
            )
        complaint = await ComplaintService.get_complaint(
            reference_number=clean_token.upper(),
            access_token=auth_token,
            db=db,
            require_token=True,
        )
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Complaint not found or token is invalid.",
            )
        clean_token = auth_token

    detail = await ComplaintService.get_complaint_detail_by_token(token=clean_token, db=db)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or token is invalid.",
        )

    current_status = (detail.get("status") or "").lower()
    if current_status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cancelled complaints cannot be filed on the portal.",
        )
    if current_status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Filing is locked until complaint is confirmed. Current status: '{detail.get('status')}'.",
        )

    citizen_name = payload.citizen_name if payload else None
    citizen_email = payload.citizen_email if payload else None
    citizen_state = payload.citizen_state if payload else None

    session = await PortalAutoFiler.start_filing(
        complaint=detail,
        citizen_name=citizen_name,
        citizen_email=citizen_email,
        citizen_state=citizen_state,
    )

    # Record action in audit history
    try:
        await ComplaintService.record_action_by_token(
            token=clean_token,
            action="portal_auto_file",
            metadata={"session_id": session.session_id},
            db=db,
        )
    except Exception as e:
        logger.debug(f"Action record notice: {e}")

    return session.to_dict()


@router.get(
    "/{token}/auto-file/status",
    status_code=status.HTTP_200_OK,
    summary="Poll status of assisted portal filing session",
    description="Returns live progress, pre-filled fields, live CAPTCHA image, and official acknowledgement number.",
    dependencies=[Depends(rate_limit("complaint_read", "RATE_LIMIT_COMPLAINT_READ"))],
)
async def get_portal_auto_file_status(
    token: str,
    session_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    clean_token = token.strip()
    session = None
    if session_id:
        session = PortalAutoFiler.get_session(session_id)

    if not session:
        ref = clean_token.upper() if clean_token.upper().startswith("SAI-") else None
        if not ref:
            detail = await ComplaintService.get_complaint_detail_by_token(token=clean_token, db=db)
            if detail:
                ref = detail.get("reference_number")
        if ref:
            session = PortalAutoFiler.get_session_by_ref(ref)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active filing session found for this complaint.",
        )

    return session.to_dict()


@router.post(
    "/{token}/auto-file/submit-auth",
    status_code=status.HTTP_200_OK,
    summary="Submit citizen CAPTCHA and SMS OTP to finalize filing",
    description="Accepts citizen CAPTCHA solve and SMS OTP to submit pre-filled complaint and generate official government Ack Number.",
    dependencies=[Depends(rate_limit("complaint_action", "RATE_LIMIT_ACTIONS"))],
)
async def submit_portal_auth(
    token: str,
    payload: AutoFileAuthPayload,
    authorization: Optional[str] = Header(None),
    query_token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    try:
        result = await PortalAutoFiler.submit_auth(
            session_id=payload.session_id,
            captcha=payload.captcha,
            otp=payload.otp,
        )
        return result
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Filing session not found or expired.",
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )

