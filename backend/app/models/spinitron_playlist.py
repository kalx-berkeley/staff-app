"""SpinitronPlaylist model — cached Spinitron playlist entries (past + pre-provisioned future)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, false

from app.database import Base


class SpinitronPlaylist(Base):
    """A cached Spinitron playlist entry, with its first persona resolved to a DJ name."""

    __tablename__ = "spinitron_playlists"

    id = Column(Integer, primary_key=True)  # Spinitron's own playlist id
    start = Column(DateTime(timezone=True), nullable=False, index=True)
    end = Column(DateTime(timezone=True), nullable=False, index=True)
    dj_name = Column(String, nullable=True)
    persona_id = Column(Integer, nullable=True)
    # The Spinitron show the playlist belongs to, which tells a Specialty
    # Music Show or Talk & Info Show slot apart
    show_id = Column(Integer, nullable=True)
    title = Column(String, nullable=True)
    # Aired with no live DJ (e.g. a roboshow)
    automation = Column(Boolean, nullable=False, default=False, server_default=false())
    fetched_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
