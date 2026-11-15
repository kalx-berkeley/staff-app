"""SpinitronPersona model — a local copy of Spinitron's persona directory."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class SpinitronPersona(Base):
    """
    One Spinitron persona (an on-air DJ name), refreshed nightly.

    Everything that shows a persona's name reads it from here, including
    personas no current staff member holds, so a renamed persona shows its new
    name everywhere. `last_playlist_at` is filled only for personas linked to
    a staff member, and lets pickers hide a staff member's personas that
    haven't been on air lately. See `app/common/services/spinitron_personas.py`.
    """

    __tablename__ = "spinitron_personas"

    # Spinitron's own persona ID
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    # When the persona's most recent aired playlist started, or null if it has
    # none (or isn't a staff member's, so it wasn't looked up)
    last_playlist_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
