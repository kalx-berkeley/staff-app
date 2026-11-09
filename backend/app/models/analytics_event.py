"""Analytics tracking tables, read by KALX Staff Analytics."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)

from app.database import Base


class AnalyticsEvent(Base):
    """One tracked event: a visit, a session, a popup, a redirect and so on.

    Unlike the audit log, these are high-volume usage records rather than
    changes to the app's data. Some rows are updated after they're written:
    a giveaway page visit's ``dimension`` holds its best outcome so far, and a
    spin-match suggestion's holds what the DJ did with it. That keeps each
    visit or suggestion one row, which the nightly rollup can count without
    knowing what the event means.

    Raw rows are kept for `tracking_service.RAW_RETENTION_DAYS`, then rolled
    into `AnalyticsDailyCount`.
    """

    __tablename__ = "analytics_event"

    id = Column(Integer, primary_key=True, index=True)
    occurred_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    event_type = Column(String, nullable=False, index=True)
    # The part of the app the event belongs to, one of `app.common.areas`
    area = Column(String, nullable=False)
    # The signed-in user; null for DJ studio and station office guests
    actor_email = Column(String, nullable=True)
    # "dj_studio", "station_office" or null
    network = Column(String, nullable=True)
    # What the event belongs to: a giveaway page visit ID, a guest session ID
    # or a Spinitron spin ID. Not kept by the rollup.
    ref = Column(String(64), nullable=True, index=True)
    entity_type = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)
    # Normalized DJ name (`tracking_service.normalize_dj_name`)
    dj_name = Column(String, nullable=True)
    # The event's outcome, result or sub-site, depending on its type
    dimension = Column(String, nullable=True)
    # Small extras, not kept by the rollup
    details = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_analytics_event_type_occurred", "event_type", "occurred_at"),
    )


class AnalyticsDailyCount(Base):
    """Daily counts of analytics events older than the raw retention period."""

    __tablename__ = "analytics_daily_count"

    id = Column(Integer, primary_key=True, index=True)
    # The Pacific date the events happened on
    day = Column(Date, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    area = Column(String, nullable=False)
    actor_email = Column(String, nullable=True)
    network = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)
    dj_name = Column(String, nullable=True)
    dimension = Column(String, nullable=True)
    count = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "day",
            "event_type",
            "area",
            "actor_email",
            "network",
            "entity_type",
            "entity_id",
            "dj_name",
            "dimension",
            name="uq_analytics_daily_count_key",
        ),
    )
