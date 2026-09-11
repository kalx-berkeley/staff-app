"""SurfacedSpinMatch model — records which Spinitron spins already triggered a DJ notification."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Integer

from app.database import Base


class SurfacedSpinMatch(Base):
    """One row per spin already surfaced to the DJ view as a feature-show match.

    Spinitron's "spins" endpoint returns the same spin repeatedly for as long
    as it stays within the lookback window SpinMatchService queries, so this
    table is what stops the same spin from popping up more than once —
    independent of how many times it's re-fetched or how many DJ tabs poll
    the matches endpoint. Rows older than SpinMatchService's prune window are
    deleted opportunistically since a spin that old can never be fetched
    again anyway.
    """

    __tablename__ = "surfaced_spin_matches"

    spin_id = Column(BigInteger, primary_key=True)
    show_id = Column(Integer, nullable=False)
    surfaced_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
