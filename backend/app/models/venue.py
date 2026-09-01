"""Venue model."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from app.database import Base


class Venue(Base):
    """Venue model representing music venues that provide passes."""

    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    address = Column(String, nullable=False)
    pass_call_instructions = Column(Text, nullable=True)
    win_frequency_days = Column(Integer, nullable=True)
    default_wheelchair_accessible = Column(Boolean, nullable=True)
    default_age_restriction = Column(String, nullable=True)
    default_num_pass_pairs = Column(Integer, nullable=True)
    logo_filename = Column(String, nullable=True)
    requires_phone_number = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    requires_email_address = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    staff_guest_requires_name = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    default_lottery_enabled = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    default_lottery_window_hours = Column(
        Integer, nullable=False, default=24, server_default=text("24")
    )
    default_dj_preassign_prohibition_days = Column(Integer, nullable=True)
    default_close_hours_before_show = Column(Integer, nullable=True)
    promoter_id = Column(Integer, ForeignKey("promoters.id"), nullable=True)
    shows_have_external_promoter = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deleted = Column(Boolean, nullable=False, default=False)
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
    promoter = relationship("Promoter", foreign_keys=[promoter_id])
    shows = relationship("Show", back_populates="venue")
    owners = relationship(
        "VenueOwner", back_populates="venue", cascade="all, delete-orphan"
    )
    contacts = relationship(
        "VenueContact", back_populates="venue", cascade="all, delete-orphan"
    )
    on_air_winners = relationship("OnAirWinner", back_populates="venue")

    @property
    def owner_emails(self) -> list[str]:
        return [o.promotions_staff_email for o in self.owners]
