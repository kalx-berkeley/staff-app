"""Matches recently played Spinitron spins against shows with passes to give away.

Polled by the DJ view roughly once a minute so a DJ can hear a song, see a
popup pointing at the matching show, and give tickets away in the next mic
break. Two throttles keep this from hammering the Spinitron API:

- The "spins" API response is cached (SpinitronSpinCache) and only refetched
  once it's older than `_CACHE_TTL` — repeated polling from one or many DJ
  tabs reuses the same cached fetch in between.
- The fetch itself is entirely demand-driven: it only happens as a side
  effect of something calling `check_for_matches`, so no Spinitron calls
  happen at all while no DJ view is open to ask.

Matching reuses the same rapidfuzz approach as feature_bin_service (tagged
show artists first, event-name fallback for multi-word names), just in the
opposite direction: one spin artist against many candidate shows instead of
many feature-bin artists against one show.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from rapidfuzz import fuzz
from rapidfuzz.utils import default_process
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.spinitron_spin_cache import SpinitronSpinCache
from app.models.surfaced_spin_match import SurfacedSpinMatch
from app.services.spinitron_service import SpinitronService

logger = logging.getLogger(__name__)

# How long a cached Spinitron "spins" fetch is considered fresh.
_CACHE_TTL = timedelta(seconds=60)

# How far back to ask Spinitron for spins each time the cache is refreshed —
# generous relative to the cache TTL so a slow poller never misses a spin.
_LOOKBACK = timedelta(minutes=15)

# How long a spin_id is remembered as "already surfaced" before it's pruned.
# Only needs to outlast _LOOKBACK, since a spin older than that can never be
# fetched from Spinitron again.
_SURFACED_RETENTION = timedelta(hours=1)

# Same thresholds as feature_bin_service, for the same reasons: a tagged
# artist name is already normalized so a high bar avoids false positives,
# while the event_name fallback needs more slack for supporting-act/venue
# text around the headliner.
_BAND_MATCH_THRESHOLD = 90
_EVENT_NAME_MATCH_THRESHOLD = 85

_CACHE_ROW_ID = 1


@dataclass
class SpinMatch:
    """One newly-surfaced spin/show match, ready to hand to the API layer."""

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
        for show in shows:
            band_names = [b.band_name for b in show.bands or [] if b.band_name]
            if band_names:
                if any(
                    fuzz.ratio(artist_name, band_name, processor=default_process)
                    >= _BAND_MATCH_THRESHOLD
                    for band_name in band_names
                ):
                    matched.append(show)
                continue

            # Same single-word guard as feature_bin_service: a short artist
            # name is too likely to coincidentally appear as a token inside
            # an unrelated event name for token_set_ratio to be trustworthy.
            if show.event_name and len(artist_name.split()) > 1:
                score = fuzz.token_set_ratio(
                    artist_name, show.event_name, processor=default_process
                )
                if score >= _EVENT_NAME_MATCH_THRESHOLD:
                    matched.append(show)
        return matched

    @staticmethod
    def _prune_surfaced(db: Session, now: datetime) -> None:
        db.query(SurfacedSpinMatch).filter(
            SurfacedSpinMatch.surfaced_at < now - _SURFACED_RETENTION
        ).delete()

    @staticmethod
    async def check_for_matches(db: Session) -> list[SpinMatch]:
        """Return spin/show matches not already surfaced to a DJ view.

        Every returned match is recorded in SurfacedSpinMatch before this
        returns, so calling it again — from this poll or any other DJ tab —
        will never return the same spin_id twice.
        """
        if not SpinMatchService.is_configured():
            return []

        spins = await SpinMatchService._get_cached_spins(db)
        if not spins:
            return []

        now = datetime.now(timezone.utc)
        spin_ids = [s["id"] for s in spins]
        already_surfaced = {
            row[0]
            for row in (
                db.query(SurfacedSpinMatch.spin_id)
                .filter(SurfacedSpinMatch.spin_id.in_(spin_ids))
                .all()
            )
        }

        pending_spins = [s for s in spins if s["id"] not in already_surfaced]
        if not pending_spins:
            return []

        candidate_shows = SpinMatchService._candidate_shows(db)
        matches: list[SpinMatch] = []
        new_rows: list[SurfacedSpinMatch] = []

        if candidate_shows:
            for spin in pending_spins:
                matched_shows = SpinMatchService._matching_shows(
                    spin["artist"], candidate_shows
                )
                for show in matched_shows:
                    matches.append(
                        SpinMatch(
                            spin_id=spin["id"],
                            artist=spin["artist"],
                            song=spin["song"],
                            image=spin["image"],
                            show=show,
                        )
                    )
                if matched_shows:
                    new_rows.append(
                        SurfacedSpinMatch(
                            spin_id=spin["id"], show_id=matched_shows[0].id, surfaced_at=now
                        )
                    )

        if new_rows:
            db.add_all(new_rows)
        SpinMatchService._prune_surfaced(db, now)
        db.commit()

        return matches
