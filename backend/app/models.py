from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func
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

