"""Spinitron show-title lookups for the specialty-show autocompletes.

Two read-through caches (~1 day TTL, via `cache_service.fetch_cached_async`):
upcoming show titles (for suggesting a specialty show's name) and show-to-DJ
history, past and future (for suggesting who to add to a specialty show's
roster). Both draw on `/shows` and `/playlists` together — `/shows` often
lists a generic placeholder for a slot that `/playlists` already has a
specific DJ's pre-provisioned playlist for, so a match in either counts.
"""

from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from app.services import cache_service
from app.services.spinitron_schedule_service import SpinitronScheduleService
from app.services.spinitron_service import SpinitronService, dedupe_by_id

UPCOMING_WINDOW_DAYS = 14
HISTORY_WINDOW_DAYS = 60

_UPCOMING_TITLES_CACHE_KEY = "spinitron:upcoming-show-titles"
_PAST_SHOW_HOSTS_CACHE_KEY = "spinitron:past-show-hosts"


class SpinitronShowTitlesService:
    """Read-through caches over Spinitron's schedule and on-air log, by title."""

    @staticmethod
    async def get_upcoming_titles(db: Session) -> List[str]:
        """
        List distinct Spinitron show titles scheduled in the next ~2 weeks.

        Includes every scheduled show, not just specialty ones — a DJ's
        regular show title will appear here too. Draws on future `/shows`,
        past `/playlists`, and pre-provisioned future `/playlists` together,
        so a new specialty show that's only been pre-provisioned as a
        playlist (and hasn't aired or reached `/shows` yet) still shows up.
        """

        async def producer() -> dict:
            now = datetime.now(timezone.utc)
            end = now + timedelta(days=UPCOMING_WINDOW_DAYS)
            shows = await SpinitronService.fetch_shows(end)
            past_playlists = await SpinitronService.fetch_playlists(
                now - timedelta(days=HISTORY_WINDOW_DAYS), now
            )
            future_playlists = await SpinitronService.fetch_future_playlists()
            playlists = dedupe_by_id(past_playlists, future_playlists)

            titles = sorted({item["title"] for item in shows + playlists if item["title"]})
            return {"titles": titles}

        data = await cache_service.fetch_cached_async(
            db, _UPCOMING_TITLES_CACHE_KEY, producer, ttl_days=1
        )
        return data["titles"]

    @staticmethod
    async def get_dj_history_for_title(db: Session, title: str) -> List[str]:
        """
        List distinct DJ names who have hosted or will host a show titled exactly *title*.

        Covers the past ~2 months and any pre-provisioned future playlists
        (`/shows` isn't consulted — it never has historical data, and any
        future occurrence it lists without a pre-provisioned playlist has no
        specific DJ to suggest yet). Names are returned in first-seen
        (most-recent-first, per Spinitron's own ordering) order.
        """

        async def producer() -> dict:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=HISTORY_WINDOW_DAYS)
            past_playlists = await SpinitronService.fetch_playlists(start, end)
            future_playlists = await SpinitronService.fetch_future_playlists()
            playlists = dedupe_by_id(past_playlists, future_playlists)
            resolved = await SpinitronScheduleService.resolve_dj_names(db, playlists)

            entries = []
            for playlist in playlists:
                dj_name = (
                    resolved.get(playlist["persona_id"]) if playlist["persona_id"] else None
                )
                if playlist["title"] and dj_name:
                    entries.append({"title": playlist["title"], "dj_name": dj_name})
            return {"entries": entries}

        data = await cache_service.fetch_cached_async(
            db, _PAST_SHOW_HOSTS_CACHE_KEY, producer, ttl_days=1
        )

        dj_names: List[str] = []
        for entry in data["entries"]:
            if entry["title"] == title and entry["dj_name"] not in dj_names:
                dj_names.append(entry["dj_name"])
        return dj_names
