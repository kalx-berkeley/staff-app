"""LotteryEntry model."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class LotteryEntry(Base):
    """Tracks a staff member or DJ's lottery entry for a show during the lottery window."""

    __tablename__ = "lottery_entries"

    id = Column(Integer, primary_key=True, index=True)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False, index=True)
    # 'staff' for staff pass entries, 'dj' for on-air pair entries
    entry_type = Column(String, nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True, index=True)
    dj_name = Column(String, nullable=True)
    specialty_show_id = Column(Integer, ForeignKey("specialty_shows.id"), nullable=True)
    assignment_date = Column(Date, nullable=True)
    has_guest = Column(Boolean, nullable=False, default=False, server_default="false")
    guest_name = Column(String, nullable=True)
    only_attend_with_guest = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # 'pending', 'won', 'lost'
    status = Column(String, nullable=False, default="pending", server_default="pending")
    entered_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    show = relationship("Show", back_populates="lottery_entries")
    staff = relationship("Staff", foreign_keys=[staff_id])
    specialty_show = relationship("SpecialtyShow", foreign_keys=[specialty_show_id])

    @property
    def staff_name(self) -> str | None:
        return self.staff.name if self.staff else None
