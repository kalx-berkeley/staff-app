"""
Record and read the analytics events behind KALX Staff Analytics.

Events go into `AnalyticsEvent`. Raw rows are kept for `RAW_RETENTION_DAYS`
(13 months, so this year can be compared with last year in full), then the
nightly rollup (`analytics_rollup`) turns them into `AnalyticsDailyCount`
rows. `event_counts` reads both, so metrics don't need to know which days
were rolled up.

Nothing is recorded while a site admin is impersonating someone in staging:
that's testing, not real use.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import is_ip_in_network
from app.config import settings
from app.models.analytics_event import AnalyticsDailyCount, AnalyticsEvent

logger = logging.getLogger(__name__)

PACIFIC = ZoneInfo("America/Los_Angeles")

# About 13 months
RAW_RETENTION_DAYS = 396

DJ_STUDIO_NETWORK = "dj_studio"
STATION_OFFICE_NETWORK = "station_office"

UNKNOWN_DJ = "Unknown DJ"


def normalize_dj_name(name: Optional[str]) -> Optional[str]:
    """Lowercase *name* and collapse its whitespace; None when it's blank."""
    if not name:
        return None
    collapsed = re.sub(r"\s+", " ", name).strip().lower()
    return collapsed[:100] or None


def normalize_person_name(name: Optional[str]) -> str:
    """Lowercase *name*, drop punctuation and collapse whitespace."""
    if not name:
        return ""
    without_punctuation = re.sub(r"[^\w\s]", "", name.lower())
    return re.sub(r"\s+", " ", without_punctuation).strip()


def normalize_phone(phone: Optional[str]) -> str:
    """Digits only, without a leading US 1 on an 11-digit number."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def as_utc(dt: datetime) -> datetime:
    """*dt* as an aware UTC datetime (SQLite returns naive UTC datetimes)."""
    return (
        dt.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None
        else dt.astimezone(timezone.utc)
    )


def pacific_date(dt: datetime) -> date:
    """The Pacific date of a UTC datetime (naive or aware)."""
    return as_utc(dt).astimezone(PACIFIC).date()


def pacific_day_start_utc(day: date) -> datetime:
    """Midnight Pacific at the start of *day*, as a naive UTC datetime."""
    local = datetime.combine(day, time.min, tzinfo=PACIFIC)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def request_network(
    x_dj_network: Optional[str],
    x_station_office_network: Optional[str],
    x_forwarded_for: Optional[str],
) -> Optional[str]:
    """Which trusted network a request came from, as `check_apache_auth_layer` decides."""
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else None
    if x_dj_network == "1" or (
        client_ip and is_ip_in_network(client_ip, settings.dj_studio_network)
    ):
        return DJ_STUDIO_NETWORK
    if x_station_office_network == "1" or (
        client_ip and is_ip_in_network(client_ip, settings.station_office_network)
    ):
        return STATION_OFFICE_NETWORK
    return None


def is_impersonating(db: Session, real_email: Optional[str]) -> bool:
    """Whether *real_email* (the signed-in user) is impersonating someone."""
    if not real_email or settings.environment != "staging":
        return False
    from app.models.impersonation_session import ImpersonationSession

    imp = (
        db.query(ImpersonationSession)
        .filter(ImpersonationSession.real_email == real_email)
        .first()
    )
    return bool(imp and imp.impersonated_email)


def record_event(
    db: Session,
    event_type: str,
    *,
    area: str,
    real_email: Optional[str] = None,
    actor_email: Optional[str] = None,
    network: Optional[str] = None,
    ref: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    dj_name: Optional[str] = None,
    dimension: Optional[str] = None,
    details: Optional[dict] = None,
) -> Optional[AnalyticsEvent]:
    """
    Write one analytics event, unless *real_email* is impersonating someone.

    Errors are logged and swallowed, so tracking never breaks the request
    it's part of.

    :param real_email: The real signed-in user (X-Forwarded-User), checked
        for impersonation. Defaults to *actor_email*.
    :param actor_email: Who to record as the actor; null for guests.
    :param dj_name: A DJ name, normalized here.
    :returns: The new event, or None if nothing was recorded.
    """
    if is_impersonating(db, real_email or actor_email):
        return None
    try:
        event = AnalyticsEvent(
            event_type=event_type,
            area=area,
            actor_email=actor_email,
            network=network,
            ref=ref,
            entity_type=entity_type,
            entity_id=entity_id,
            dj_name=normalize_dj_name(dj_name),
            dimension=dimension,
            details=details,
        )
        db.add(event)
        db.commit()
        return event
    except Exception:
        db.rollback()
        logger.error("Failed to record analytics event %s", event_type, exc_info=True)
        return None


@dataclass
class EventCount:
    """Events with the same key on one day: one raw event, or a rolled-up count."""

    day: date
    event_type: str
    actor_email: Optional[str]
    network: Optional[str]
    entity_type: Optional[str]
    entity_id: Optional[int]
    dj_name: Optional[str]
    dimension: Optional[str]
    count: int
    # Set for raw events only
    occurred_at: Optional[datetime] = None
    ref: Optional[str] = None


def event_counts(
    db: Session,
    event_types: Iterable[str],
    start: date,
    end: date,
) -> list[EventCount]:
    """Every event of *event_types* from *start* to *end* (Pacific dates, inclusive)."""
    types = list(event_types)
    rows: list[EventCount] = []
    raw = (
        db.query(AnalyticsEvent)
        .filter(
            AnalyticsEvent.event_type.in_(types),
            AnalyticsEvent.occurred_at >= pacific_day_start_utc(start),
            AnalyticsEvent.occurred_at < pacific_day_start_utc(end + timedelta(days=1)),
        )
        .all()
    )
    for e in raw:
        rows.append(
            EventCount(
                day=pacific_date(e.occurred_at),
                event_type=e.event_type,
                actor_email=e.actor_email,
                network=e.network,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                dj_name=e.dj_name,
                dimension=e.dimension,
                count=1,
                occurred_at=as_utc(e.occurred_at),
                ref=e.ref,
            )
        )
    rolled = (
        db.query(AnalyticsDailyCount)
        .filter(
            AnalyticsDailyCount.event_type.in_(types),
            AnalyticsDailyCount.day >= start,
            AnalyticsDailyCount.day <= end,
        )
        .all()
    )
    for r in rolled:
        rows.append(
            EventCount(
                day=r.day,
                event_type=r.event_type,
                actor_email=r.actor_email,
                network=r.network,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                dj_name=r.dj_name,
                dimension=r.dimension,
                count=r.count,
            )
        )
    return rows


def data_since(db: Session, event_types: Iterable[str]) -> Optional[date]:
    """The Pacific date of the earliest event of *event_types*, raw or rolled up."""
    types = list(event_types)
    earliest_raw = (
        db.query(func.min(AnalyticsEvent.occurred_at))
        .filter(AnalyticsEvent.event_type.in_(types))
        .scalar()
    )
    earliest_rolled = (
        db.query(func.min(AnalyticsDailyCount.day))
        .filter(AnalyticsDailyCount.event_type.in_(types))
        .scalar()
    )
    candidates = []
    if earliest_raw is not None:
        candidates.append(pacific_date(earliest_raw))
    if earliest_rolled is not None:
        candidates.append(earliest_rolled)
    return min(candidates) if candidates else None
