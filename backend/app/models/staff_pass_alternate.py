"""StaffPassAlternate model."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import relationship
from app.database import Base


class StaffPassAlternate(Base):
    """
    A staff member's place in a show's staff-pass alternate queue.

    Waiting entries are ordered by ``priority_at`` (ties broken by ``id``). When a
    staff pass frees up, the first eligible waiting entry is promoted to a real
    claim. Position in the queue is computed, never stored.
    """

    __tablename__ = "staff_pass_alternates"

    id = Column(Integer, primary_key=True, index=True)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False, index=True)
    has_guest = Column(Boolean, nullable=False, default=False, server_default="false")
    guest_name = Column(String, nullable=True)
    only_attend_with_guest = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Ordering key: join time, lottery entered_at, or original claimed_at for a
    # claim cut by a pass-count reduction.
    priority_at = Column(DateTime(timezone=True), nullable=False)
    # 'joined', 'lottery', 'capacity_cut'
    source = Column(String, nullable=False, default="joined", server_default="joined")
    # 'waiting', 'promoted', 'left', 'removed', 'expired', 'cancelled'
    status = Column(String, nullable=False, default="waiting", server_default="waiting")
    promoted_pass_id = Column(Integer, ForeignKey("passes.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    removed_by_staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
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

    __table_args__ = (
        Index(
            "uq_staff_pass_alternates_waiting",
            "show_id",
            "staff_id",
            unique=True,
            sqlite_where=text("status = 'waiting'"),
            postgresql_where=text("status = 'waiting'"),
        ),
    )

    show = relationship("Show", back_populates="alternates")
    staff = relationship("Staff", foreign_keys=[staff_id])
    removed_by = relationship("Staff", foreign_keys=[removed_by_staff_id])

    @property
    def staff_name(self) -> str | None:
        return self.staff.name if self.staff else None

    @property
    def show_event_name(self) -> str | None:
        return self.show.event_name if self.show else None

    @property
    def show_date(self):
        return self.show.show_date if self.show else None

    @property
    def show_venue_name(self) -> str | None:
        return self.show.venue.name if self.show and self.show.venue else None
