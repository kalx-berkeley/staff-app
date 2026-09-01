"""Pass model."""

from datetime import datetime, date, timezone
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
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
    only_attend_with_guest = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
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
