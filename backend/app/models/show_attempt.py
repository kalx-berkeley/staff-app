"""ShowAttempt model — records failed pass giveaway attempts per show."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import object_session, relationship
from app.database import Base
from app.models.credit import credit_label


class ShowAttempt(Base):
    """Records each failed on-air giveaway attempt for a show."""

    __tablename__ = "show_attempts"

    id = Column(Integer, primary_key=True, index=True)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False)
    # The old typed DJ name, until phase 4 of the Spinitron identity plan
    dj_name = Column(String, nullable=False)
    # Who was on air: the persona, the show, or both (see Pass)
    persona_id = Column(Integer, nullable=True)
    specialty_show_id = Column(Integer, ForeignKey("specialty_shows.id"), nullable=True)
    attempted_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    show = relationship("Show", back_populates="attempts")

    @property
    def credited_name(self) -> str:
        """Who was on air, by current name (see `credit`)."""
        return credit_label(
            object_session(self), self.persona_id, self.specialty_show_id, self.dj_name
        )
