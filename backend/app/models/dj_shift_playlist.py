"""DjShiftPlaylist model — aired Spinitron playlists, for the Sublist DJ shift check."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


class DjShiftPlaylist(Base):
    """
    One aired Spinitron playlist from the previous or current quarter.

    Stored by the directory's nightly "Sync DJ shifts from Spinitron" job and
    read when showing a profile's eligibility checklist. Separate from the pass
    giveaway's `spinitron_playlists` cache, which covers a different window.
    """

    __tablename__ = "dj_shift_playlists"

    id = Column(Integer, primary_key=True, autoincrement=False)  # Spinitron's playlist id
    persona_id = Column(Integer, nullable=True, index=True)
    show_id = Column(Integer, nullable=True)
    start = Column(DateTime(timezone=True), nullable=False, index=True)
    end = Column(DateTime(timezone=True), nullable=False)
    title = Column(String, nullable=True)
    # Spinitron's "automation" flag: the playlist aired with no live DJ (e.g. a roboshow)
    automation = Column(Boolean, nullable=False, default=False)
    fetched_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
