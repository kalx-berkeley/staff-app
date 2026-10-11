"""WorkformPreferences model — per-user KALX Workforms email settings."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, UniqueConstraint
from app.database import Base


class WorkformPreferences(Base):
    """Which KALX Workforms emails a staff member gets. No row means both."""

    __tablename__ = "workform_preferences"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    # Reminders to submit this month's workform
    reminder_emails_enabled = Column(Boolean, nullable=False, default=True)
    # Department heads: the "submissions to review" email
    review_emails_enabled = Column(Boolean, nullable=False, default=True)
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
        UniqueConstraint("staff_id", name="uq_workform_preferences_staff_id"),
    )
