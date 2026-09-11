"""Spinitron show-title lookups for the specialty-show autocompletes.

Two read-through caches (~1 day TTL, via `cache_service.fetch_cached_async`):
upcoming show titles (for suggesting a specialty show's name) and recent
show-to-DJ history (for suggesting who to add to a specialty show's roster).
"""

from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from app.services import cache_service
from app.services.spinitron_schedule_service import SpinitronScheduleService
from app.services.spinitron_service import SpinitronService

UPCOMING_WINDOW_DAYS = 14
HISTORY_WINDOW_DAYS = 60

_UPCOMING_TITLES_CACHE_KEY = "spinitron:upcoming-show-titles"
_PAST_SHOW_HOSTS_CACHE_KEY = "spinitron:past-show-hosts"


class SpinitronShowTitlesService:
    """Read-through caches over Spinitron's `/shows` schedule, by title."""

    @staticmethod
    async def get_upcoming_titles(db: Session) -> List[str]:
        """
        List distinct Spinitron show titles scheduled in the next ~2 weeks.

        Includes every scheduled show, not just specialty ones — a DJ's
        regular show title will appear here too.
        """

        async def producer() -> dict:
            end = datetime.now(timezone.utc) + timedelta(days=UPCOMING_WINDOW_DAYS)
            shows = await SpinitronService.fetch_shows(end)
            titles = sorted({show["title"] for show in shows if show["title"]})
            return {"titles": titles}

        data = await cache_service.fetch_cached_async(
            db, _UPCOMING_TITLES_CACHE_KEY, producer, ttl_days=1
        )
        return data["titles"]

    @staticmethod
    async def get_dj_history_for_title(db: Session, title: str) -> List[str]:
        """
        List distinct DJ names who hosted a show titled exactly *title* in the past ~2 months.

        Names are returned in first-seen (most-recent-first, per Spinitron's
        own ordering) order.
        """

        async def producer() -> dict:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=HISTORY_WINDOW_DAYS)
            shows = await SpinitronService.fetch_shows(end, start=start)
            resolved = await SpinitronScheduleService.resolve_dj_names(db, shows)

            entries = []
            for show in shows:
                dj_name = resolved.get(show["persona_id"]) if show["persona_id"] else None
                if show["title"] and dj_name:
                    entries.append({"title": show["title"], "dj_name": dj_name})
            return {"entries": entries}

        data = await cache_service.fetch_cached_async(
            db, _PAST_SHOW_HOSTS_CACHE_KEY, producer, ttl_days=1
        )

        dj_names: List[str] = []
        for entry in data["entries"]:
            if entry["title"] == title and entry["dj_name"] not in dj_names:
                dj_names.append(entry["dj_name"])
        return dj_names
