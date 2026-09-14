"""KalxLiveAppearance model — current snapshot of the KALX Live! calendar."""

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Integer, String

from app.database import Base


class KalxLiveAppearance(Base):
    """One band's KALX Live! appearance, synced nightly from a public Google Calendar.

    The table is fully replaced on each sync (see
    KalxLiveService.sync_kalx_live) since the calendar itself is a current
    snapshot, not an append-only log.
    """

    __tablename__ = "kalx_live_appearances"

    id = Column(Integer, primary_key=True, index=True)
    band_name = Column(String, nullable=False, index=True)
    event_date = Column(Date, nullable=False)
    fetched_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
