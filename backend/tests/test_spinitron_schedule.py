"""Tests for SpinitronScheduleService and the GET /api/dj/on-air endpoint."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.job_log import JobLog
from app.models.spinitron_show import SpinitronShow
from app.models.staff import Staff
from app.services.spinitron_schedule_service import SpinitronScheduleService
from app.services.spinitron_service import SpinitronShowItem

DJ_STUDIO_IP = "192.168.1.100"  # within default dj_studio_network 192.168.1.0/24


def _show(
    id: int, start: datetime, end: datetime, persona_id: int | None
) -> SpinitronShowItem:
    return SpinitronShowItem(id=id, start=start, end=end, persona_id=persona_id)


class TestSyncSchedule:
    async def test_no_ops_when_not_configured(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", None)

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 0
        assert db.query(SpinitronShow).count() == 0
        assert (
            db.query(JobLog).filter(JobLog.job_id == "spinitron_schedule_sync").count() == 0
        )

    async def test_uses_staff_dj_name_for_single_persona_match(
        self, db: Session, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
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

        async def fake_fetch_persona_name(persona_id):
            raise AssertionError("should not call the persona API when Staff has the name")

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_persona_name",
            fake_fetch_persona_name,
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

        async def fake_fetch_persona_name(persona_id):
            assert persona_id == 111
            return "Resolved From API"

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_persona_name",
            fake_fetch_persona_name,
        )

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 1
        row = db.query(SpinitronShow).one()
        assert row.dj_name == "Resolved From API"

    async def test_falls_back_to_persona_api_when_no_staff_match(
        self, db: Session, monkeypatch
    ):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), 999)]

        async def fake_fetch_persona_name(persona_id):
            assert persona_id == 999
            return "API Resolved DJ"

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_persona_name",
            fake_fetch_persona_name,
        )

        count = await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        assert count == 1
        assert db.query(SpinitronShow).one().dj_name == "API Resolved DJ"

    async def test_show_with_no_persona_has_no_dj_name(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
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

    async def test_sync_replaces_existing_rows(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "spinitron_api_key", "fake-key")
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
        db.commit()

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), None)]

        monkeypatch.setattr(
            "app.services.spinitron_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )

        await SpinitronScheduleService.sync_schedule(db, trigger="scheduled")

        rows = db.query(SpinitronShow).all()
        assert len(rows) == 1
        assert rows[0].id == 1


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
