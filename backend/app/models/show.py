"""Show model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Time,
    Boolean,
    ForeignKey,
    DateTime,
    JSON,
    false,
    text,
)
from sqlalchemy.orm import relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.promoter import Promoter


class Show(Base):
    """Show model representing music events with allocated passes."""

    __tablename__ = "shows"

    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String, nullable=False)
    genre = Column(JSON, nullable=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    promoter_id = Column(Integer, ForeignKey("promoters.id"), nullable=True)
    show_date = Column(Date, nullable=False)
    show_time = Column(Time, nullable=True)
    show_start_date = Column(Date, nullable=True)
    on_air_description = Column(String, nullable=True)
    caller_special_instructions = Column(String, nullable=True)
    age_restriction = Column(String, nullable=False)  # "all_ages", "18+", "21+"
    wheelchair_accessible = Column(Boolean, nullable=False)
    num_pass_pairs = Column(Integer, nullable=False)
    status = Column(
        String, nullable=False, default="draft"
    )  # "draft", "published", "closed", "deleted"
    planned_close_date = Column(Date, nullable=True)
    planned_close_time = Column(Time, nullable=True)
    auto_close = Column(Boolean, nullable=False, default=False, server_default=false())
    co_announce = Column(Boolean, nullable=False, default=False, server_default=false())
    lottery_enabled = Column(Boolean, nullable=False, default=False, server_default=false())
    lottery_window_hours = Column(
        Integer, nullable=False, default=24, server_default=text("24")
    )
    dj_preassign_prohibition_days = Column(Integer, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
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
    venue = relationship("Venue", back_populates="shows")
    promoter = relationship("Promoter", foreign_keys=[promoter_id])
    passes = relationship("Pass", back_populates="show", cascade="all, delete-orphan")
    on_air_winners = relationship("OnAirWinner", back_populates="show")
    attempts = relationship(
        "ShowAttempt", back_populates="show", cascade="all, delete-orphan"
    )
    bands = relationship(
        "ShowBand",
        back_populates="show",
        cascade="all, delete-orphan",
        order_by="ShowBand.start_pos",
    )
    lottery_entries = relationship(
        "LotteryEntry", back_populates="show", cascade="all, delete-orphan"
    )

    @property
    def effective_promoter(self) -> "Promoter | None":
        """Return the promoter responsible for this show: show-level override → venue default → None."""
        return self.promoter or (self.venue.promoter if self.venue else None)
