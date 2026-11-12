"""Tests for the band popup's artist info cache warm-up."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.external_api_cache import ExternalApiCache
from app.pass_giveaway.services import artist_info_service

# Imported before the autouse `artist_info_warmups` fixture replaces it.
from app.pass_giveaway.services.artist_info_service import (
    musicbrainz_url,
    warm_artist_info,
)
from tests.conftest import TestingSessionLocal

WIKIDATA_URL = (
    "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q1"
    "&props=sitelinks&sitefilter=enwiki&format=json"
)
WIKIPEDIA_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/Wolf_Parade"

RESPONSES = {
    WIKIDATA_URL: {"entities": {"Q1": {"sitelinks": {"enwiki": {"title": "Wolf Parade"}}}}},
    WIKIPEDIA_URL: {
        "extract": "Wolf Parade is a band.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Wolf_Parade"}},
    },
}


def _mb(wikidata: bool = True) -> dict:
    rels = [{"type": "bandcamp", "url": {"resource": "https://wp.bandcamp.com"}}]
    if wikidata:
        rels.append(
            {"type": "wikidata", "url": {"resource": "https://www.wikidata.org/wiki/Q1"}}
        )
    return {"relations": rels}


@pytest.fixture
def fetches(monkeypatch) -> list[str]:
    """Serve canned upstream responses and record every URL fetched."""
    fetched: list[str] = []

    def fake_get_json(url, headers):
        fetched.append(url)
        if url.startswith("https://musicbrainz.org/"):
            if "broken" in url:
                raise RuntimeError("MusicBrainz is down")
            return _mb(wikidata="nowiki" not in url)
        return RESPONSES[url]

    monkeypatch.setattr("app.common.services.cache_service._get_json", fake_get_json)
    monkeypatch.setattr(artist_info_service, "SessionLocal", TestingSessionLocal)
    return fetched


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr(artist_info_service.time, "sleep", slept.append)
    return slept


def _cache(db: Session, url: str, payload: dict, *, expired: bool) -> None:
    now = datetime.now(timezone.utc)
    db.add(
        ExternalApiCache(
            url=url,
            payload=payload,
            fetched_at=now,
            expires_at=now + timedelta(days=-1 if expired else 1),
        )
    )
    db.commit()


def test_warm_caches_the_whole_chain_for_uncached_artists(db: Session, fetches, sleeps):
    """MusicBrainz, Wikidata and Wikipedia are fetched and cached for a new artist."""
    warm_artist_info(["wolf"])

    assert fetches == [musicbrainz_url("wolf"), WIKIDATA_URL, WIKIPEDIA_URL]
    info = artist_info_service.get_artist_info(db, "wolf").info
    assert info["extract"] == "Wolf Parade is a band."
    assert len(fetches) == 3  # served from the cache the second time


def test_warm_skips_fresh_artists_and_refreshes_expired_ones(db: Session, fetches, sleeps):
    """Only artists without a fresh MusicBrainz entry are fetched."""
    _cache(db, musicbrainz_url("fresh"), _mb(wikidata=False), expired=False)
    _cache(db, musicbrainz_url("old-nowiki"), {"relations": []}, expired=True)

    warm_artist_info(["fresh", "old-nowiki"])

    assert fetches == [musicbrainz_url("old-nowiki")]
    db.expire_all()
    row = db.query(ExternalApiCache).filter_by(url=musicbrainz_url("old-nowiki")).one()
    assert row.payload == _mb(wikidata=False)


def test_warm_spaces_out_musicbrainz_requests(db: Session, fetches, sleeps):
    """It waits between artists it fetches, but not before the first or for skipped ones."""
    _cache(db, musicbrainz_url("fresh"), {"relations": []}, expired=False)

    warm_artist_info(["a-nowiki", "fresh", "b-nowiki", "a-nowiki"])

    assert fetches == [musicbrainz_url("a-nowiki"), musicbrainz_url("b-nowiki")]
    assert sleeps == [artist_info_service.MUSICBRAINZ_REQUEST_INTERVAL_SECONDS]


def test_warm_keeps_going_after_a_failed_artist(db: Session, fetches, sleeps):
    """An upstream failure is logged, and the other artists are still cached."""
    warm_artist_info(["broken", "ok-nowiki"])

    assert fetches == [musicbrainz_url("broken"), musicbrainz_url("ok-nowiki")]
    assert (
        db.query(ExternalApiCache).filter_by(url=musicbrainz_url("broken")).first() is None
    )
    assert artist_info_service._in_flight == set()


def test_warm_skips_artists_already_being_fetched(db: Session, fetches, sleeps):
    """A refresh already in progress for an artist isn't started again."""
    artist_info_service._in_flight.add("busy")
    try:
        warm_artist_info(["busy"])
    finally:
        artist_info_service._in_flight.discard("busy")

    assert fetches == []
