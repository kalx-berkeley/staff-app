"""ExternalApiCache model — generic URL-keyed cache for third-party API responses."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.database import Base


class ExternalApiCache(Base):
    """Stores a JSON payload fetched from an external URL, with an expiry timestamp."""

    __tablename__ = "external_api_cache"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False, unique=True, index=True)
    payload = Column(JSON, nullable=False)
    fetched_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at = Column(DateTime, nullable=False, index=True)
