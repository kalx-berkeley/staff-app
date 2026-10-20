"""Spinitron API service for fetching DJ personas and other data."""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, NotRequired, Optional, Set, TypedDict

import httpx2 as httpx
from sqlalchemy.orm import Session

from app.common.services import cache_service
from app.config import settings

logger = logging.getLogger(__name__)

SPINITRON_API_BASE = "https://spinitron.com/api"

_PERSONA_ID_RE = re.compile(r"/personas/(\d+)")

_PERSONAS_CACHE_KEY = "spinitron:personas"


def placeholder_persona_ids() -> Set[int]:
    """Parse SPINITRON_PLACEHOLDER_PERSONA_IDS into a set of persona IDs."""
    return {
        int(raw_id.strip())
        for raw_id in settings.spinitron_placeholder_persona_ids.split(",")
        if raw_id.strip()
    }


async def cached_persona_names(db: Session) -> Dict[int, str]:
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


class SpinitronShowItem(TypedDict):
    """A single Spinitron show, as relevant to the on-air schedule cache."""

    id: int
    start: datetime
    end: datetime
    persona_id: Optional[int]
    title: Optional[str]
    # Only on items from `/playlists`: the Spinitron show the playlist belongs
    # to, and whether it aired with no live DJ (e.g. a roboshow)
    show_id: NotRequired[Optional[int]]
    automation: NotRequired[bool]


class SpinitronSpinItem(TypedDict):
    """A single Spinitron spin (played song), as relevant to feature-show matching."""

    id: int
    start: datetime
    artist: str
    song: str
    image: Optional[str]


def dedupe_by_id(*item_lists: List[SpinitronShowItem]) -> List[SpinitronShowItem]:
    """Merge any number of item lists, keeping the first occurrence of each id.

    Used to combine a bounded `fetch_playlists` window with
    `fetch_future_playlists`, whose windows can overlap near "now".
    """
    seen: Dict[int, SpinitronShowItem] = {}
    for items in item_lists:
        for item in items:
            seen.setdefault(item["id"], item)
    return list(seen.values())


