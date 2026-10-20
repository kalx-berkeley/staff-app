"""SpecialtyShow model — on-air DJ specialty shows that can receive pre-assigned passes."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, DateTime, and_
from sqlalchemy.orm import relationship
from app.database import Base


class SpecialtyShow(Base):
    """A named specialty show (on-air DJ shift) that can be pre-assigned pass pairs."""

    __tablename__ = "specialty_shows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
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
        return [d.dj_name for d in self.djs]
