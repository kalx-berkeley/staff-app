"""Spinitron upcoming on-air schedule lookups, for pass pair pre-assignment dates.

One read-through cache (~1 day TTL, via `cache_service.fetch_cached_async`) over
the next ~8 weeks of Spinitron shows and pre-provisioned future playlists.
Each entry keeps its date, its persona and its Spinitron show.

An identity (a persona, or a Specialty Music Show or Talk & Info Show) is
scheduled on a date if *either* `/shows` or `/playlists` has it that day,
since `/shows` often lists a generic placeholder for a slot that `/playlists`
already has a specific DJ's pre-provisioned playlist for. A specialty show
is told apart by its Spinitron show ID only, never by title.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, TypedDict
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.common.services import cache_service
from app.common.services.spinitron_service import SpinitronService
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_spinitron_show import SpecialtyShowSpinitronShow

SCHEDULE_WINDOW_DAYS = 56

# Bump the trailing :vN suffix whenever `_get_entries`'s producer logic or
# output shape changes -- otherwise a stale cached payload (up to ttl_days
# old) keeps getting served under the old key and looks like a regression.
_UPCOMING_SCHEDULE_CACHE_KEY = "spinitron:upcoming-schedule:v3"
_LA = ZoneInfo("America/Los_Angeles")


class _ScheduleEntry(TypedDict):
    date: str
    persona_id: Optional[int]
    spinitron_show_id: Optional[int]


class IdentitySchedule(TypedDict):
    """When an identity is on the schedule."""

    # Days the identity can be pre-assigned for: on air as itself, or (for a
    # persona) hosting a Specialty Music Show
    dates: List[str]
    # Persona only: days it hosts a Talk & Info Show instead, by show name,
    # when the pass belongs to the show
    talk_show_dates: dict[str, str]


class ScheduledIdentity(TypedDict):
    """Someone on air on a date: a persona, or a specialty show."""

    persona_id: Optional[int]
    specialty_show_id: Optional[int]


def _show_map(db: Session) -> dict[int, SpecialtyShow]:
    """Spinitron show ID -> the current specialty show it belongs to."""
    rows = (
        db.query(SpecialtyShowSpinitronShow.spinitron_show_id, SpecialtyShow)
        .join(
            SpecialtyShow, SpecialtyShow.id == SpecialtyShowSpinitronShow.specialty_show_id
        )
        .filter(SpecialtyShow.current_filter())
        .all()
    )
    return {spinitron_id: show for spinitron_id, show in rows}


class SpinitronUpcomingScheduleService:
    """Read-through cache over Spinitron's near-term schedule, for pre-assignment dates."""

    @staticmethod
    async def get_identity_schedule(
        db: Session,
        persona_id: Optional[int] = None,
        specialty_show_id: Optional[int] = None,
    ) -> IdentitySchedule:
        """
        When a persona or a specialty show is on air in the next ~8 weeks.

        :param db: Database session.
        :param persona_id: A persona, or
        :param specialty_show_id: a Specialty Music Show or Talk & Info Show.
        :returns: The dates (YYYY-MM-DD, Pacific) it can be pre-assigned for,
            and for a persona the dates it hosts a talk show instead.
        """
        entries = await SpinitronUpcomingScheduleService._get_entries(db)
        shows = _show_map(db)
        dates: set[str] = set()
        talk: dict[str, str] = {}
        for entry in entries:
            show = shows.get(entry["spinitron_show_id"])
            if specialty_show_id is not None:
                if show is not None and show.id == specialty_show_id:
                    dates.add(entry["date"])
            elif persona_id is not None and entry["persona_id"] == persona_id:
                if show is not None and show.is_talk:
                    talk[entry["date"]] = show.name
                else:
                    dates.add(entry["date"])
        # A day with a regular shift as well as a talk show is fine
        talk = {d: name for d, name in talk.items() if d not in dates}
        return {"dates": sorted(dates), "talk_show_dates": dict(sorted(talk.items()))}

    @staticmethod
    async def get_identities_for_date(db: Session, date: str) -> List[ScheduledIdentity]:
        """
        Who is on air on *date* (a YYYY-MM-DD Pacific day in the next ~8 weeks).

        A slot of a specialty show is that show, and for a Specialty Music
        Show also the slot's persona (passes can go to either). Any other slot
        is its persona. Slots with neither are left out.

        :returns: Each identity once, in schedule order.
        """
        entries = await SpinitronUpcomingScheduleService._get_entries(db)
        shows = _show_map(db)
        seen: set[tuple] = set()
        found: List[ScheduledIdentity] = []

        def add(persona_id: Optional[int], show_id: Optional[int]) -> None:
            if (persona_id, show_id) not in seen:
                seen.add((persona_id, show_id))
                found.append(
                    ScheduledIdentity(persona_id=persona_id, specialty_show_id=show_id)
                )

        for entry in entries:
            if entry["date"] != date:
                continue
            show = shows.get(entry["spinitron_show_id"])
            if show is not None:
                add(None, show.id)
            if entry["persona_id"] is not None and (show is None or not show.is_talk):
                add(entry["persona_id"], None)
        return found

    @staticmethod
    async def _get_entries(db: Session) -> List[_ScheduleEntry]:
        async def producer() -> dict:
            end = datetime.now(timezone.utc) + timedelta(days=SCHEDULE_WINDOW_DAYS)
            shows = await SpinitronService.fetch_shows(end)
            future_playlists = await SpinitronService.fetch_future_playlists()
            playlists = [p for p in future_playlists if p["start"] <= end]

            def entry(item, spinitron_show_id) -> _ScheduleEntry:
                return {
                    # Spinitron gives `start` in UTC; bucket by the station's
                    # own (Pacific) calendar day, not UTC's — otherwise a show
                    # airing anytime after ~4-5pm Pacific gets stamped with
                    # tomorrow's UTC date instead of today's.
                    "date": item["start"].astimezone(_LA).date().isoformat(),
                    "persona_id": item["persona_id"],
                    "spinitron_show_id": spinitron_show_id,
                }

            # A /shows item's id is the Spinitron show; a playlist names its show
            entries = [entry(item, item["id"]) for item in shows] + [
                entry(item, item.get("show_id")) for item in playlists
            ]
            return {"entries": entries}

        data = await cache_service.fetch_cached_async(
            db, _UPCOMING_SCHEDULE_CACHE_KEY, producer, ttl_days=1
        )
        return data["entries"]
