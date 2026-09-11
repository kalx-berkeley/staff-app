"""SpinitronShow model — cached upcoming on-air schedule from Spinitron."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class SpinitronShow(Base):
    """A cached Spinitron show entry, with its first persona resolved to a DJ name."""

    __tablename__ = "spinitron_shows"

    id = Column(Integer, primary_key=True)  # Spinitron's own show id
    start = Column(DateTime(timezone=True), nullable=False, index=True)
    end = Column(DateTime(timezone=True), nullable=False, index=True)
    dj_name = Column(String, nullable=True)
    persona_id = Column(Integer, nullable=True)
    fetched_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
