"""DjQuizDeadline model — when each year's DJ Quiz is due (Staff Directory)."""

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Integer

from app.database import Base


class DjQuizDeadline(Base):
    """
    The deadline for one year's DJ Quiz, set by site admins in KALX Staff Admin.

    The deadline is the last day (Pacific time) to complete that year's quiz.
    Until it passes, the previous year's quiz still counts for the Sublist DJ
    requirements.
    """

    __tablename__ = "dj_quiz_deadlines"

    year = Column(Integer, primary_key=True, autoincrement=False)
    deadline = Column(Date, nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
