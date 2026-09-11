"""FeatureBinRelease model — current snapshot of KALX's music "feature bin"."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class FeatureBinRelease(Base):
    """One release currently in the feature bin, synced nightly from a Google Sheet.

    The table is fully replaced on each sync (see FeatureBinService.sync_feature_bin)
    since the sheet itself is a current snapshot, not an append-only log.
    """

    __tablename__ = "feature_bin_releases"

    id = Column(Integer, primary_key=True, index=True)
    added_date = Column(String, nullable=True)  # "MM/DD" as given by the sheet
    artist = Column(String, nullable=False, index=True)
    album = Column(String, nullable=False)
    label = Column(String, nullable=True)
    released_year = Column(String, nullable=True)  # "Rel'd" column
    dot = Column(String, nullable=True)  # "RED", "YLW", "GRN", "G2R"
    media = Column(String, nullable=True)  # "CD", "LP", "7IN"
    reviewer = Column(String, nullable=True)  # "Rev'r" column
    sheet_status = Column(String, nullable=True)  # "Status" column
    media_url = Column(String, nullable=True)  # Bandcamp or YouTube link
    fetched_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
