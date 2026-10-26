from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.complaint_update import ComplaintUpdateRequest
from backend.app.services.complaint_service import ComplaintService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/complaints", tags=["Complaints & Incident Management"])


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
    "/{token}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve complaint review details by token or reference number",
    description=(
        "Retrieves the complaint review state, English summary, native voice transcript, "
        "structured fields, and missing-field indicators. When querying by reference number "
        "(SAI-XXXXXX), Authorization Bearer token or ?token= is strictly required."
    ),
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
