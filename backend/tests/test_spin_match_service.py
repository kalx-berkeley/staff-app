"""Tests for SpinMatchService and the GET/POST /api/dj/spin-matches endpoints."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.dismissed_spin_match import DismissedSpinMatch
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.show_band import ShowBand
from app.models.spinitron_spin_cache import SpinitronSpinCache
from app.models.venue import Venue
from app.services.spin_match_service import SpinMatchService
from app.services.spinitron_service import SpinitronSpinItem

DJ_STUDIO_IP = "192.168.1.100"  # within default dj_studio_network 192.168.1.0/24


def _spin(
    id: int, artist: str, song: str = "Some Song", image: str | None = None
) -> SpinitronSpinItem:
    return SpinitronSpinItem(
        id=id, start=datetime.now(timezone.utc), artist=artist, song=song, image=image
    )


@pytest.fixture
def test_venue(db: Session):
    venue = Venue(name="Test Venue", address="123 Test St")
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def _show_with_available_pair(
    db: Session, venue, event_name: str, band_name: str | None = None
) -> Show:
    show = Show(
        event_name=event_name,
        venue_id=venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add(show)
    db.flush()
    if band_name:
        db.add(
            ShowBand(
                show_id=show.id,
                musicbrainz_id="fake-mbid",
                band_name=band_name,
                start_pos=0,
                end_pos=10,
            )
        )
    db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    db.commit()
    db.refresh(show)
    return show


class TestGetCachedSpins:
    async def test_fetches_and_caches_when_no_row_exists(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        calls = []

        async def fake_fetch_spins(start):
            calls.append(start)
            return [_spin(1, "Murcof")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        spins = await SpinMatchService._get_cached_spins(db)

        assert len(calls) == 1
        assert spins == [{
            "id": 1,
            "start": spins[0]["start"],
            "artist": "Murcof",
            "song": "Some Song",
            "image": None,
        }]
        assert db.query(SpinitronSpinCache).count() == 1

    async def test_reuses_fresh_cache_without_refetching(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        db.add(
            SpinitronSpinCache(
                id=1,
                fetched_at=datetime.now(timezone.utc),
                spins=[{
                    "id": 1,
                    "start": "x",
                    "artist": "Cached Artist",
                    "song": "s",
                    "image": None,
                }],
            )
        )
        db.commit()

        async def fake_fetch_spins(start):
            raise AssertionError("should not refetch while cache is fresh")

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        spins = await SpinMatchService._get_cached_spins(db)
        assert spins[0]["artist"] == "Cached Artist"

    async def test_refetches_when_cache_is_stale(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        db.add(
            SpinitronSpinCache(
                id=1,
                fetched_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                spins=[{
                    "id": 1,
                    "start": "x",
                    "artist": "Stale Artist",
                    "song": "s",
                    "image": None,
                }],
            )
        )
        db.commit()

        async def fake_fetch_spins(start):
            return [_spin(2, "Fresh Artist")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        spins = await SpinMatchService._get_cached_spins(db)
        assert spins == [{
            "id": 2,
            "start": spins[0]["start"],
            "artist": "Fresh Artist",
            "song": "Some Song",
            "image": None,
        }]


class TestGetCurrentMatches:
    async def test_no_ops_when_not_configured(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", None)
        assert await SpinMatchService.get_current_matches(db) == []

    async def test_matches_tagged_band(self, db: Session, monkeypatch, test_venue):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        show = _show_with_available_pair(db, test_venue, "Some Show", band_name="Murcof")

        async def fake_fetch_spins(start):
            return [_spin(101, "Murcof", song="Cielo", image="http://example.com/x.jpg")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        matches = await SpinMatchService.get_current_matches(db)

        assert len(matches) == 1
        assert matches[0].spin_id == 101
        assert matches[0].artist == "Murcof"
        assert matches[0].song == "Cielo"
        assert matches[0].image == "http://example.com/x.jpg"
        assert matches[0].show.id == show.id
        assert matches[0].show.venue.name == "Test Venue"
        # Nothing is recorded just from computing the match.
        assert db.query(DismissedSpinMatch).count() == 0

    async def test_same_spin_match_returned_again_until_dismissed(
        self, db: Session, monkeypatch, test_venue
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        _show_with_available_pair(db, test_venue, "Some Show", band_name="Murcof")

        async def fake_fetch_spins(start):
            return [_spin(101, "Murcof")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        first = await SpinMatchService.get_current_matches(db)
        assert len(first) == 1

        # Force a cache refresh so the same spin is fetched from Spinitron
        # again, simulating it still being inside the 15-minute lookback.
        cache_row = db.query(SpinitronSpinCache).one()
        cache_row.fetched_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

        second = await SpinMatchService.get_current_matches(db)
        assert len(second) == 1
        assert second[0].spin_id == 101

    async def test_dismissed_match_stops_being_returned(
        self, db: Session, monkeypatch, test_venue
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        show = _show_with_available_pair(db, test_venue, "Some Show", band_name="Murcof")

        async def fake_fetch_spins(start):
            return [_spin(101, "Murcof")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        first = await SpinMatchService.get_current_matches(db)
        assert len(first) == 1

        SpinMatchService.dismiss(db, spin_id=101, show_id=show.id)

        # Force a cache refresh so the spin is fetched again, same as above.
        cache_row = db.query(SpinitronSpinCache).one()
        cache_row.fetched_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

        second = await SpinMatchService.get_current_matches(db)
        assert second == []

    async def test_dismissing_one_matched_show_leaves_other_showing(
        self, db: Session, monkeypatch, test_venue
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        show_a = _show_with_available_pair(db, test_venue, "Show A", band_name="Murcof")
        show_b = _show_with_available_pair(db, test_venue, "Show B", band_name="Murcof")

        async def fake_fetch_spins(start):
            return [_spin(101, "Murcof")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        first = await SpinMatchService.get_current_matches(db)
        assert {m.show.id for m in first} == {show_a.id, show_b.id}

        SpinMatchService.dismiss(db, spin_id=101, show_id=show_a.id)

        cache_row = db.query(SpinitronSpinCache).one()
        cache_row.fetched_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

        second = await SpinMatchService.get_current_matches(db)
        assert len(second) == 1
        assert second[0].show.id == show_b.id

    async def test_no_match_when_no_show_has_available_pairs(
        self, db: Session, monkeypatch, test_venue
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        show = Show(
            event_name="Murcof show",
            venue_id=test_venue.id,
            show_date=date(2024, 12, 31),
            show_time=time(20, 0),
            age_restriction="all_ages",
            wheelchair_accessible=True,
            num_pass_pairs=2,
            status="published",
        )
        db.add(show)
        db.flush()
        db.add(
            ShowBand(
                show_id=show.id,
                musicbrainz_id="fake-mbid",
                band_name="Murcof",
                start_pos=0,
                end_pos=6,
            )
        )
        # No available Pass rows for this show.
        db.commit()

        async def fake_fetch_spins(start):
            return [_spin(101, "Murcof")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        assert await SpinMatchService.get_current_matches(db) == []

    async def test_unrelated_artist_does_not_match(
        self, db: Session, monkeypatch, test_venue
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        _show_with_available_pair(db, test_venue, "Some Show", band_name="Murcof")

        async def fake_fetch_spins(start):
            return [_spin(101, "Ana Tijoux")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        assert await SpinMatchService.get_current_matches(db) == []

    async def test_multi_word_artist_matches_via_event_name_fallback(
        self, db: Session, monkeypatch, test_venue
    ):
        """An untagged show falls back to fuzzy-matching event_name, same as
        feature_bin_service and kalx_live_service."""
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        show = _show_with_available_pair(db, test_venue, "Ana Tijoux w/ openers")

        async def fake_fetch_spins(start):
            return [_spin(101, "Ana Tijoux")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        matches = await SpinMatchService.get_current_matches(db)
        assert len(matches) == 1
        assert matches[0].show.id == show.id

    async def test_single_word_artist_matches_short_event_name(
        self, db: Session, monkeypatch, test_venue
    ):
        """Single-word artists get the same event-name fallback added for
        feature-bin/KALX Live in 53be60b — previously this was skipped
        entirely for Spinitron spins."""
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        show = _show_with_available_pair(db, test_venue, "Trough w/ openers")

        async def fake_fetch_spins(start):
            return [_spin(101, "Trough")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        matches = await SpinMatchService.get_current_matches(db)
        assert len(matches) == 1
        assert matches[0].show.id == show.id

    async def test_single_word_artist_does_not_match_coincidental_surname(
        self, db: Session, monkeypatch, test_venue
    ):
        """A single-word artist ("Solomon") shouldn't match a long event name
        that happens to contain that word as part of an unrelated name —
        same guard as feature_bin_service/kalx_live_service."""
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        _show_with_available_pair(db, test_venue, "Elori Saxl and Henry Solomon")

        async def fake_fetch_spins(start):
            return [_spin(101, "Solomon")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        assert await SpinMatchService.get_current_matches(db) == []


class TestDismiss:
    def test_is_idempotent(self, db: Session, test_venue):
        show = _show_with_available_pair(db, test_venue, "Some Show", band_name="Murcof")

        SpinMatchService.dismiss(db, spin_id=101, show_id=show.id)
        SpinMatchService.dismiss(db, spin_id=101, show_id=show.id)

        assert db.query(DismissedSpinMatch).count() == 1


class TestSpinMatchesEndpoint:
    def test_requires_dj_access(self, client: TestClient):
        response = client.get(
            "/api/dj/spin-matches", headers={"X-Forwarded-For": "8.8.8.8"}
        )
        assert response.status_code == 400

    def test_returns_matches_as_json(
        self, db: Session, client: TestClient, monkeypatch, test_venue
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        show = _show_with_available_pair(db, test_venue, "Some Show", band_name="Murcof")

        async def fake_fetch_spins(start):
            return [_spin(101, "Murcof", song="Cielo", image="http://example.com/x.jpg")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        response = client.get(
            "/api/dj/spin-matches", headers={"X-Forwarded-For": DJ_STUDIO_IP}
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["spin_id"] == 101
        assert body[0]["artist"] == "Murcof"
        assert body[0]["show"]["id"] == show.id
        assert body[0]["show"]["venue_name"] == "Test Venue"
        assert body[0]["show"]["event_name"] == "Some Show"


class TestDismissSpinMatchEndpoint:
    def test_requires_dj_access(self, client: TestClient):
        response = client.post(
            "/api/dj/spin-matches/101/dismiss",
            params={"show_id": 1},
            headers={"X-Forwarded-For": "8.8.8.8"},
        )
        assert response.status_code == 400

    def test_dismiss_clears_match_from_next_poll(
        self, db: Session, client: TestClient, monkeypatch, test_venue
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        show = _show_with_available_pair(db, test_venue, "Some Show", band_name="Murcof")

        async def fake_fetch_spins(start):
            return [_spin(101, "Murcof")]

        monkeypatch.setattr(
            "app.services.spin_match_service.SpinitronService.fetch_spins", fake_fetch_spins
        )

        first = client.get(
            "/api/dj/spin-matches", headers={"X-Forwarded-For": DJ_STUDIO_IP}
        )
        assert len(first.json()) == 1

        dismiss_response = client.post(
            f"/api/dj/spin-matches/101/dismiss",
            params={"show_id": show.id},
            headers={"X-Forwarded-For": DJ_STUDIO_IP},
        )
        assert dismiss_response.status_code == 204

        cache_row = db.query(SpinitronSpinCache).one()
        cache_row.fetched_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

        second = client.get(
            "/api/dj/spin-matches", headers={"X-Forwarded-For": DJ_STUDIO_IP}
        )
        assert second.json() == []
