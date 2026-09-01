"""NotificationPreferences model."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from app.database import Base


class NotificationPreferences(Base):
    """Per-user notification preferences."""

    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    email_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("staff_id", name="uq_notification_preferences_staff_id"),
    )
