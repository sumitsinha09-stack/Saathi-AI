from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ComplaintUpdateRequest(BaseModel):
    """
    Schema for partial updates to editable complaint fields during review.
    Rejects unsupported fields or attempts to modify read-only system metadata.
    """
    incident_type: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Category of the complaint"
    )
    summary: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=500,
        description="Concise summary of the incident"
    )
    description: Optional[str] = Field(
        default=None,
        min_length=5,
        description="Detailed factual description"
    )
    reported_entity: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Bank, organization, or person mentioned"
    )
    incident_date: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Date of the incident"
    )
    financial_loss: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Reported financial loss amount"
    )
    currency: Optional[str] = Field(
        default=None,
        max_length=16,
        description="Currency associated with financial loss"
    )
    phone_number: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Suspect phone number"
    )
    suspected_scam: Optional[bool] = Field(
        default=None,
        description="Whether this incident is a suspected scam"
    )
    evidence_description: Optional[str] = Field(
        default=None,
        description="Description of evidence or transaction receipts"
    )

    @field_validator("financial_loss", mode="before")
    @classmethod
    def parse_financial_loss(cls, v):
        if v is None or v == "" or v == "null":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            clean_str = v.replace(",", "").replace("₹", "").replace("Rs", "").replace("INR", "").strip()
            if not clean_str:
                return None
            try:
                return float(clean_str)
            except ValueError:
                raise ValueError("financial_loss must be a numeric value")
        return None

    @field_validator("suspected_scam", mode="before")
    @classmethod
    def parse_suspected_scam(cls, v):
        if v is None or v == "" or v == "null":
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            low = v.lower().strip()
            if low in ("true", "yes", "1"):
                return True
            if low in ("false", "no", "0"):
                return False
            raise ValueError("suspected_scam must be a boolean (true/false) or null")
        return None
