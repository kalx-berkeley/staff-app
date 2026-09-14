"""KALX Live! sync and matching service.

KALX Live! is KALX's weekly in-studio live band performance. The schedule of
past and upcoming performances is tracked in a public Google Calendar. This
service fetches that calendar nightly as an ICS export, replaces the
KalxLiveAppearance table with the calendar's current snapshot, and matches
KALX Live! bands against shows so the promotions website can flag shows with
a performer who was recently on KALX Live! or will be in the future.
"""

import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import httpx2 as httpx
from icalendar import Calendar
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.job_log import JobLog
from app.models.kalx_live_appearance import KalxLiveAppearance
from app.services.fuzzy_artist_match import (
    is_band_name_match,
    match_names_against_event_name,
)

logger = logging.getLogger(__name__)

_ICS_URL_TEMPLATE = (
    "https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics"
)

# How old KALX Live data can get before a fresh sync is considered overdue
# (used by the startup bootstrap check, not the nightly schedule itself).
_STALE_AFTER = timedelta(days=1)

# How far in the past a KALX Live! appearance can be and still count as
# "recent" for flagging purposes. There's no upper bound on future dates.
_PAST_WINDOW = timedelta(days=60)

# Calendar titles follow the convention "<Band Name> on KALX Live!". Before a
# band is booked the slot is titled "[band] on KALX Live!", and a cancelled
# slot is prefixed "CANCELLED". Everything else on the calendar (trainings,
# meetings, orientations, etc.) doesn't match this suffix at all.
_TITLE_RE = re.compile(r"^(.+?)\s+on\s+KALX Live!\s*$", re.IGNORECASE)


@dataclass
class KalxLiveIndex:
    """A snapshot of KALX Live! appearances used to match against shows."""

    appearances: list[KalxLiveAppearance] = field(default_factory=list)


class KalxLiveService:
    """Fetches, stores, and matches the KALX Live! calendar against shows."""

    @staticmethod
    def is_configured() -> bool:
        """Whether KALX_LIVE_CALENDAR_ID is set.

        The calendar ID isn't public data, so it has no default in this
        public repo — the feature is simply disabled until it's configured.
        """
        return bool(settings.kalx_live_calendar_id)

    @staticmethod
    def needs_sync(db: Session) -> bool:
        """Whether there's no KALX Live data yet, or it's more than a day old.

        Used by the startup bootstrap check to catch a freshly deployed
        instance or a long period of scheduler downtime.
        """
        count, latest_fetched_at = db.query(
            func.count(KalxLiveAppearance.id), func.max(KalxLiveAppearance.fetched_at)
        ).one()
        if count == 0 or latest_fetched_at is None:
            return True
        # SQLite drops tzinfo on round-trip even though fetched_at is stored
        # timezone-aware (UTC) — re-attach it before comparing.
        latest_fetched_at = latest_fetched_at.replace(tzinfo=timezone.utc)
        return latest_fetched_at < datetime.now(timezone.utc) - _STALE_AFTER

    @staticmethod
    def fetch_ics() -> bytes:
        """Fetch the KALX Live! calendar as an ICS export.

        The calendar is currently public, so this is a plain unauthenticated
        request to its ICS export URL.
        """
        url = _ICS_URL_TEMPLATE.format(
            calendar_id=urllib.parse.quote(settings.kalx_live_calendar_id, safe="")
        )
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return response.content

    @staticmethod
    def parse_ics(ics_content: bytes) -> list[dict]:
        """Parse the calendar's ICS export into {band_name, event_date} dicts.

        Only events whose title matches "<Band Name> on KALX Live!" are
        returned — the not-yet-booked "[band]" placeholder and cancelled
        slots are skipped, as is anything that doesn't match the title
        format at all (trainings, meetings, orientations, etc.).

        Recurring "master" events (carrying an RRULE) are never expanded:
        every real, booked appearance is already materialized in the export
        as its own override VEVENT with a concrete DTSTART, and the masters
        all carry the literal placeholder title, so they're already excluded
        by the placeholder check below without any recurrence-expansion
        logic.
        """
        calendar = Calendar.from_ical(ics_content)
        parsed: list[dict] = []
        for event in calendar.walk("VEVENT"):
            summary = event.get("SUMMARY")
            dtstart = event.get("DTSTART")
            if summary is None or dtstart is None:
                continue

            match = _TITLE_RE.match(str(summary))
            if not match:
                continue
            band_name = match.group(1).strip()
            if not band_name:
                continue
            if band_name.lower() == "[band]":
                continue
            if band_name.lower().startswith("cancelled"):
                continue

            start = dtstart.dt
            event_date = start.date() if isinstance(start, datetime) else start
            parsed.append({"band_name": band_name, "event_date": event_date})

        return parsed

    @staticmethod
    def sync_kalx_live(db: Session, trigger: str = "scheduled") -> int:
        """Fetch the calendar and replace KalxLiveAppearance with its current contents.

        No-ops (without logging a JobLog run) when the calendar isn't configured.
        """
        if not KalxLiveService.is_configured():
            logger.warning("KALX_LIVE_CALENDAR_ID not configured, skipping KALX Live sync")
            return 0

        ics_content = KalxLiveService.fetch_ics()
        rows = KalxLiveService.parse_ics(ics_content)

        db.query(KalxLiveAppearance).delete()
        db.add_all([KalxLiveAppearance(**row) for row in rows])
        db.add(JobLog(job_id="kalx_live_sync", trigger=trigger))
        db.commit()

        logger.info("KALX Live sync stored %d appearance(s)", len(rows))
        return len(rows)

    @staticmethod
    def build_index(db: Session) -> KalxLiveIndex:
        """Load all KALX Live! appearances once, for matching against many shows."""
        return KalxLiveIndex(appearances=db.query(KalxLiveAppearance).all())

    @staticmethod
    def find_matches(index: KalxLiveIndex, show) -> list[KalxLiveAppearance]:
        """Return KALX Live! appearances matching a show's tagged artists or event name.

        Tagged artists (show.bands) are preferred when present; otherwise
        falls back to fuzzy-matching the whole event_name against KALX Live!
        band names. Only appearances within the recency window (recent past
        or any future date) are considered.
        """
        cutoff = date.today() - _PAST_WINDOW
        candidates = [a for a in index.appearances if a.event_date >= cutoff]
        if not candidates:
            return []

        band_names = [b.band_name for b in show.bands or [] if b.band_name]
        if band_names:
            matched: list[KalxLiveAppearance] = []
            matched_ids: set[int] = set()
            for band_name in band_names:
                for appearance in candidates:
                    if appearance.id in matched_ids:
                        continue
                    if is_band_name_match(band_name, appearance.band_name):
                        matched.append(appearance)
                        matched_ids.add(appearance.id)
            return matched

        if not show.event_name:
            return []

        name_candidates = {a.id: a.band_name for a in candidates}
        matched_ids = match_names_against_event_name(show.event_name, name_candidates)
        return [a for a in candidates if a.id in matched_ids]
