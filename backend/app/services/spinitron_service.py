"""Spinitron API service for fetching DJ personas and other data."""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, TypedDict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SPINITRON_API_BASE = "https://spinitron.com/api"

_PERSONA_ID_RE = re.compile(r"/personas/(\d+)")


class SpinitronShowItem(TypedDict):
    """A single Spinitron show, as relevant to the on-air schedule cache."""

    id: int
    start: datetime
    end: datetime
    persona_id: Optional[int]


class SpinitronSpinItem(TypedDict):
    """A single Spinitron spin (played song), as relevant to feature-show matching."""

    id: int
    start: datetime
    artist: str
    song: str
    image: Optional[str]


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
    async def fetch_shows(end: datetime) -> List[SpinitronShowItem]:
        """
        Fetch Spinitron shows from now through *end*.

        Fetches all pages using the maximum page size of 200. Each item's
        first-listed persona (if any) is extracted from its `_links.personas`
        hrefs; a show is not expected to change DJ mid-slot for our purposes.

        :param end: Upper bound of the schedule window (used as the "end"
            query argument, formatted as UTC ISO-8601 with a numeric offset).
        :returns: List of show dicts with id, start, end, and persona_id.
        :raises RuntimeError: If the Spinitron API returns an error.
        """
        if not settings.spinitron_api_key:
            logger.warning("SPINITRON_API_KEY not configured, skipping show fetch")
            return []

        url = f"{SPINITRON_API_BASE}/shows"
        headers = SpinitronService._request_headers()
        end_param = end.strftime("%Y-%m-%dT%H:%M:%S%z")
        shows: List[SpinitronShowItem] = []

        async with httpx.AsyncClient() as client:
            page = 1
            while True:
                try:
                    response = await client.get(
                        url,
                        headers=headers,
                        params={"end": end_param, "count": 200, "page": page},
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

                    persona_id = None
                    persona_links = item.get("_links", {}).get("personas") or []
                    if persona_links:
                        match = _PERSONA_ID_RE.search(persona_links[0].get("href", ""))
                        if match:
                            persona_id = int(match.group(1))

                    shows.append(
                        SpinitronShowItem(
                            id=int(show_id),
                            start=datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S%z"),
                            end=datetime.strptime(end_str, "%Y-%m-%dT%H:%M:%S%z"),
                            persona_id=persona_id,
                        )
                    )

                meta = data.get("_meta", {})
                if page >= meta.get("pageCount", 1):
                    break
                page += 1

        logger.info("Fetched %d Spinitron shows", len(shows))
        return shows

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

    @staticmethod
    async def fetch_persona_name(persona_id: int) -> Optional[str]:
        """
        Fetch a single Spinitron persona's on-air DJ name.

        :param persona_id: Spinitron persona ID.
        :returns: The persona's name, or None if it has no name.
        :raises RuntimeError: If the Spinitron API returns an error.
        """
        if not settings.spinitron_api_key:
            logger.warning("SPINITRON_API_KEY not configured, skipping persona fetch")
            return None

        url = f"{SPINITRON_API_BASE}/personas/{persona_id}"
        headers = SpinitronService._request_headers()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"Spinitron API error {e.response.status_code}: {e.response.text}"
                ) from e
            except httpx.RequestError as e:
                raise RuntimeError(f"Spinitron API request failed: {e}") from e

        return response.json().get("name")
