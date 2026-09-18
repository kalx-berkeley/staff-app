"""DismissedSpinMatch model — records which spin/show matches a DJ has cleared."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Integer

from app.database import Base


class DismissedSpinMatch(Base):
    """One row per (spin, show) match a DJ has dismissed or clicked through.

    GET /api/dj/spin-matches returns every current spin/show match on every
    poll; this table is what lets the DJ view stop showing one once someone
    has acted on it, independent of how many tabs are open — each tab's next
    poll filters against the same rows. A spin matching two different shows
    produces two independent matches with their own rows here, so dismissing
    one leaves the other showing. Rows older than SpinMatchService's prune
    window are deleted opportunistically since a spin that old can never be
    fetched from Spinitron again anyway.
    """

    __tablename__ = "dismissed_spin_matches"

    spin_id = Column(BigInteger, primary_key=True)
    show_id = Column(Integer, primary_key=True)
    dismissed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
