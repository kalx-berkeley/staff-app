"""StaffGenrePreference model."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, JSON, DateTime, ForeignKey, UniqueConstraint
from app.database import Base


class StaffGenrePreference(Base):
    """Per-staff list of music genres they like, used to suggest DJs for pre-assignment."""

    __tablename__ = "staff_genre_preferences"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    genres = Column(JSON, nullable=False, default=list)
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
        UniqueConstraint("staff_id", name="uq_staff_genre_preferences_staff_id"),
    )
