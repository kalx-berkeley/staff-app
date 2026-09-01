"""OnAirWinner model — records on-air pass winners for venue win-frequency tracking."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class OnAirWinner(Base):
    """Tracks each on-air pass winner, enabling per-venue win-frequency limits."""

    __tablename__ = "on_air_winners"

    id = Column(Integer, primary_key=True, index=True)
    pass_id = Column(Integer, ForeignKey("passes.id"), nullable=False, unique=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False)
    recipient_name = Column(String, nullable=False)
    recipient_phone = Column(String, nullable=False)
    recipient_email = Column(String, nullable=True)
    given_away_by_dj = Column(String, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    pass_ref = relationship("Pass", back_populates="on_air_winner")
    venue = relationship("Venue", back_populates="on_air_winners")
    show = relationship("Show", back_populates="on_air_winners")
