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

A spin only matches a show's tagged artists (ShowBand), never its
event_name, by the rule shared with feature_bin_service and
kalx_live_service (see fuzzy_artist_match).

A show is only a candidate while whoever is on air could give away a pair
for it right now, by the same rule as the DJ show list's "Give Away" button:
it's published and not past its planned close time, a pair is left that
isn't pre-assigned to another DJ, and the on-air identity hasn't already
given away a pair for it within DJ_SHOW_GIVEAWAY_WINDOW.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.dismissed_spin_match import DismissedSpinMatch
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.spinitron_spin_cache import SpinitronSpinCache
from app.pass_giveaway.services.fuzzy_artist_match import is_band_name_match
from app.common.services.spinitron_service import SpinitronService

if TYPE_CHECKING:
    # on_air_identity imports this module (for recent_spins), and pass_service
    # imports on_air_identity, so both are imported where they're used.
    from app.pass_giveaway.services.on_air_identity import OnAirIdentity

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
    async def recent_spins(db: Session) -> list[dict]:
        """
        Spins from the last 15 minutes, most recent first, refetched from
        Spinitron at most once a minute.

        Each is {"id", "start" (ISO), "artist", "song", "image",
        "playlist_id"}. Also read by `on_air_identity`, so the DJ pages'
        polling keeps both features fresh with one Spinitron call a minute.
        """
        return await SpinMatchService._get_cached_spins(db)

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
                "playlist_id": s.get("playlist_id"),
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
    def _candidate_shows(db: Session, identity: "OnAirIdentity | None") -> list[Show]:
        """Published shows that *identity* could give away a pass pair for right now.

        That takes an available pair that's unassigned or pre-assigned to
        *identity* (during a talk show, only the show's own; see
        `isPreassignedTo` in the frontend's utils.ts), a planned close time
        that hasn't passed, and no pair given away by *identity* for the show
        within DJ_SHOW_GIVEAWAY_WINDOW. With no one on air, only unassigned
        pairs count.
        """
        from app.pass_giveaway.services.on_air_identity import credit
        from app.pass_giveaway.services.pass_service import (
            DJ_SHOW_GIVEAWAY_WINDOW,
            PassService,
        )

        persona_id, specialty_show_id = credit(identity)
        mine = []
        if specialty_show_id is not None:
            mine.append(Pass.preassigned_specialty_show_id == specialty_show_id)
        if persona_id is not None and identity.kind != "talk":
            mine.append(
                Pass.preassigned_specialty_show_id.is_(None)
                & (Pass.preassigned_persona_id == persona_id)
            )
        givable_pair_show_ids = db.query(Pass.show_id).filter(
            Pass.pass_type == "pair",
            Pass.status == "available",
            or_(~Pass.is_preassigned, *mine) if mine else ~Pass.is_preassigned,
        )

        query = (
            db.query(Show)
            .options(joinedload(Show.bands), joinedload(Show.venue))
            .filter(Show.status == "published", Show.id.in_(givable_pair_show_ids))
        )
        if identity is not None:
            since = datetime.now(timezone.utc) - DJ_SHOW_GIVEAWAY_WINDOW
            recently_given = db.query(OnAirWinner.show_id).filter(
                _null_safe_eq(OnAirWinner.given_away_persona_id, persona_id),
                _null_safe_eq(OnAirWinner.given_away_specialty_show_id, specialty_show_id),
                OnAirWinner.created_at >= since,
            )
            query = query.filter(~Show.id.in_(recently_given))

        return [show for show in query.all() if not PassService.planned_close_passed(show)]

    @staticmethod
    def _matching_shows(artist_name: str, shows: list[Show]) -> list[Show]:
        """Return candidate shows with a tagged artist matching *artist_name*.

        A show with no tagged artists never matches.
        """
        return [
            show
            for show in shows
            if any(
                is_band_name_match(artist_name, band.band_name)
                for band in show.bands or []
                if band.band_name
            )
        ]

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
    async def get_current_matches(
        db: Session, identity: "OnAirIdentity | None"
    ) -> list[SpinMatch]:
        """Return every current spin/show match that hasn't been dismissed.

        Only shows *identity* (who is on air) could give away a pair for now
        can match (see `_candidate_shows`).

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

        candidate_shows = SpinMatchService._candidate_shows(db, identity)
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


def _null_safe_eq(column, value):
    return column.is_(None) if value is None else column == value
