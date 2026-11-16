"""SpecialtyShow model — Specialty Music Shows and Talk & Information shows.

Both kinds can receive pre-assigned passes. In the UI they're "Specialty Music
Shows" (category "music") and "Talk & Info Shows" (category "talk").
"""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, DateTime, and_
from sqlalchemy.orm import relationship
from app.database import Base

# The two kinds of specialty show
MUSIC = "music"
TALK = "talk"
CATEGORIES = (MUSIC, TALK)


def category_label(category: str) -> str:
    """The name people see for a kind of show, e.g. "Specialty Music Show"."""
    return "Talk & Info Show" if category == TALK else "Specialty Music Show"


class SpecialtyShow(Base):
    """
    A named show that can be pre-assigned pass pairs.

    A Specialty Music Show (category "music") has DJ members, by DJ name. A
    Talk & Information show (category "talk") has staff members instead
    (`TalkShowStaff`). Everything else is shared.
    """

    __tablename__ = "specialty_shows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    category = Column(String, nullable=False, default=MUSIC, server_default=MUSIC)
    # Deleted shows were mistakes: they're hidden everywhere, and their
    # Spinitron show IDs are ignored.
    deleted = Column(Boolean, nullable=False, default=False)
    # When the show was retired (it ran and ended), or null if it's current.
    # A retired show is kept, and its Spinitron show IDs still mark its
    # playlists as a specialty show, but the pass giveaway no longer offers it.
    retired_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    owners = relationship(
        "SpecialtyShowOwner", back_populates="specialty_show", cascade="all, delete-orphan"
    )
    djs = relationship(
        "SpecialtyShowDJ", back_populates="specialty_show", cascade="all, delete-orphan"
    )
    staff_members = relationship(
        "TalkShowStaff", back_populates="specialty_show", cascade="all, delete-orphan"
    )
    spinitron_show_rows = relationship(
        "SpecialtyShowSpinitronShow",
        back_populates="specialty_show",
        cascade="all, delete-orphan",
        order_by="SpecialtyShowSpinitronShow.id",
    )

    @property
    def spinitron_shows(self) -> list[dict]:
        return [
            {
                "id": row.spinitron_show_id,
                "title": row.title,
                "url": f"https://spinitron.com/KALX/show/{row.spinitron_show_id}/",
            }
            for row in self.spinitron_show_rows
        ]

    @property
    def retired(self) -> bool:
        return self.retired_at is not None

    @classmethod
    def current_filter(cls):
        """A query filter for shows the pass giveaway offers: not deleted or retired."""
        return and_(cls.deleted == False, cls.retired_at.is_(None))  # noqa: E712

    @property
    def owner_emails(self) -> list[str]:
        return [o.staff_email for o in self.owners if o.staff_email]

    @property
    def owner_details(self) -> list[dict]:
        return [
            {"email": o.staff_email, "name": o.staff.name if o.staff else None}
            for o in self.owners
            if o.staff_email
        ]

    @property
    def dj_names(self) -> list[str]:
        return [d.name for d in self.djs]

    @property
    def dj_persona_ids(self) -> set[int]:
        return {d.persona_id for d in self.djs if d.persona_id is not None}

    @property
    def is_talk(self) -> bool:
        return self.category == TALK

    @property
    def category_label(self) -> str:
        return category_label(self.category)

    @property
    def staff_member_emails(self) -> list[str]:
        return [m.staff_email for m in self.staff_members if m.staff_email]

    @property
    def staff_member_details(self) -> list[dict]:
        return [
            {"email": m.staff_email, "name": m.staff.name if m.staff else None}
            for m in self.staff_members
            if m.staff_email
        ]
