"""Spinitron API service for fetching DJ personas and other data."""

import logging
from typing import Dict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SPINITRON_API_BASE = "https://spinitron.com/api"


class SpinitronService:
    """Service for interacting with the Spinitron v2 API."""

    @staticmethod
    def _request_headers() -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.spinitron_api_key}",
            "User-Agent": f"kalx-promotions/1.0 ({settings.api_contact_url})",
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
