"""Spinitron upcoming on-air schedule lookups, for DJ pass-pair reservation dates.

One read-through cache (~1 day TTL, via `cache_service.fetch_cached_async`) over
the next ~8 weeks of Spinitron shows and pre-provisioned future playlists,
filtered by name on read — mirrors the `SpinitronShowTitlesService` pattern
used for the specialty-show autocompletes.

A DJ/show name is considered scheduled on a date if it matches *either*
`/shows` or `/playlists` — a match in only one is enough, since `/shows`
often lists a generic placeholder for a slot that `/playlists` already has
a specific DJ's pre-provisioned playlist for.
"""

from datetime import datetime, timedelta, timezone
from typing import List, TypedDict
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.services import cache_service
from app.services.spinitron_schedule_service import SpinitronScheduleService
from app.services.spinitron_service import SpinitronService

SCHEDULE_WINDOW_DAYS = 56

# Bump the trailing :vN suffix whenever `_get_entries`'s producer logic or
# output shape changes -- otherwise a stale cached payload (up to ttl_days
# old) keeps getting served under the old key and looks like a regression.
_UPCOMING_SCHEDULE_CACHE_KEY = "spinitron:upcoming-schedule:v2"
_LA = ZoneInfo("America/Los_Angeles")


class _ScheduleEntry(TypedDict):
    date: str
    dj_name: str | None
    title: str | None


class SpinitronUpcomingScheduleService:
    """Read-through cache over Spinitron's near-term schedule, for reservation date checks."""

    @staticmethod
    async def get_dates_for_name(db: Session, name: str) -> List[str]:
        """
        List dates (YYYY-MM-DD) in the next ~8 weeks *name* is scheduled on-air.

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
    async def get_names_for_date(db: Session, date: str) -> List[str]:
        """
        List DJ/specialty-show names scheduled on-air on *date* (a YYYY-MM-DD
        station calendar day, in the next ~8 weeks).

        Reverse of `get_dates_for_name`: each entry on that date contributes
        its resolved DJ name if it has one, else its Spinitron show title (a
        specialty show's exact title, for an unresolved persona).
        """
        entries = await SpinitronUpcomingScheduleService._get_entries(db)
        names = {
            (entry["dj_name"] or entry["title"])
            for entry in entries
            if entry["date"] == date and (entry["dj_name"] or entry["title"])
        }
        return sorted(names)

    @staticmethod
    async def _get_entries(db: Session) -> List[_ScheduleEntry]:
        async def producer() -> dict:
            end = datetime.now(timezone.utc) + timedelta(days=SCHEDULE_WINDOW_DAYS)
            shows = await SpinitronService.fetch_shows(end)
            future_playlists = await SpinitronService.fetch_future_playlists()
            playlists = [p for p in future_playlists if p["start"] <= end]
            resolved = await SpinitronScheduleService.resolve_dj_names(
                db, shows + playlists
            )

            entries: List[_ScheduleEntry] = [
                {
                    # Spinitron gives `start` in UTC; bucket by the station's
                    # own (Pacific) calendar day, not UTC's — otherwise a show
                    # airing anytime after ~4-5pm Pacific gets stamped with
                    # tomorrow's UTC date instead of today's.
                    "date": item["start"].astimezone(_LA).date().isoformat(),
                    "dj_name": (
                        resolved.get(item["persona_id"]) if item["persona_id"] else None
                    ),
                    "title": item["title"],
                }
                for item in shows + playlists
            ]
            return {"entries": entries}

        data = await cache_service.fetch_cached_async(
            db, _UPCOMING_SCHEDULE_CACHE_KEY, producer, ttl_days=1
        )
        return data["entries"]
