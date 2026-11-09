"""
Roll raw analytics events older than 13 months into daily counts.

Each event becomes a count on its Pacific date, keyed by type, area, actor,
network, entity, DJ name and dimension. `ref` and `details` are dropped, so
anything a metric needs from an old event has to be in those columns: that's
why a giveaway page visit keeps its outcome in `dimension` instead of in
separate events.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.common.services.tracking_service import (
    RAW_RETENTION_DAYS,
    pacific_date,
    pacific_day_start_utc,
)
from app.models.analytics_event import AnalyticsDailyCount, AnalyticsEvent


def roll_up_old_events(db: Session, now: datetime | None = None) -> int:
    """
    Move every raw event from before the retention cutoff into daily counts.

    The cutoff is a Pacific midnight, so a day is always rolled up whole.

    :returns: How many raw events were rolled up.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = pacific_day_start_utc(pacific_date(now) - timedelta(days=RAW_RETENTION_DAYS))
    old = db.query(AnalyticsEvent).filter(AnalyticsEvent.occurred_at < cutoff).all()
    if not old:
        return 0

    counts: Counter = Counter()
    for e in old:
        counts[(
            pacific_date(e.occurred_at),
            e.event_type,
            e.area,
            e.actor_email,
            e.network,
            e.entity_type,
            e.entity_id,
            e.dj_name,
            e.dimension,
        )] += 1

    for key, n in counts.items():
        day, event_type, area, actor, network, entity_type, entity_id, dj, dimension = key
        existing = (
            db.query(AnalyticsDailyCount)
            .filter(
                AnalyticsDailyCount.day == day,
                AnalyticsDailyCount.event_type == event_type,
                AnalyticsDailyCount.area == area,
                _null_safe_eq(AnalyticsDailyCount.actor_email, actor),
                _null_safe_eq(AnalyticsDailyCount.network, network),
                _null_safe_eq(AnalyticsDailyCount.entity_type, entity_type),
                _null_safe_eq(AnalyticsDailyCount.entity_id, entity_id),
                _null_safe_eq(AnalyticsDailyCount.dj_name, dj),
                _null_safe_eq(AnalyticsDailyCount.dimension, dimension),
            )
            .first()
        )
        if existing:
            existing.count += n
        else:
            db.add(
                AnalyticsDailyCount(
                    day=day,
                    event_type=event_type,
                    area=area,
                    actor_email=actor,
                    network=network,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    dj_name=dj,
                    dimension=dimension,
                    count=n,
                )
            )
    for e in old:
        db.delete(e)
    db.commit()
    return len(old)


def _null_safe_eq(column, value):
    return column.is_(None) if value is None else column == value
