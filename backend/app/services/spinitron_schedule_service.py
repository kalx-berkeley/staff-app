"""Syncs the upcoming Spinitron on-air schedule into the schedule cache tables."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.config import settings
from app.models.job_log import JobLog
from app.models.spinitron_playlist import SpinitronPlaylist
from app.models.spinitron_show import SpinitronShow
from app.models.staff import Staff
from app.services import cache_service
from app.services.spinitron_service import SpinitronService, SpinitronShowItem, dedupe_by_id

logger = logging.getLogger(__name__)

_PERSONAS_CACHE_KEY = "spinitron:personas"

# How far back to look for playlists that are already airing. Generous
# relative to any plausible show length, since a playlist that started
# earlier than this and is still running would otherwise be missed by
# `GET /api/dj/on-air`.
PLAYLIST_LOOKBACK_HOURS = 24


class SpinitronScheduleService:
    """Fetches and caches the upcoming Spinitron on-air schedule."""

    @staticmethod
    async def sync_schedule(
        db: Session, trigger: str = "scheduled", hours_ahead: int = 12
    ) -> int:
        """
        Fetch the next *hours_ahead* hours of Spinitron shows and playlists and replace the cache.

        Playlists are fetched alongside shows because Spinitron's `/shows`
        and `/playlists` can disagree about a given timeslot — `/shows` often
        lists a generic placeholder (e.g. "DJ Trainee") for a slot that
        `/playlists` already has a specific DJ's pre-provisioned playlist
        for. `GET /api/dj/on-air` prefers the cached playlist over the cached
        show when both cover the same instant.

        Resolves each show/playlist's first persona to a DJ name, preferring
        the local Staff directory (already resolved during the Airtable
        sync) over a Spinitron persona API call. An entry whose persona is a
        configured "placeholder" (a rotating slot like "DJ Trainee" rather
        than a specific DJ) is stored with no DJ name, same as an entry with
        no persona at all — this stops the DJ Name field from being
        auto-filled or flagged as mismatched during that show.

        No-ops (without logging a JobLog run) when Spinitron isn't configured.

        :param db: Database session.
        :param trigger: "manual" or "scheduled", recorded on the JobLog entry.
        :param hours_ahead: How far ahead of now to fetch the schedule.
        :returns: Number of shows plus playlists cached.
        """
        if not settings.spinitron_api_key:
            logger.warning("SPINITRON_API_KEY not configured, skipping schedule sync")
            return 0

        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=hours_ahead)

        shows = await SpinitronService.fetch_shows(end)
        past_playlists = await SpinitronService.fetch_playlists(
            now - timedelta(hours=PLAYLIST_LOOKBACK_HOURS), now
        )
        future_playlists = await SpinitronService.fetch_future_playlists()
        playlists = [
            playlist
            for playlist in dedupe_by_id(past_playlists, future_playlists)
            if playlist["start"] <= end
        ]

        resolved = await SpinitronScheduleService.resolve_dj_names(db, shows + playlists)

        show_rows: list[SpinitronShow] = [
            SpinitronShow(
                id=show["id"],
                start=show["start"],
                end=show["end"],
                dj_name=resolved.get(show["persona_id"]),
                persona_id=show["persona_id"],
            )
            for show in shows
        ]
        playlist_rows: list[SpinitronPlaylist] = [
            SpinitronPlaylist(
                id=playlist["id"],
                start=playlist["start"],
                end=playlist["end"],
                dj_name=resolved.get(playlist["persona_id"]),
                persona_id=playlist["persona_id"],
            )
            for playlist in playlists
        ]

        db.query(SpinitronShow).delete()
        db.query(SpinitronPlaylist).delete()
        db.add_all(show_rows)
        db.add_all(playlist_rows)
        db.add(JobLog(job_id="spinitron_schedule_sync", trigger=trigger))
        db.commit()

        total = len(show_rows) + len(playlist_rows)
        logger.info(
            "Spinitron schedule sync cached %d show(s) and %d playlist(s)",
            len(show_rows),
            len(playlist_rows),
        )
        return total

    @staticmethod
    async def resolve_dj_names(
        db: Session, shows: List[SpinitronShowItem]
    ) -> Dict[int, Optional[str]]:
        """
        Resolve each distinct persona ID among *shows* to a DJ name.

        Prefers the local Staff directory (already resolved during the
        Airtable sync) over Spinitron's persona directory (bulk-fetched and
        cached for a week, see `_cached_persona_names`). A show whose
        persona is a configured "placeholder" (a rotating slot like "DJ
        Trainee" rather than a specific DJ) resolves to no name, same as a
        show with no persona at all.

        :param db: Database session.
        :param shows: Shows to resolve personas for.
        :returns: Dict mapping persona ID to DJ name (or None if unresolved
            or a placeholder); persona IDs that are None are not included.
        """
        staff_persona_names = SpinitronScheduleService._single_persona_staff_names(db)
        placeholder_ids = SpinitronScheduleService._placeholder_persona_ids()
        resolved: Dict[int, Optional[str]] = {}

        unresolved_ids = {
            show["persona_id"]
            for show in shows
            if show["persona_id"] is not None
            and show["persona_id"] not in placeholder_ids
            and show["persona_id"] not in staff_persona_names
        }
        persona_names = (
            await SpinitronScheduleService._cached_persona_names(db)
            if unresolved_ids
            else {}
        )

        for show in shows:
            persona_id = show["persona_id"]
            if persona_id is None or persona_id in resolved:
                continue
            if persona_id in placeholder_ids:
                resolved[persona_id] = None
            elif persona_id in staff_persona_names:
                resolved[persona_id] = staff_persona_names[persona_id]
            else:
                resolved[persona_id] = persona_names.get(persona_id)

        return resolved

    @staticmethod
    async def _cached_persona_names(db: Session) -> Dict[int, str]:
        """
        Read-through cache (~1 week TTL) over Spinitron's full persona directory.

        Persona names change rarely, so one bulk `/personas` fetch (paginated
        internally by `fetch_all_personas`), shared across every caller for a
        week, replaces what would otherwise be a separate `/personas/{id}`
        API call for every distinct unresolved persona on every cache miss.
        """

        async def producer() -> dict:
            personas = await SpinitronService.fetch_all_personas()
            return {
                "personas": {str(persona_id): name for persona_id, name in personas.items()}
            }

        data = await cache_service.fetch_cached_async(
            db, _PERSONAS_CACHE_KEY, producer, ttl_days=7
        )
        return {int(persona_id): name for persona_id, name in data["personas"].items()}

    @staticmethod
    def _placeholder_persona_ids() -> Set[int]:
        """Parse SPINITRON_PLACEHOLDER_PERSONA_IDS into a set of persona IDs."""
        return {
            int(raw_id.strip())
            for raw_id in settings.spinitron_placeholder_persona_ids.split(",")
            if raw_id.strip()
        }

    @staticmethod
    def _single_persona_staff_names(db: Session) -> Dict[int, str]:
        """
        Map persona ID -> DJ name for Staff records with exactly one Spinitron ID.

        `Staff.dj_name` is a comma-joined string when a staff member has
        multiple `spinitron_ids`, so it's only safe to reuse directly when
        there's a single ID — otherwise we'd attribute the joined name to one
        persona.
        """
        names: Dict[int, str] = {}
        staff = (
            db.query(Staff)
            .filter(Staff.spinitron_ids.isnot(None), Staff.dj_name.isnot(None))
            .all()
        )
        for record in staff:
            ids = record.spinitron_ids or []
            if len(ids) == 1:
                names[int(ids[0])] = record.dj_name
        return names
