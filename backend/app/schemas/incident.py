from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Incident(BaseModel):
    """
    Validated incident data model extracted from user complaint transcripts.
    Strictly grounded in reported facts without hallucinated or assumed values.
    """
    incident_type: Optional[str] = Field(
        default=None,
        description="Category of the complaint if explicitly supported by transcript, otherwise null"
    )
    summary: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="A concise summary of the reported incident"
    )
    description: str = Field(
        ...,
        min_length=5,
        description="A detailed account of what the user reported"
    )
    language: str = Field(
        ...,
        min_length=2,
        max_length=16,
        description="The original language of the transcript"
    )
    reported_entity: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Bank, company, organization, or person mentioned, otherwise null"
    )
    incident_date: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Date of the incident, otherwise null if not explicitly stated"
    )
    financial_loss: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Reported financial loss, otherwise null if not stated"
    )
    currency: Optional[str] = Field(
        default=None,
        max_length=16,
        description="Currency associated with the reported loss, otherwise null"
    )
    phone_number: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Phone number mentioned, otherwise null"
    )
    suspected_scam: Optional[bool] = Field(
        default=None,
        description="Whether the transcript explicitly supports a suspected scam, otherwise null"
    )
    evidence_description: Optional[str] = Field(
        default=None,
        description="Description of any evidence mentioned, otherwise null"
    )
    is_fallback: bool = Field(
        default=False,
        description="Whether this incident was generated via deterministic fallback summary"
    )
    extraction_method: str = Field(
        default="structured",
        description="Method used for extraction: 'structured' or 'fallback_summary'"
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
            try:
                return float(clean_str)
            except ValueError:
                return None
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
        return None
