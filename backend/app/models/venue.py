"""Venue model."""

import re
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from app.database import Base

_LEADING_THE = re.compile(r"^the\s+", re.IGNORECASE)


def venue_sort_key(name: str) -> tuple[str, str]:
    """Sort key for a venue name, ignoring case and a leading "The ".

    "The Fox Theater" sorts as "fox theater". The name itself breaks ties so
    the order is stable.
    """
    stripped = name.strip()
    return (_LEADING_THE.sub("", stripped).casefold(), stripped)


class Venue(Base):
    """Venue model representing music venues that provide passes."""

    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    address = Column(String, nullable=False)
    show_sourcing_instructions = Column(Text, nullable=True)
    pass_call_instructions = Column(Text, nullable=True)
    win_frequency_days = Column(Integer, nullable=True)
    # A venue that shares another venue's win frequency limit (for venues owned
    # by the same company). The parent's limit applies to the parent and all
    # its children; a child has no limit of its own. One level only.
    parent_venue_id = Column(Integer, ForeignKey("venues.id"), nullable=True)
    # "music" or "movie_theater". Shows at a movie theater have a movie rating
    # instead of an age restriction.
    venue_type = Column(String, nullable=False, default="music", server_default="music")
    # "yes", "no", "unknown", or null for no default
    default_wheelchair_accessible = Column(String, nullable=True)
    default_age_restriction = Column(String, nullable=True)
    default_movie_rating = Column(String, nullable=True)
    default_num_pass_pairs = Column(Integer, nullable=True)
    logo_filename = Column(String, nullable=True)
    # When the venue has a logo, the DJ view shows the logo in place of the
    # venue name unless this is set, in which case it shows both.
    show_name_with_logo = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    requires_phone_number = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Which winners' email addresses the guest list needs: "none", "staff_passes"
    # (staff claimants only, whose addresses we already have) or "all" (DJs
    # must also collect one from every on-air winner)
    email_address_requirement = Column(
        String, nullable=False, default="none", server_default="none"
    )
    staff_guest_requires_name = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Hold the emails telling staff and alternates the outcome when a show closes
    # until a promotions rep clicks the button on the show page
    hold_close_notifications = Column(
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
    default_on_air_description = Column(Text, nullable=True)
    default_caller_special_instructions = Column(Text, nullable=True)
    default_staff_instructions = Column(Text, nullable=True)
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
    parent = relationship("Venue", remote_side=[id], back_populates="children")
    children = relationship("Venue", back_populates="parent", order_by="Venue.name")

    @property
    def limit_venue(self) -> "Venue":
        """The venue whose win frequency limit applies: the parent, or itself."""
        return self.parent if self.parent is not None else self

    @property
    def effective_win_frequency_days(self) -> int | None:
        """The win frequency limit that applies to this venue's shows."""
        return self.limit_venue.win_frequency_days

    @property
    def family_venue_ids(self) -> list[int]:
        """The IDs of the venues sharing this venue's win frequency limit."""
        root = self.limit_venue
        return [root.id, *(c.id for c in root.children)]

    @property
    def sister_venue_names(self) -> list[str]:
        """The names of the other venues sharing this venue's limit, sorted."""
        root = self.limit_venue
        return sorted(
            (v.name for v in [root, *root.children] if v.id != self.id),
            key=venue_sort_key,
        )

    @property
    def requires_email_address(self) -> bool:
        """Whether DJs must collect an email address from on-air winners."""
        return self.email_address_requirement == "all"

    @property
    def includes_staff_email_address(self) -> bool:
        """Whether the guest list includes staff claimants' email addresses."""
        return self.email_address_requirement in ("staff_passes", "all")

    @property
    def owner_emails(self) -> list[str]:
        return [o.promotions_staff_email for o in self.owners]
