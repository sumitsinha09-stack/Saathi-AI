from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship
from backend.app.database import Base


class ProcessedMessage(Base):
    """
    Model for recording incoming WhatsApp messages.
    Uses message_id as primary key to guarantee database-level idempotency
    and prevent duplicate message processing across webhook retries.
    """
    __tablename__ = "processed_messages"

    message_id = Column(String(128), primary_key=True, index=True, nullable=False)
    sender_id = Column(String(64), index=True, nullable=False)
    message_type = Column(String(32), nullable=False, default="text")
    status = Column(String(32), nullable=False, default="received")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ProcessedMessage(message_id='{self.message_id}', sender='{self.sender_id}', type='{self.message_type}', status='{self.status}')>"


class VoiceUpload(Base):
    """
    Model for recording uploaded voice notes and audio recordings.
    Identified by a cryptographically secure, unpredictable token.
    Internal file_path is strictly isolated and never exposed in API responses.
    """
    __tablename__ = "voice_uploads"

    token = Column(String(64), primary_key=True, index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(64), nullable=False)
    format = Column(String(16), nullable=False)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String(32), nullable=False, default="received")
    transcript = Column(Text, nullable=True)
    english_translation = Column(Text, nullable=True)
    language = Column(String(16), nullable=True)
    language_name = Column(String(64), nullable=True)
    language_probability = Column(Float, nullable=True)
    error_message = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<VoiceUpload(token='{self.token}', format='{self.format}', size={self.file_size_bytes}, status='{self.status}')>"


class Complaint(Base):
    """
    Model for recording AI-extracted complaints.
    - Unique reference number format 'SAI-XXXXXX'.
    - Stored token_hash guarantees secure authorized access without exposing the raw token.
    - Linked to VoiceUpload by upload_token for end-to-end tracing and idempotency.
    - Sanitized credential fields with sensitive values redacted.
    """
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_number = Column(String(16), unique=True, index=True, nullable=False)
    token_hash = Column(String(64), index=True, nullable=False)
    upload_token = Column(String(64), index=True, nullable=True)
    status = Column(String(32), nullable=False, default="awaiting_review")
    incident_type = Column(String(64), nullable=True)
    summary = Column(Text, nullable=False)
    english_summary = Column(Text, nullable=True)
    description = Column(Text, nullable=False)
    language = Column(String(16), nullable=False)
    reported_entity = Column(String(128), nullable=True)
    incident_date = Column(String(64), nullable=True)
    financial_loss = Column(Float, nullable=True)
    currency = Column(String(16), nullable=True)
    phone_number = Column(String(32), nullable=True)
    suspected_scam = Column(Boolean, nullable=True)
    evidence_description = Column(Text, nullable=True)
    is_fallback = Column(Boolean, nullable=False, default=False)
    raw_transcript_redacted = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    history = relationship(
        "ComplaintStatusHistory",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintStatusHistory.created_at",
    )

    def __repr__(self) -> str:
        return f"<Complaint(ref='{self.reference_number}', status='{self.status}', loss={self.financial_loss} {self.currency})>"


class ComplaintStatusHistory(Base):
    """
    Audit trail event recording status changes and timeline for a complaint.
    """
    __tablename__ = "complaint_status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), index=True, nullable=False)
    status = Column(String(32), nullable=False)
    action_type = Column(String(32), nullable=True)  # e.g., notify_bank, call_1930, download_pdf, copy_filing_guide, fir_simulation, view_status
    is_demo = Column(Boolean, nullable=False, default=False)
    note = Column(Text, nullable=True)
    extra_data = Column(Text, nullable=True)  # Sanitized JSON metadata (never raw credentials)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    complaint = relationship("Complaint", back_populates="history")

    def __repr__(self) -> str:
        return f"<ComplaintStatusHistory(complaint_id={self.complaint_id}, status='{self.status}', action='{self.action_type}', demo={self.is_demo})>"


