"""Tests for SpinitronScheduleService and the GET /api/dj/on-air endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.job_log import JobLog
from app.models.spinitron_playlist import SpinitronPlaylist
from app.models.spinitron_show import SpinitronShow
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.services.spinitron_schedule_service import SpinitronScheduleService
from app.services.spinitron_service import SpinitronShowItem

DJ_STUDIO_IP = "192.168.1.100"  # within default dj_studio_network 192.168.1.0/24


@pytest.fixture
def test_promotions_staff(db: Session):
    staff = Staff(email="promotions@test.com", name="Test Promotions", phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


def _show(
    id: int, start: datetime, end: datetime, persona_id: int | None
) -> SpinitronShowItem:
    return SpinitronShowItem(id=id, start=start, end=end, persona_id=persona_id, title=None)


def _no_playlists(*args, **kwargs):
    """A stand-in for fetch_playlists/fetch_future_playlists that returns nothing."""
    return []


class TestSyncSchedule:
    def _patch_no_playlists(self, monkeypatch):
        """Most sync_schedule tests only care about shows; keep playlist fetches empty."""

        async def fake_fetch_playlists(start, end):
            return []

        async def fake_fetch_future_playlists():
            return []

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_playlists",
            fake_fetch_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_future_playlists",
            fake_fetch_future_playlists,
        )

    async def test_no_ops_when_not_configured(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", None)

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 0
        assert db.query(SpinitronShow).count() == 0
        assert db.query(SpinitronPlaylist).count() == 0
        assert (
            db.query(JobLog).filter(JobLog.job_id == "spinitron_schedule_sync").count() == 0
        )

    async def test_uses_staff_dj_name_for_single_persona_match(
        self, db: Session, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        self._patch_no_playlists(monkeypatch)
        now = datetime.now(timezone.utc)

        staff = Staff(
            email="dj@example.com",
            name="DJ Person",
            phone="5555555555",
            spinitron_ids=[169765],
            dj_name="Murky Logic",
        )
        db.add(staff)
        db.commit()

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), 169765)]

        async def fake_fetch_all_personas():
            raise AssertionError("should not call the persona API when Staff has the name")

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_all_personas",
            fake_fetch_all_personas,
        )

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 1
        row = db.query(SpinitronShow).one()
        assert row.dj_name == "Murky Logic"
        assert row.persona_id == 169765
        assert (
            db.query(JobLog).filter(JobLog.job_id == "spinitron_schedule_sync").count() == 1
        )

    async def test_falls_back_to_persona_api_when_staff_has_multiple_ids(
        self, db: Session, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        self._patch_no_playlists(monkeypatch)
        now = datetime.now(timezone.utc)

        staff = Staff(
            email="dj@example.com",
            name="DJ Person",
            phone="5555555555",
            spinitron_ids=[111, 222],
            dj_name="Name A, Name B",
        )
        db.add(staff)
        db.commit()

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), 111)]

        async def fake_fetch_all_personas():
            return {111: "Resolved From API"}

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_all_personas",
            fake_fetch_all_personas,
        )

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 1
        row = db.query(SpinitronShow).one()
        assert row.dj_name == "Resolved From API"

    async def test_falls_back_to_persona_api_when_no_staff_match(
        self, db: Session, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        self._patch_no_playlists(monkeypatch)
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), 999)]

        async def fake_fetch_all_personas():
            return {999: "API Resolved DJ"}

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_all_personas",
            fake_fetch_all_personas,
        )

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 1
        assert db.query(SpinitronShow).one().dj_name == "API Resolved DJ"

    async def test_show_with_no_persona_has_no_dj_name(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        self._patch_no_playlists(monkeypatch)
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), None)]

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 1
        assert db.query(SpinitronShow).one().dj_name is None

    async def test_placeholder_persona_stores_no_dj_name(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        monkeypatch.setattr(settings, "spinitron_placeholder_persona_ids", "176287,193517")
        self._patch_no_playlists(monkeypatch)
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), 176287)]

        async def fake_fetch_all_personas():
            raise AssertionError("should not resolve a name for a placeholder persona")

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_all_personas",
            fake_fetch_all_personas,
        )

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 1
        row = db.query(SpinitronShow).one()
        assert row.dj_name is None
        assert row.persona_id == 176287

    async def test_placeholder_persona_ignores_staff_shortcut_too(
        self, db: Session, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        monkeypatch.setattr(settings, "spinitron_placeholder_persona_ids", "176287")
        self._patch_no_playlists(monkeypatch)
        now = datetime.now(timezone.utc)

        staff = Staff(
            email="trainee@example.com",
            name="Whoever Is Training",
            phone="5555555555",
            spinitron_ids=[176287],
            dj_name="DJ Trainee",
        )
        db.add(staff)
        db.commit()

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), 176287)]

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )

        await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert db.query(SpinitronShow).one().dj_name is None

    async def test_sync_replaces_existing_rows(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        self._patch_no_playlists(monkeypatch)
        now = datetime.now(timezone.utc)

        db.add(
            SpinitronShow(
                id=999,
                start=now - timedelta(days=1),
                end=now - timedelta(days=1) + timedelta(hours=1),
                dj_name="Stale DJ",
                fetched_at=now - timedelta(days=1),
            )
        )
        db.add(
            SpinitronPlaylist(
                id=888,
                start=now - timedelta(days=1),
                end=now - timedelta(days=1) + timedelta(hours=1),
                dj_name="Stale Playlist DJ",
                fetched_at=now - timedelta(days=1),
            )
        )
        db.commit()

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), None)]

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )

        await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        show_rows = db.query(SpinitronShow).all()
        assert len(show_rows) == 1
        assert show_rows[0].id == 1
        assert db.query(SpinitronPlaylist).count() == 0

    async def test_playlists_are_fetched_and_cached_alongside_shows(
        self, db: Session, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), None)]

        async def fake_fetch_playlists(start, end):
            return [_show(2, now - timedelta(minutes=10), now + timedelta(minutes=20), 42)]

        async def fake_fetch_future_playlists():
            return [_show(3, now + timedelta(hours=2), now + timedelta(hours=3), None)]

        async def fake_fetch_all_personas():
            return {42: "Wolfman"}

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_playlists",
            fake_fetch_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_future_playlists",
            fake_fetch_future_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_all_personas",
            fake_fetch_all_personas,
        )

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 3
        assert db.query(SpinitronShow).count() == 1
        playlist_rows = {row.id: row for row in db.query(SpinitronPlaylist).all()}
        assert set(playlist_rows) == {2, 3}
        assert playlist_rows[2].dj_name == "Wolfman"

    async def test_dedupes_overlapping_past_and_future_playlist_fetches(
        self, db: Session, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return []

        async def fake_fetch_playlists(start, end):
            return [_show(5, now, now + timedelta(hours=1), None)]

        async def fake_fetch_future_playlists():
            # Same playlist id as the "past" window call, since its window
            # can overlap with the future=1 call near "now".
            return [_show(5, now, now + timedelta(hours=1), None)]

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_playlists",
            fake_fetch_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_future_playlists",
            fake_fetch_future_playlists,
        )

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 1
        assert db.query(SpinitronPlaylist).count() == 1

    async def test_future_playlists_beyond_hours_ahead_are_not_cached(
        self, db: Session, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return []

        async def fake_fetch_playlists(start, end):
            return []

        async def fake_fetch_future_playlists():
            return [
                _show(6, now + timedelta(hours=1), now + timedelta(hours=2), None),
                _show(7, now + timedelta(days=5), now + timedelta(days=5, hours=1), None),
            ]

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_playlists",
            fake_fetch_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_future_playlists",
            fake_fetch_future_playlists,
        )

        await SpinitronScheduleService.sync_schedule(
            db, trigger="scheduled", hours_ahead=12
        )

        assert [row.id for row in db.query(SpinitronPlaylist).all()] == [6]


class TestPlaceholderPersonaIds:
    def test_parses_comma_separated_ids(self, monkeypatch):
        monkeypatch.setattr(
            settings, "spinitron_placeholder_persona_ids", " 176287, 193517 ,169919"
        )
        assert SpinitronScheduleService._placeholder_persona_ids() == {
            176287,
            193517,
            169919,
        }

    def test_empty_setting_yields_empty_set(self, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_placeholder_persona_ids", "")
        assert SpinitronScheduleService._placeholder_persona_ids() == set()


class TestCachedPersonaNames:
    async def test_one_bulk_fetch_resolves_every_distinct_unresolved_persona(
        self, db: Session, monkeypatch
    ):
        now = datetime.now(timezone.utc)
        shows = [
            _show(1, now, now + timedelta(hours=1), 111),
            _show(2, now, now + timedelta(hours=1), 222),
            _show(3, now, now + timedelta(hours=1), 111),  # same persona again
        ]

        calls = []

        async def fake_fetch_all_personas():
            calls.append(1)
            return {111: "DJ One", 222: "DJ Two"}

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_all_personas",
            fake_fetch_all_personas,
        )

        resolved = await SpinitronScheduleService.resolve_dj_names(db, shows)

        assert resolved == {111: "DJ One", 222: "DJ Two"}
        assert len(calls) == 1

    async def test_second_lookup_is_served_from_the_week_long_cache(
        self, db: Session, monkeypatch
    ):
        now = datetime.now(timezone.utc)
        calls = []

        async def fake_fetch_all_personas():
            calls.append(1)
            return {333: "DJ Three"}

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_all_personas",
            fake_fetch_all_personas,
        )

        first = await SpinitronScheduleService.resolve_dj_names(
            db, [_show(1, now, now + timedelta(hours=1), 333)]
        )
        second = await SpinitronScheduleService.resolve_dj_names(
            db, [_show(2, now, now + timedelta(hours=1), 333)]
        )

        assert first == {333: "DJ Three"}
        assert second == {333: "DJ Three"}
        assert len(calls) == 1

    async def test_no_bulk_fetch_when_nothing_needs_resolving(
        self, db: Session, monkeypatch
    ):
        now = datetime.now(timezone.utc)

        async def fake_fetch_all_personas():
            raise AssertionError(
                "should not fetch personas when there's nothing to resolve"
            )

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_all_personas",
            fake_fetch_all_personas,
        )

        resolved = await SpinitronScheduleService.resolve_dj_names(
            db, [_show(1, now, now + timedelta(hours=1), None)]
        )

        assert resolved == {}


class TestOnAirEndpoint:
    def test_no_shows_returns_all_none(self, client: TestClient):
        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP})
        assert response.status_code == 200
        assert response.json() == {
            "current_dj_name": None,
            "current_show_ends_at": None,
            "next_dj_name": None,
        }

    def test_returns_current_and_next_dj(self, client: TestClient, db: Session):
        now = datetime.now(timezone.utc)
        db.add(
            SpinitronShow(
                id=1,
                start=now - timedelta(minutes=30),
                end=now + timedelta(minutes=30),
                dj_name="Current DJ",
                fetched_at=now,
            )
        )
        db.add(
            SpinitronShow(
                id=2,
                start=now + timedelta(minutes=30),
                end=now + timedelta(minutes=90),
                dj_name="Next DJ",
                fetched_at=now,
            )
        )
        db.commit()

        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP})
        assert response.status_code == 200
        data = response.json()
        assert data["current_dj_name"] == "Current DJ"
        assert data["next_dj_name"] == "Next DJ"
        assert data["current_show_ends_at"] is not None

    def test_between_shows_returns_only_next(self, client: TestClient, db: Session):
        now = datetime.now(timezone.utc)
        db.add(
            SpinitronShow(
                id=1,
                start=now - timedelta(hours=2),
                end=now - timedelta(hours=1),
                dj_name="Past DJ",
                fetched_at=now,
            )
        )
        db.add(
            SpinitronShow(
                id=2,
                start=now + timedelta(minutes=30),
                end=now + timedelta(minutes=90),
                dj_name="Upcoming DJ",
                fetched_at=now,
            )
        )
        db.commit()

        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP})
        data = response.json()
        assert data["current_dj_name"] is None
        assert data["current_show_ends_at"] is None
        assert data["next_dj_name"] == "Upcoming DJ"

    def test_requires_dj_access(self, client: TestClient):
        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": "8.8.8.8"})
        assert response.status_code == 400

    def test_playlist_preferred_over_show_for_current(
        self, client: TestClient, db: Session
    ):
        """A pre-provisioned playlist for the current slot beats the generic show."""
        now = datetime.now(timezone.utc)
        db.add(
            SpinitronShow(
                id=1,
                start=now - timedelta(minutes=30),
                end=now + timedelta(minutes=30),
                dj_name="DJ Trainee",
                fetched_at=now,
            )
        )
        db.add(
            SpinitronPlaylist(
                id=1,
                start=now - timedelta(minutes=30),
                end=now + timedelta(minutes=30),
                dj_name="Wolfman",
                fetched_at=now,
            )
        )
        db.commit()

        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP})
        assert response.json()["current_dj_name"] == "Wolfman"

    def test_falls_back_to_show_when_no_current_playlist(
        self, client: TestClient, db: Session
    ):
        now = datetime.now(timezone.utc)
        db.add(
            SpinitronShow(
                id=1,
                start=now - timedelta(minutes=30),
                end=now + timedelta(minutes=30),
                dj_name="Show Only DJ",
                fetched_at=now,
            )
        )
        db.commit()

        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP})
        assert response.json()["current_dj_name"] == "Show Only DJ"

    def test_playlist_only_current_with_no_show(self, client: TestClient, db: Session):
        now = datetime.now(timezone.utc)
        db.add(
            SpinitronPlaylist(
                id=1,
                start=now - timedelta(minutes=30),
                end=now + timedelta(minutes=30),
                dj_name="Playlist Only DJ",
                fetched_at=now,
            )
        )
        db.commit()

        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP})
        assert response.json()["current_dj_name"] == "Playlist Only DJ"

    def test_next_prefers_playlist_on_exact_tie(self, client: TestClient, db: Session):
        now = datetime.now(timezone.utc)
        next_start = now + timedelta(minutes=30)
        db.add(
            SpinitronShow(
                id=1,
                start=next_start,
                end=next_start + timedelta(hours=1),
                dj_name="DJ Trainee",
                fetched_at=now,
            )
        )
        db.add(
            SpinitronPlaylist(
                id=1,
                start=next_start,
                end=next_start + timedelta(hours=1),
                dj_name="Wolfman",
                fetched_at=now,
            )
        )
        db.commit()

        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP})
        assert response.json()["next_dj_name"] == "Wolfman"

    def test_next_picks_whichever_source_starts_first(
        self, client: TestClient, db: Session
    ):
        now = datetime.now(timezone.utc)
        db.add(
            SpinitronPlaylist(
                id=1,
                start=now + timedelta(hours=2),
                end=now + timedelta(hours=3),
                dj_name="Later Playlist DJ",
                fetched_at=now,
            )
        )
        db.add(
            SpinitronShow(
                id=1,
                start=now + timedelta(minutes=30),
                end=now + timedelta(hours=1),
                dj_name="Sooner Show DJ",
                fetched_at=now,
            )
        )
        db.commit()

        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP})
        assert response.json()["next_dj_name"] == "Sooner Show DJ"

    def test_duplicate_current_playlists_return_exactly_one(
        self, client: TestClient, db: Session
    ):
        """Two DJs mistakenly scheduling overlapping playlists shouldn't 500 -- just pick one."""
        now = datetime.now(timezone.utc)
        db.add(
            SpinitronPlaylist(
                id=1,
                start=now - timedelta(minutes=30),
                end=now + timedelta(minutes=30),
                dj_name="First Mistaken DJ",
                fetched_at=now,
            )
        )
        db.add(
            SpinitronPlaylist(
                id=2,
                start=now - timedelta(minutes=20),
                end=now + timedelta(minutes=40),
                dj_name="Second Mistaken DJ",
                fetched_at=now,
            )
        )
        db.commit()

        response = client.get("/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP})
        assert response.status_code == 200
        assert response.json()["current_dj_name"] in (
            "First Mistaken DJ",
            "Second Mistaken DJ",
        )


class TestManualSyncJob:
    def test_reports_not_configured_when_no_api_key(
        self, client: TestClient, test_promotions_staff, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", None)

        response = client.post(
            "/api/admin/jobs/spinitron_schedule_sync/run",
            headers={"X-Forwarded-User": test_promotions_staff.email},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not configured" in data["message"]

    def test_runs_when_configured(
        self, client: TestClient, test_promotions_staff, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), None)]

        async def fake_fetch_playlists(start, end):
            return []

        async def fake_fetch_future_playlists():
            return []

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_playlists",
            fake_fetch_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_future_playlists",
            fake_fetch_future_playlists,
        )

        response = client.post(
            "/api/admin/jobs/spinitron_schedule_sync/run",
            headers={"X-Forwarded-User": test_promotions_staff.email},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "1" in data["message"]

    def test_appears_in_job_statuses(self, client: TestClient, test_promotions_staff):
        response = client.get(
            "/api/admin/job-statuses",
            headers={"X-Forwarded-User": test_promotions_staff.email},
        )

        assert response.status_code == 200
        job_ids = {job["id"] for job in response.json()}
        assert "spinitron_schedule_sync" in job_ids
