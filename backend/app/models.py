from datetime import datetime
from sqlalchemy import Column, DateTime, String, func
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
