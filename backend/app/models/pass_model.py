"""Pass model."""

from datetime import datetime, date, timezone
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
from app.models.guest_fallback import GuestFallback
from app.database import Base


class Pass(Base):
    """Pass model representing pass pairs for giveaway and staff passes."""

    __tablename__ = "passes"

    id = Column(Integer, primary_key=True, index=True)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False)
    pass_type = Column(String, nullable=False)  # "pair" or "staff"
    status = Column(
        String, nullable=False, default="available"
    )  # "available", "given_away", "claimed"

    # For pass pairs given away on-air — who gave it away and when
    given_away_by_dj = Column(String, nullable=True)
    given_away_at = Column(DateTime, nullable=True)

    # For staff passes claimed
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    claimed_at = Column(DateTime, nullable=True)

    # For pre-assigned pairs (promotions assignment)
    preassigned_dj = Column(String, nullable=True)
    preassigned_date = Column(Date, nullable=True)
    preassigned_by_staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    preassigned_specialty_show_id = Column(
        Integer, ForeignKey("specialty_shows.id"), nullable=True
    )

    # For staff passes claimed with a +1 guest
    has_guest = Column(Boolean, nullable=False, default=False, server_default="false")
    guest_name = Column(String, nullable=True)
    guest_fallback = Column(
        String,
        nullable=False,
        default=GuestFallback.ATTEND_ALONE,
        server_default=GuestFallback.ATTEND_ALONE,
    )
    # The guest has no pass and is on the alternate list. has_guest stays false
    # until they get a seat, because the guest list depends on it.
    guest_waiting = Column(Boolean, nullable=False, default=False, server_default="false")
    # Decides which guest gets a free pass first and which is bumped last: the claim
    # time, or when the guest was added if that was after claiming.
    guest_priority_at = Column(DateTime, nullable=True)
    # If this pass is a guest hold, points to the primary staff pass
    guest_of_pass_id = Column(Integer, ForeignKey("passes.id"), nullable=True)

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    show = relationship("Show", back_populates="passes")
    staff = relationship("Staff", foreign_keys=[staff_id], back_populates="claimed_passes")
    preassigned_by = relationship("Staff", foreign_keys=[preassigned_by_staff_id])
    preassigned_specialty_show = relationship(
        "SpecialtyShow", foreign_keys=[preassigned_specialty_show_id]
    )
    primary_pass = relationship(
        "Pass", foreign_keys=[guest_of_pass_id], remote_side="Pass.id"
    )
    on_air_winner = relationship(
        "OnAirWinner",
        back_populates="pass_ref",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Properties that proxy through on_air_winner for backward-compatible PassResponse
    @property
    def recipient_name(self):
        return self.on_air_winner.recipient_name if self.on_air_winner else None

    @property
    def recipient_phone(self):
        return self.on_air_winner.recipient_phone if self.on_air_winner else None

    @property
    def recipient_email(self):
        return self.on_air_winner.recipient_email if self.on_air_winner else None

    @property
    def staff_name(self):
        return self.staff.name if self.staff else None

    @property
    def staff_phone(self):
        return self.staff.phone if self.staff else None

    @property
    def staff_email(self):
        return self.staff.email if self.staff else None

    @property
    def guest_queue_key(self) -> tuple:
        """Sort key for this pass's guest among a show's waiting guests."""
        priority = self.guest_priority_at or self.claimed_at or datetime.min
        if priority.tzinfo is None:
            priority = priority.replace(tzinfo=timezone.utc)
        return (priority, self.id or 0)

    @property
    def guest_position(self) -> int | None:
        """This pass's guest's place among the show's waiting guests, from 1."""
        if not self.guest_waiting or self.show is None:
            return None
        ahead = [
            p
            for p in self.show.passes
            if p.guest_waiting
            and p.status == "claimed"
            and p.guest_queue_key < self.guest_queue_key
        ]
        return len(ahead) + 1

    def _claimant_leave_covering_show(self):
        """The claimant, if this is their own staff pass and they're on leave for the show."""
        from app.common.services.leave_service import leave_covers_show

        if self.staff is None or self.show is None or self.guest_of_pass_id is not None:
            return None
        return self.staff if leave_covers_show(self.staff, self.show) else None

    @property
    def staff_loa_start(self):
        staff = self._claimant_leave_covering_show()
        return staff.loa_start if staff else None

    @property
    def staff_loa_end(self):
        staff = self._claimant_leave_covering_show()
        return staff.loa_end if staff else None

    @property
    def staff_on_leave(self):
        return self._claimant_leave_covering_show() is not None

    @property
    def show_event_name(self):
        return self.show.event_name if self.show else None

    @property
    def show_date(self):
        return self.show.show_date if self.show else None

    @property
    def show_venue_name(self):
        return self.show.venue.name if self.show and self.show.venue else None

    @property
    def show_status(self):
        return self.show.status if self.show else None

    @property
    def preassigned_specialty_show_name(self):
        return (
            self.preassigned_specialty_show.name
            if self.preassigned_specialty_show
            else None
        )
