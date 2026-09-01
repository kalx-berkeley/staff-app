"""ImpersonationSession model — staging-only user impersonation state."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class ImpersonationSession(Base):
    """Stores active impersonation state for a promotions user in staging."""

    __tablename__ = "impersonation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    real_email = Column(String, nullable=False, index=True)
    impersonated_email = Column(String, nullable=True)
    impersonate_dj_network = Column(Boolean, nullable=False, default=False)
    impersonate_station_office_network = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