class SpinitronService:
    """Service for interacting with the Spinitron v2 API."""

    @staticmethod
    def _request_headers() -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.spinitron_api_key}",
            "User-Agent": f"kalx-staff-app/1.0 ({settings.api_contact_url})",
        }

    @staticmethod
    async def fetch_all_personas() -> Dict[int, str]:
        """
        Fetch all DJ personas from Spinitron.

        Fetches all pages using the maximum page size of 200, returning a
        mapping from Spinitron persona ID to on-air DJ name.

        :returns: Dict mapping Spinitron persona ID (int) to DJ name (str).
        :raises RuntimeError: If the Spinitron API returns an error.
        """
        if not settings.spinitron_api_key:
            logger.warning("SPINITRON_API_KEY not configured, skipping persona fetch")
            return {}

        url = f"{SPINITRON_API_BASE}/personas"
        headers = SpinitronService._request_headers()
        personas: Dict[int, str] = {}

        async with httpx.AsyncClient() as client:
            page = 1
            while True:
                try:
                    response = await client.get(
                        url,
                        headers=headers,
                        params={"count": 200, "page": page},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise RuntimeError(
                        f"Spinitron API error {e.response.status_code}: {e.response.text}"
                    ) from e
                except httpx.RequestError as e:
                    raise RuntimeError(f"Spinitron API request failed: {e}") from e

                data = response.json()
                for item in data.get("items", []):
                    persona_id = item.get("id")
                    name = item.get("name")
                    if persona_id is not None and name:
                        personas[int(persona_id)] = name

                meta = data.get("_meta", {})
                if page >= meta.get("pageCount", 1):
                    break
                page += 1

        logger.info("Fetched %d Spinitron personas", len(personas))
        return personas

    @staticmethod
    def _extract_persona_id(item: dict) -> Optional[int]:
        """Extract a persona ID from a Spinitron item.

        Prefers a direct `persona_id` field (seen on `/playlists` items);
        falls back to the first `_links.personas` href (the shape `/shows`
        items use instead).
        """
        persona_id = item.get("persona_id")
        if persona_id is not None:
            return int(persona_id)

        persona_links = item.get("_links", {}).get("personas") or []
        if persona_links:
            match = _PERSONA_ID_RE.search(persona_links[0].get("href", ""))
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    async def fetch_shows(end: datetime) -> List[SpinitronShowItem]:
        """
        Fetch Spinitron shows from now through *end*.

        This is Spinitron's live/near-term schedule grid — it only tolerates
        a `start` within about an hour of now, so it's only useful for
        "what's on now or coming up soon", not historical lookback (use
        `fetch_playlists` for that). Fetches all pages using the maximum
        page size of 200.

        :param end: Upper bound of the schedule window (used as the "end"
            query argument, formatted as UTC ISO-8601 with a numeric offset).
        :returns: List of show dicts with id, start, end, persona_id, title.
        :raises RuntimeError: If the Spinitron API returns an error.
        """
        if not settings.spinitron_api_key:
            logger.warning("SPINITRON_API_KEY not configured, skipping show fetch")
            return []

        url = f"{SPINITRON_API_BASE}/shows"
        headers = SpinitronService._request_headers()
        params: Dict[str, object] = {
            "end": end.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "count": 200,
        }
        shows: List[SpinitronShowItem] = []

        async with httpx.AsyncClient() as client:
            page = 1
            while True:
                try:
                    response = await client.get(
                        url,
                        headers=headers,
                        params={**params, "page": page},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise RuntimeError(
                        f"Spinitron API error {e.response.status_code}: {e.response.text}"
                    ) from e
                except httpx.RequestError as e:
                    raise RuntimeError(f"Spinitron API request failed: {e}") from e

                data = response.json()
                for item in data.get("items", []):
                    show_id = item.get("id")
                    start_str = item.get("start")
                    end_str = item.get("end")
                    if show_id is None or not start_str or not end_str:
                        continue

                    title = (item.get("title") or "").strip() or None

                    shows.append(
                        SpinitronShowItem(
                            id=int(show_id),
                            start=datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S%z"),
                            end=datetime.strptime(end_str, "%Y-%m-%dT%H:%M:%S%z"),
                            persona_id=SpinitronService._extract_persona_id(item),
                            title=title,
                        )
                    )

                meta = data.get("_meta", {})
                if page >= meta.get("pageCount", 1):
                    break
                page += 1

        logger.info("Fetched %d Spinitron shows", len(shows))
        return shows

    @staticmethod
    async def _fetch_playlists_pages(params: Dict[str, object]) -> List[SpinitronShowItem]:
        """Page through `/playlists` with the given query params and parse the items.

        Shared by `fetch_playlists` and `fetch_future_playlists`, which only
        differ in which query params select the window of playlists returned.
        """
        url = f"{SPINITRON_API_BASE}/playlists"
        headers = SpinitronService._request_headers()
        playlists: List[SpinitronShowItem] = []

        async with httpx.AsyncClient() as client:
            page = 1
            while True:
                try:
                    response = await client.get(
                        url,
                        headers=headers,
                        params={**params, "page": page},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise RuntimeError(
                        f"Spinitron API error {e.response.status_code}: {e.response.text}"
                    ) from e
                except httpx.RequestError as e:
                    raise RuntimeError(f"Spinitron API request failed: {e}") from e

                data = response.json()
                for item in data.get("items", []):
                    playlist_id = item.get("id")
                    start_str = item.get("start")
                    end_str = item.get("end")
                    if playlist_id is None or not start_str or not end_str:
                        continue

                    title = (item.get("title") or "").strip() or None

                    playlists.append(
                        SpinitronShowItem(
                            id=int(playlist_id),
                            start=datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S%z"),
                            end=datetime.strptime(end_str, "%Y-%m-%dT%H:%M:%S%z"),
                            persona_id=SpinitronService._extract_persona_id(item),
                            title=title,
                            show_id=(
                                int(item["show_id"])
                                if item.get("show_id") is not None
                                else None
                            ),
                            automation=bool(item.get("automation")),
                        )
                    )

                meta = data.get("_meta", {})
                if page >= meta.get("pageCount", 1):
                    break
                page += 1

        return playlists

    @staticmethod
    async def fetch_playlists(start: datetime, end: datetime) -> List[SpinitronShowItem]:
        """
        Fetch aired Spinitron playlists (historical on-air log entries) between *start* and *end*.

        Unlike `fetch_shows` (a live/near-term schedule grid), `/playlists`
        is Spinitron's log of what actually aired, so it accepts an
        arbitrary lookback window. Fetches all pages using the maximum page
        size of 200.

        :param start: Lower bound of the lookback window.
        :param end: Upper bound of the lookback window.
        :returns: List of playlist dicts with id, start, end, persona_id, title.
        :raises RuntimeError: If the Spinitron API returns an error.
        """
        if not settings.spinitron_api_key:
            logger.warning("SPINITRON_API_KEY not configured, skipping playlist fetch")
            return []

        params = {
            "start": start.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "count": 200,
        }
        playlists = await SpinitronService._fetch_playlists_pages(params)
        logger.info("Fetched %d Spinitron playlist(s)", len(playlists))
        return playlists

    @staticmethod
    async def fetch_future_playlists() -> List[SpinitronShowItem]:
        """
        Fetch all pre-provisioned future Spinitron playlists.

        Unlike `fetch_playlists`, which only returns entries that have
        actually aired, this is Spinitron's `future=1` mode: it returns
        playlists that have been pre-provisioned ahead of time for a show
        that hasn't happened yet. There's no `start`/`end` bound to pass —
        Spinitron returns everything it has. Fetches all pages using the
        maximum page size of 200.

        :returns: List of playlist dicts with id, start, end, persona_id, title.
        :raises RuntimeError: If the Spinitron API returns an error.
        """
        if not settings.spinitron_api_key:
            logger.warning(
                "SPINITRON_API_KEY not configured, skipping future playlist fetch"
            )
            return []

        params = {"future": 1, "count": 200}
        playlists = await SpinitronService._fetch_playlists_pages(params)
        logger.info("Fetched %d future Spinitron playlist(s)", len(playlists))
        return playlists

    @staticmethod
    async def _fetch_one(path: str) -> Optional[Dict[str, Any]]:
        """
        GET one Spinitron item, such as `/shows/123`.

        :returns: The item's JSON, or None if Spinitron has no such item.
        :raises RuntimeError: If the API key isn't set or the API returns an error.
        """
        if not settings.spinitron_api_key:
            raise RuntimeError("SPINITRON_API_KEY not configured")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{SPINITRON_API_BASE}{path}",
                    headers=SpinitronService._request_headers(),
                    timeout=30.0,
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"Spinitron API error {e.response.status_code}: {e.response.text}"
                ) from e
            except httpx.RequestError as e:
                raise RuntimeError(f"Spinitron API request failed: {e}") from e
        return response.json()

    @staticmethod
    async def fetch_show(show_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch one Spinitron show (its id, title, category, and so on).

        :returns: The show, or None if there's no show with that ID.
        :raises RuntimeError: If the API key isn't set or the API returns an error.
        """
        return await SpinitronService._fetch_one(f"/shows/{show_id}")

    @staticmethod
    async def fetch_playlist(playlist_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch one Spinitron playlist (including its show_id and persona_id).

        :returns: The playlist, or None if there's no playlist with that ID.
        :raises RuntimeError: If the API key isn't set or the API returns an error.
        """
        return await SpinitronService._fetch_one(f"/playlists/{playlist_id}")

    @staticmethod
    async def fetch_spins(start: datetime) -> List[SpinitronSpinItem]:
        """
        Fetch Spinitron spins (played songs) logged since *start*.

        Fetches all pages using the maximum page size of 200. Spins with a
        blank artist are skipped since there's nothing to match against.

        :param start: Lower bound of the lookback window (used as the "start"
            query argument, formatted as UTC ISO-8601 with a numeric offset).
        :returns: List of spin dicts with id, start, artist, song, and image,
            most-recent first (Spinitron's own ordering).
        :raises RuntimeError: If the Spinitron API returns an error.
        """
        if not settings.spinitron_api_key:
            logger.warning("SPINITRON_API_KEY not configured, skipping spin fetch")
            return []

        url = f"{SPINITRON_API_BASE}/spins"
        headers = SpinitronService._request_headers()
        start_param = start.strftime("%Y-%m-%dT%H:%M:%S%z")
        spins: List[SpinitronSpinItem] = []

        async with httpx.AsyncClient() as client:
            page = 1
            while True:
                try:
                    response = await client.get(
                        url,
                        headers=headers,
                        params={"start": start_param, "count": 200, "page": page},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise RuntimeError(
                        f"Spinitron API error {e.response.status_code}: {e.response.text}"
                    ) from e
                except httpx.RequestError as e:
                    raise RuntimeError(f"Spinitron API request failed: {e}") from e

                data = response.json()
                for item in data.get("items", []):
                    spin_id = item.get("id")
                    start_str = item.get("start")
                    artist = (item.get("artist") or "").strip()
                    if spin_id is None or not start_str or not artist:
                        continue

                    spins.append(
                        SpinitronSpinItem(
                            id=int(spin_id),
                            start=datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S%z"),
                            artist=artist,
                            song=(item.get("song") or "").strip(),
                            image=item.get("image") or None,
                        )
                    )

                meta = data.get("_meta", {})
                if page >= meta.get("pageCount", 1):
                    break
                page += 1

        logger.info("Fetched %d Spinitron spin(s)", len(spins))
        return spins
