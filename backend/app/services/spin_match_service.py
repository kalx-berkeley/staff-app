"""Matches recently played Spinitron spins against shows with passes to give away.

Polled by the DJ view roughly once a minute so a DJ can hear a song, see a
popup pointing at the matching show, and give tickets away in the next mic
break. Two throttles keep this from hammering the Spinitron API:

- The "spins" API response is cached (SpinitronSpinCache) and only refetched
  once it's older than `_CACHE_TTL` — repeated polling from one or many DJ
  tabs reuses the same cached fetch in between.
- The fetch itself is entirely demand-driven: it only happens as a side
  effect of something calling `get_current_matches`, so no Spinitron calls
  happen at all while no DJ view is open to ask.

Every current match is returned on every poll — nothing is remembered as
"already shown" just because it was computed. A match only stops being
returned once something explicitly calls `dismiss` for that exact
(spin_id, show_id) pair (see DismissedSpinMatch), which the DJ view does
when a toast is dismissed or clicked through. That keeps dismissal tied to
an actual DJ seeing the notification, rather than the first poll after a
match exists — and since dismissal is server-side, it clears the match from
every open DJ tab on their next poll, not just the tab that dismissed it.

Matching shares its rapidfuzz rules and thresholds with feature_bin_service
and kalx_live_service (tagged show artists first, event-name fallback with a
stricter path for single-word names) via fuzzy_artist_match, just in the
opposite direction: one spin artist against many candidate shows instead of
many artists against one show.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.dismissed_spin_match import DismissedSpinMatch
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.spinitron_spin_cache import SpinitronSpinCache
from app.services.fuzzy_artist_match import (
    is_band_name_match,
    match_event_names_against_name,
)
from app.services.spinitron_service import SpinitronService

logger = logging.getLogger(__name__)

# How long a cached Spinitron "spins" fetch is considered fresh.
_CACHE_TTL = timedelta(seconds=60)

# How far back to ask Spinitron for spins each time the cache is refreshed —
# generous relative to the cache TTL so a slow poller never misses a spin.
_LOOKBACK = timedelta(minutes=15)

# How long a dismissed (spin_id, show_id) pair is remembered before it's
# pruned. Only needs to outlast _LOOKBACK, since a spin older than that can
# never be fetched from Spinitron again, so its match can never resurface.
_DISMISSED_RETENTION = timedelta(hours=1)

_CACHE_ROW_ID = 1


@dataclass
class SpinMatch:
    """One current spin/show match, ready to hand to the API layer."""

    spin_id: int
    artist: str
    song: str
    image: str | None
    show: Show


class SpinMatchService:
    """Fetches/caches recent Spinitron spins and matches them against giveaway shows."""

    @staticmethod
    def is_configured() -> bool:
        """Whether Spinitron is configured at all (same flag SpinitronService checks)."""
        return bool(settings.spinitron_api_key)

    @staticmethod
    async def _get_cached_spins(db: Session) -> list[dict]:
        """Return recent spins, refetching from Spinitron if the cache is stale."""
        now = datetime.now(timezone.utc)
        row = db.get(SpinitronSpinCache, _CACHE_ROW_ID)

        if row is not None:
            fetched_at = row.fetched_at
            if fetched_at.tzinfo is None:
                # SQLite drops tzinfo on round-trip even though it's stored UTC.
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if now - fetched_at < _CACHE_TTL:
                return row.spins

        spins = await SpinitronService.fetch_spins(start=now - _LOOKBACK)
        spin_dicts = [
            {
                "id": s["id"],
                "start": s["start"].isoformat(),
                "artist": s["artist"],
                "song": s["song"],
                "image": s["image"],
            }
            for s in spins
        ]

        if row is None:
            db.add(SpinitronSpinCache(id=_CACHE_ROW_ID, fetched_at=now, spins=spin_dicts))
        else:
            row.fetched_at = now
            row.spins = spin_dicts
        db.commit()

        return spin_dicts

    @staticmethod
    def _candidate_shows(db: Session) -> list[Show]:
        """Published shows with at least one available pass pair left to give away."""
        show_ids_with_pairs = (
            select(Pass.show_id)
            .where(Pass.pass_type == "pair", Pass.status == "available")
            .group_by(Pass.show_id)
            .having(func.count(Pass.id) > 0)
        )
        return (
            db.query(Show)
            .options(joinedload(Show.bands), joinedload(Show.venue))
            .filter(Show.status == "published", Show.id.in_(show_ids_with_pairs))
            .all()
        )

    @staticmethod
    def _matching_shows(artist_name: str, shows: list[Show]) -> list[Show]:
        """Return candidate shows whose tagged artists (or event name) match *artist_name*."""
        matched: list[Show] = []
        event_name_candidates: dict[int, str] = {}
        for show in shows:
            band_names = [b.band_name for b in show.bands or [] if b.band_name]
            if band_names:
                if any(
                    is_band_name_match(artist_name, band_name) for band_name in band_names
                ):
                    matched.append(show)
                continue

            if show.event_name:
                event_name_candidates[show.id] = show.event_name

        if event_name_candidates:
            matched_ids = match_event_names_against_name(artist_name, event_name_candidates)
            matched.extend(show for show in shows if show.id in matched_ids)

        return matched

    @staticmethod
    def _dismissed_pairs(db: Session, spin_ids: list[int]) -> set[tuple[int, int]]:
        """Which (spin_id, show_id) pairs among *spin_ids* have already been dismissed."""
        rows = (
            db.query(DismissedSpinMatch.spin_id, DismissedSpinMatch.show_id)
            .filter(DismissedSpinMatch.spin_id.in_(spin_ids))
            .all()
        )
        return {(spin_id, show_id) for spin_id, show_id in rows}

    @staticmethod
    def _prune_dismissed(db: Session, now: datetime) -> None:
        db.query(DismissedSpinMatch).filter(
            DismissedSpinMatch.dismissed_at < now - _DISMISSED_RETENTION
        ).delete()

    @staticmethod
    async def get_current_matches(db: Session) -> list[SpinMatch]:
        """Return every current spin/show match that hasn't been dismissed.

        Returned again on every call — including from every other open DJ
        tab — until `dismiss` is called for that exact (spin_id, show_id)
        pair. A spin matching two different shows yields two independent
        matches, each dismissible on its own.
        """
        if not SpinMatchService.is_configured():
            return []

        spins = await SpinMatchService._get_cached_spins(db)
        if not spins:
            return []

        now = datetime.now(timezone.utc)
        spin_ids = [s["id"] for s in spins]
        dismissed = SpinMatchService._dismissed_pairs(db, spin_ids)

        candidate_shows = SpinMatchService._candidate_shows(db)
        matches: list[SpinMatch] = []

        if candidate_shows:
            for spin in spins:
                matched_shows = SpinMatchService._matching_shows(
                    spin["artist"], candidate_shows
                )
                for show in matched_shows:
                    if (spin["id"], show.id) in dismissed:
                        continue
                    matches.append(
                        SpinMatch(
                            spin_id=spin["id"],
                            artist=spin["artist"],
                            song=spin["song"],
                            image=spin["image"],
                            show=show,
                        )
                    )

        SpinMatchService._prune_dismissed(db, now)
        db.commit()

        return matches

    @staticmethod
    def dismiss(db: Session, spin_id: int, show_id: int) -> None:
        """Record that a spin/show match has been dismissed or clicked through.

        Idempotent, so a retried request never errors on the duplicate row.
        """
        if db.get(DismissedSpinMatch, (spin_id, show_id)) is None:
            db.add(
                DismissedSpinMatch(
                    spin_id=spin_id,
                    show_id=show_id,
                    dismissed_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
