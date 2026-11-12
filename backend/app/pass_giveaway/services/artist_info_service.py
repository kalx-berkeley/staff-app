"""Artist info for the band popup: a Wikipedia extract and MusicBrainz links.

Each lookup is three cached GETs in a chain: the MusicBrainz artist (with its
URL relations), then its Wikidata entity's English Wikipedia sitelink, then
that page's Wikipedia summary. All three are cached in `external_api_cache`
for `cache_service.fetch_cached`'s default 90 days.

The popup is served stale-while-revalidate: it gets whatever is cached, even
if expired, and an expired artist is refreshed in a background task
(`warm_artist_info`). Saving a show's band tags runs the same task for every
tagged artist, so the popup rarely has to wait for an upstream fetch.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.common.services import cache_service
from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# MusicBrainz artist URL relation types shown as icons in the band popup, in
# the order they're shown.
ARTIST_LINK_TYPES = (
    "official homepage",
    "bandcamp",
    "discogs",
    "lyrics",
    "free streaming",
    "soundcloud",
)

# MusicBrainz allows about one request per second per client.
MUSICBRAINZ_REQUEST_INTERVAL_SECONDS = 1.0

# Artist IDs a warm-up task is currently fetching, so that several popups
# opening the same stale artist start only one refresh.
_in_flight: set[str] = set()
_in_flight_lock = threading.Lock()


@dataclass
class ArtistInfoLookup:
    """An artist's popup info, and whether any of it came from an expired cache entry."""

    info: dict = field(
        default_factory=lambda: {"extract": None, "wikipedia_url": None, "links": []}
    )
    stale: bool = False


def _headers() -> dict:
    return {
        "User-Agent": f"kalx-promotions/1.0 ({settings.api_contact_url})",
        "Accept-Encoding": "gzip, deflate",
    }


def musicbrainz_url(artist_id: str) -> str:
    """Return the MusicBrainz artist lookup URL, which is also its cache key."""
    return f"https://musicbrainz.org/ws/2/artist/{artist_id}?inc=url-rels&fmt=json"


def _artist_links(mb_data: dict) -> list[dict]:
    """Return the artist's current links of the ARTIST_LINK_TYPES types.

    Ended relations (links MusicBrainz marks as no longer valid) and anything
    that isn't an http(s) URL are skipped, as are duplicates.
    """
    links = []
    seen = set()
    for rel in mb_data.get("relations", []):
        rel_type = rel.get("type")
        url = (rel.get("url") or {}).get("resource") or ""
        if rel_type not in ARTIST_LINK_TYPES or rel.get("ended"):
            continue
        if not url.startswith(("https://", "http://")) or (rel_type, url) in seen:
            continue
        seen.add((rel_type, url))
        links.append({"type": rel_type, "url": url})
    links.sort(key=lambda link: ARTIST_LINK_TYPES.index(link["type"]))
    return links


def _wikidata_id(mb_data: dict) -> str | None:
    for rel in mb_data.get("relations", []):
        if rel.get("type") == "wikidata":
            resource = rel.get("url", {}).get("resource", "")
            m = re.search(r"wikidata\.org/wiki/(Q\d+)", resource)
            if m:
                return m.group(1)
    return None


def get_artist_info(
    db: Session, artist_id: str, *, allow_stale: bool = False
) -> ArtistInfoLookup:
    """Look up an artist's Wikipedia extract and links, through the cache.

    :param db: Database session.
    :param artist_id: MusicBrainz artist ID.
    :param allow_stale: Return expired cache entries instead of refetching
        them, and report that in `stale`. Entries that don't exist at all are
        still fetched.
    """
    lookup = ArtistInfoLookup()
    headers = _headers()

    def fetch(url: str) -> dict:
        if not allow_stale:
            return cache_service.fetch_cached(db, url, headers=headers)
        data, stale = cache_service.fetch_cached_or_stale(db, url, headers=headers)
        lookup.stale = lookup.stale or stale
        return data

    try:
        mb_data = fetch(musicbrainz_url(artist_id))
    except Exception as exc:
        logger.warning("MusicBrainz lookup failed for artist '%s': %s", artist_id, exc)
        return lookup

    lookup.info["links"] = _artist_links(mb_data)

    try:
        wikidata_id = _wikidata_id(mb_data)
        if not wikidata_id:
            return lookup

        wd_data = fetch(
            "https://www.wikidata.org/w/api.php"
            f"?action=wbgetentities&ids={wikidata_id}&props=sitelinks"
            "&sitefilter=enwiki&format=json"
        )
        entity = wd_data.get("entities", {}).get(wikidata_id, {})
        wiki_title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
        if not wiki_title:
            return lookup

        wp_data = fetch(
            "https://en.wikipedia.org/api/rest_v1/page/summary/"
            f"{wiki_title.replace(' ', '_')}"
        )
        lookup.info["extract"] = wp_data.get("extract")
        lookup.info["wikipedia_url"] = (
            wp_data.get("content_urls", {}).get("desktop", {}).get("page")
        )
    except Exception as exc:
        logger.warning("Wikipedia lookup failed for artist '%s': %s", artist_id, exc)

    return lookup


def warm_artist_info(artist_ids: list[str]) -> None:
    """Fetch and cache the popup info of every artist that isn't freshly cached.

    Runs as a background task, with its own database session. Artists whose
    MusicBrainz entry is fresh are skipped, and the MusicBrainz requests are
    spaced out to respect its rate limit. Failures are logged, not raised.

    :param artist_ids: MusicBrainz artist IDs; duplicates are ignored.
    """
    with _in_flight_lock:
        claimed = [a for a in dict.fromkeys(artist_ids) if a and a not in _in_flight]
        _in_flight.update(claimed)
    if not claimed:
        return

    db = SessionLocal()
    try:
        fetched_any = False
        for artist_id in claimed:
            try:
                if cache_service.is_fresh(db, musicbrainz_url(artist_id)):
                    continue
                if fetched_any:
                    time.sleep(MUSICBRAINZ_REQUEST_INTERVAL_SECONDS)
                get_artist_info(db, artist_id)
                fetched_any = True
            except Exception:
                db.rollback()
                logger.exception("Couldn't cache artist info for '%s'", artist_id)
    finally:
        with _in_flight_lock:
            _in_flight.difference_update(claimed)
        db.close()


def tagged_artist_ids(bands) -> list[str]:
    """Return the distinct MusicBrainz IDs of a show's band tags, in order."""
    return list(dict.fromkeys(b.musicbrainz_id for b in bands if b.musicbrainz_id))
