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
from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.job_log import JobLog
from app.models.kalx_live_appearance import KalxLiveAppearance

logger = logging.getLogger(__name__)

_ICS_URL_TEMPLATE = (
    "https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics"
)

# How old KALX Live data can get before a fresh sync is considered overdue
# (used by the startup bootstrap check, not the nightly schedule itself).
_STALE_AFTER = timedelta(days=1)

# Same thresholds as FeatureBinService: a tagged artist (from ShowBand) is
# already an isolated, normalized name, so the only slop expected is
# casing/punctuation — a high threshold avoids false positives. An
# event_name fuzzy fallback needs more slack since it often has supporting-act
# text or venue framing around the headliner.
_BAND_MATCH_THRESHOLD = 90
_EVENT_NAME_MATCH_THRESHOLD = 85

# Single-word band names skip the token_set_ratio fallback above (see
# find_matches) and instead get compared word-for-word. The safety here
# comes mainly from comparing individual words rather than whole-string
# subset detection, plus the length floor and event-name word cap below
# — so this reuses the same high bar already trusted for tagged-band
# identity matching (_BAND_MATCH_THRESHOLD) rather than something even
# stricter, which would reject plausible single-letter typos on real
# short names (e.g. "Trough"/"Trogh" scores 91) while still rejecting
# genuinely different short words (e.g. "Cat"/"Bat" scores 67,
# "Live"/"Life" 75).
_SINGLE_WORD_EVENT_NAME_MATCH_THRESHOLD = _BAND_MATCH_THRESHOLD
# Below this length there's too little information in a single word for a
# match to mean anything, no matter how exact — a short, common word is
# too likely to collide by chance.
_MIN_SINGLE_WORD_LENGTH = 4
# Only attempt a single-word match when the band's word makes up a
# meaningful share of the event name — a coincidental shared word
# explains little of a long event name, so it isn't trustworthy evidence
# no matter how exactly it matches (see feature_bin_service's identical
# constant for the full rationale, including the residual ambiguity this
# doesn't resolve: two distinct real bands sharing a word within a short
# event name, which is exactly what tagging the artist on the show
# resolves unambiguously).
_MAX_EVENT_NAME_WORDS_FOR_SINGLE_WORD_MATCH = 3

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _event_name_words(event_name: str) -> list[str]:
    """Split an event name into individual words, for single-word band matching."""
    return _WORD_RE.findall(event_name)


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
                    score = fuzz.ratio(
                        band_name, appearance.band_name, processor=default_process
                    )
                    if score >= _BAND_MATCH_THRESHOLD:
                        matched.append(appearance)
                        matched_ids.add(appearance.id)
            return matched

        if not show.event_name:
            return []

        matched_ids: set[int] = set()

        # token_set_ratio (not token_sort_ratio) since event names typically
        # have extra words around the artist name — supporting acts, "w/",
        # venue framing — that token_sort_ratio's full-string comparison
        # would otherwise penalize heavily. Restricted to multi-word band
        # names, same as feature bin, so a single-word band name doesn't
        # coincidentally match an unrelated event name that happens to
        # contain that word; single-word names are handled separately below.
        multi_word_choices = {
            appearance.id: appearance.band_name
            for appearance in candidates
            if len(appearance.band_name.split()) > 1
        }
        if multi_word_choices:
            results = process.extract(
                show.event_name,
                multi_word_choices,
                scorer=fuzz.token_set_ratio,
                processor=default_process,
                score_cutoff=_EVENT_NAME_MATCH_THRESHOLD,
                limit=None,
            )
            matched_ids.update(appearance_id for _name, _score, appearance_id in results)

        # Single-word band names: see the constants above for why this is a
        # separate, stricter path (near-exact per-word comparison, a
        # minimum length, and a cap on how much longer the event name can
        # be) rather than just lowering token_set_ratio's threshold.
        event_words = _event_name_words(show.event_name)
        if event_words and len(event_words) <= _MAX_EVENT_NAME_WORDS_FOR_SINGLE_WORD_MATCH:
            for appearance in candidates:
                if appearance.id in matched_ids:
                    continue
                band_name = appearance.band_name
                if len(band_name.split()) != 1 or len(band_name) < _MIN_SINGLE_WORD_LENGTH:
                    continue
                if any(
                    fuzz.ratio(band_name, word, processor=default_process)
                    >= _SINGLE_WORD_EVENT_NAME_MATCH_THRESHOLD
                    for word in event_words
                ):
                    matched_ids.add(appearance.id)

        return [a for a in candidates if a.id in matched_ids]
