"""Generic HTTP cache service backed by the external_api_cache DB table."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

import httpx2 as httpx
from sqlalchemy.orm import Session

from app.models.external_api_cache import ExternalApiCache

logger = logging.getLogger(__name__)


def fetch_cached(
    db: Session,
    url: str,
    *,
    headers: dict | None = None,
    ttl_days: int = 90,
) -> dict:
    """Return cached JSON for *url* if fresh; otherwise fetch, cache, and return.

    :param db: Database session.
    :param url: Full URL to GET (used as the cache key).
    :param headers: Optional HTTP request headers.
    :param ttl_days: How long a cached entry is considered fresh.
    :raises httpx.HTTPStatusError: When the upstream request returns a non-2xx status.
    """
    now = datetime.now(timezone.utc)

    entry = (
        db.query(ExternalApiCache)
        .filter(ExternalApiCache.url == url, ExternalApiCache.expires_at > now)
        .first()
    )
    if entry is not None:
        return entry.payload

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, headers=headers, follow_redirects=True)
        if resp.status_code == 429:
            retry_after = min(int(resp.headers.get("Retry-After", "5")), 10)
            logger.warning("Rate limited by %s; retrying after %ds", url, retry_after)
            time.sleep(retry_after)
            resp = client.get(url, headers=headers, follow_redirects=True)
        resp.raise_for_status()
        data: dict = resp.json()

    expires_at = now + timedelta(days=ttl_days)
    existing = db.query(ExternalApiCache).filter(ExternalApiCache.url == url).first()
    if existing is not None:
        existing.payload = data
        existing.fetched_at = now
        existing.expires_at = expires_at
    else:
        db.add(
            ExternalApiCache(url=url, payload=data, fetched_at=now, expires_at=expires_at)
        )
    db.commit()

    return data


async def fetch_cached_async(
    db: Session,
    key: str,
    producer: Callable[[], Awaitable[dict]],
    *,
    ttl_days: int = 1,
) -> dict:
    """Return cached JSON for *key* if fresh; otherwise call *producer*, cache, and return.

    Same read-check-write shape as `fetch_cached`, but calls an async *producer*
    instead of doing an HTTP GET itself — for sources like an async, paginated
    API client that `fetch_cached`'s single synchronous GET can't express.
    Reuses the same `external_api_cache` table; *key* need not be a real URL.

    :param db: Database session.
    :param key: Cache key (stored in the table's `url` column).
    :param producer: Async callable returning the JSON-serializable payload to cache on a miss.
    :param ttl_days: How long a cached entry is considered fresh.
    """
    now = datetime.now(timezone.utc)

    entry = (
        db.query(ExternalApiCache)
        .filter(ExternalApiCache.url == key, ExternalApiCache.expires_at > now)
        .first()
    )
    if entry is not None:
        return entry.payload

    data = await producer()

    expires_at = now + timedelta(days=ttl_days)
    existing = db.query(ExternalApiCache).filter(ExternalApiCache.url == key).first()
    if existing is not None:
        existing.payload = data
        existing.fetched_at = now
        existing.expires_at = expires_at
    else:
        db.add(
            ExternalApiCache(url=key, payload=data, fetched_at=now, expires_at=expires_at)
        )
    db.commit()

    return data
