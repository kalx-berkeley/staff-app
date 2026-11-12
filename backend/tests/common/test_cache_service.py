"""Tests for the external API cache's stale-while-revalidate lookup."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.common.services import cache_service
from app.models.external_api_cache import ExternalApiCache

URL = "https://example.com/thing"


def _cache(db: Session, payload: dict, *, expired: bool) -> None:
    now = datetime.now(timezone.utc)
    db.add(
        ExternalApiCache(
            url=URL,
            payload=payload,
            fetched_at=now,
            expires_at=now + timedelta(days=-1 if expired else 1),
        )
    )
    db.commit()


def _record_fetches(monkeypatch) -> list[str]:
    fetched: list[str] = []

    def fake_get_json(url, headers):
        fetched.append(url)
        return {"new": True}

    monkeypatch.setattr(cache_service, "_get_json", fake_get_json)
    return fetched


def test_or_stale_returns_an_expired_entry_without_fetching(db: Session, monkeypatch):
    fetched = _record_fetches(monkeypatch)
    _cache(db, {"old": True}, expired=True)

    assert cache_service.fetch_cached_or_stale(db, URL) == ({"old": True}, True)
    assert fetched == []
    assert not cache_service.is_fresh(db, URL)


def test_or_stale_returns_a_fresh_entry_as_fresh(db: Session, monkeypatch):
    fetched = _record_fetches(monkeypatch)
    _cache(db, {"old": True}, expired=False)

    assert cache_service.fetch_cached_or_stale(db, URL) == ({"old": True}, False)
    assert fetched == []
    assert cache_service.is_fresh(db, URL)


def test_or_stale_fetches_and_caches_on_a_miss(db: Session, monkeypatch):
    fetched = _record_fetches(monkeypatch)

    assert cache_service.fetch_cached_or_stale(db, URL) == ({"new": True}, False)
    assert fetched == [URL]
    assert cache_service.is_fresh(db, URL)


def test_fetch_cached_replaces_an_expired_entry(db: Session, monkeypatch):
    fetched = _record_fetches(monkeypatch)
    _cache(db, {"old": True}, expired=True)

    assert cache_service.fetch_cached(db, URL) == {"new": True}
    assert fetched == [URL]
    assert db.query(ExternalApiCache).filter_by(url=URL).one().payload == {"new": True}
    assert cache_service.is_fresh(db, URL)
