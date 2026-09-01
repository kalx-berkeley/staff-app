"""JobLog model — records each scheduled job execution."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base


class JobLog(Base):
    """Records each scheduled job run so the admin page can show when jobs last ran."""

    __tablename__ = "job_log"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, nullable=False, index=True)
    ran_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    trigger = Column(String, nullable=False)  # "manual" or "scheduled"
