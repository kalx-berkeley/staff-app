"""SpinitronSpinCache model — singleton cache of recently fetched Spinitron spins."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON

from app.database import Base


class SpinitronSpinCache(Base):
    """Singleton row (id=1) holding the last Spinitron "spins" API response.

    Refetched by SpinMatchService whenever `fetched_at` is older than its
    cache TTL, so repeated frontend polling doesn't hammer the Spinitron API.
    """

    __tablename__ = "spinitron_spin_cache"

    id = Column(Integer, primary_key=True)
    fetched_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    spins = Column(JSON, nullable=False)
