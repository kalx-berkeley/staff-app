"""Spinitron upcoming on-air schedule lookups, for DJ pass-pair reservation dates.

One read-through cache (~1 day TTL, via `cache_service.fetch_cached_async`) over
the next ~4 weeks of Spinitron shows, filtered by name on read — mirrors the
`SpinitronShowTitlesService` pattern used for the specialty-show autocompletes.
"""

from datetime import datetime, timedelta, timezone
from typing import List, TypedDict

from sqlalchemy.orm import Session

from app.services import cache_service
from app.services.spinitron_schedule_service import SpinitronScheduleService
from app.services.spinitron_service import SpinitronService

SCHEDULE_WINDOW_DAYS = 28

_UPCOMING_SCHEDULE_CACHE_KEY = "spinitron:upcoming-schedule"


class _ScheduleEntry(TypedDict):
    date: str
    dj_name: str | None
    title: str | None


class SpinitronUpcomingScheduleService:
    """Read-through cache over Spinitron's near-term schedule, for reservation date checks."""

    @staticmethod
    async def get_dates_for_name(db: Session, name: str) -> List[str]:
        """
        List dates (YYYY-MM-DD) in the next ~4 weeks *name* is scheduled on-air.

        *name* is matched the same way the "Reserve for" autocomplete conflates
        DJs and specialty shows: either a DJ persona resolving to this name
        (case-insensitive), or a show titled exactly this name (a specialty
        show's Spinitron title).
        """
        entries = await SpinitronUpcomingScheduleService._get_entries(db)
        needle = name.strip().lower()
        return sorted({
            entry["date"]
            for entry in entries
            if (entry["dj_name"] and entry["dj_name"].strip().lower() == needle)
            or entry["title"] == name
        })

    @staticmethod
    async def _get_entries(db: Session) -> List[_ScheduleEntry]:
        async def producer() -> dict:
            end = datetime.now(timezone.utc) + timedelta(days=SCHEDULE_WINDOW_DAYS)
            shows = await SpinitronService.fetch_shows(end)
            resolved = await SpinitronScheduleService.resolve_dj_names(db, shows)

            entries: List[_ScheduleEntry] = [
                {
                    "date": show["start"].date().isoformat(),
                    "dj_name": (
                        resolved.get(show["persona_id"]) if show["persona_id"] else None
                    ),
                    "title": show["title"],
                }
                for show in shows
            ]
            return {"entries": entries}

        data = await cache_service.fetch_cached_async(
            db, _UPCOMING_SCHEDULE_CACHE_KEY, producer, ttl_days=1
        )
        return data["entries"]
