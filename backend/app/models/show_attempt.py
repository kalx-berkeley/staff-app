"""ShowAttempt model — records failed pass giveaway attempts per show."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class ShowAttempt(Base):
    """Records each failed on-air giveaway attempt for a show."""

    __tablename__ = "show_attempts"

    id = Column(Integer, primary_key=True, index=True)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False)
    dj_name = Column(String, nullable=False)
    attempted_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    show = relationship("Show", back_populates="attempts")
