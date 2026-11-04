"""Show model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo
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
    from app.models.venue import Venue


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
    # Shows at music venues have an age restriction ("all_ages", "18+", "21+")
    # and shows at movie theaters a movie rating ("G", "PG", "PG-13", "R",
    # "NC-17", "NR"); the other is null
    age_restriction = Column(String, nullable=True)
    movie_rating = Column(String, nullable=True)
    wheelchair_accessible = Column(String, nullable=False)  # "yes", "no", "unknown"
    num_pass_pairs = Column(Integer, nullable=False)
    # Staff passes above (positive) or below (negative) the usual one per pair
    staff_pass_adjustment = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    status = Column(
        String, nullable=False, default="draft"
    )  # "draft", "published", "closed", "deleted"
    planned_close_date = Column(Date, nullable=True)
    planned_close_time = Column(Time, nullable=True)
    auto_close = Column(Boolean, nullable=False, default=False, server_default=false())
    # True from a close whose outcome emails were held until they're sent, the
    # show is reopened or it's deleted. See promoted_by.hold_close_notifications.
    close_notifications_held = Column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    close_notifications_sent_at = Column(DateTime(timezone=True), nullable=True)
    close_notifications_sent_by = Column(String, nullable=True)
    reopened_at = Column(DateTime(timezone=True), nullable=True)
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
    alternates = relationship(
        "StaffPassAlternate", back_populates="show", cascade="all, delete-orphan"
    )

    @property
    def num_staff_passes(self) -> int:
        """Total staff passes for this show: one per pair plus the adjustment."""
        return self.num_pass_pairs + (self.staff_pass_adjustment or 0)

    @property
    def promoted_by(self) -> "Promoter | Venue":
        """The show's own promoter or, when it has none, the venue.

        Its KALX promotions reps own the show, and its guest list settings
        apply. The venue's default promoter only pre-fills a new show's
        promoter, so it plays no part here.
        """
        return self.promoter or self.venue

    @property
    def close_notifications_pending(self) -> bool:
        """Whether held close emails can still be sent.

        They stop being useful once the show date has passed, so they're dropped.
        """
        today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
        return (
            self.status == "closed"
            and self.close_notifications_held
            and self.show_date >= today
        )
