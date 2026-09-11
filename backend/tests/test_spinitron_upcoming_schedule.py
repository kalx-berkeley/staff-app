"""Tests for SpinitronUpcomingScheduleService and the preassign-schedule endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.spinitron_service import SpinitronShowItem
from app.services.spinitron_upcoming_schedule_service import (
    SpinitronUpcomingScheduleService,
)
from app.models.staff import Staff
from app.models.staff_status import StaffStatus


@pytest.fixture
def staff_member(db: Session) -> Staff:
    """Create a test staff member (satisfies the identity-check middleware)."""
    staff = Staff(email="staff@test.com", name="Test Staff", phone="555-0002")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


def _show(
    id: int,
    start: datetime,
    end: datetime,
    persona_id: int | None,
    title: str | None,
) -> SpinitronShowItem:
    return SpinitronShowItem(
        id=id, start=start, end=end, persona_id=persona_id, title=title
    )


class TestGetDatesForName:
    async def test_matches_by_dj_name_case_insensitive(self, db: Session, monkeypatch):
        now = datetime.now(timezone.utc)
        day1 = now + timedelta(days=3)
        day2 = now + timedelta(days=10)

        async def fake_fetch_shows(end):
            return [
                _show(1, day1, day1 + timedelta(hours=1), 1, "The Howl"),
                _show(2, day2, day2 + timedelta(hours=1), 1, "The Howl"),
                _show(3, now, now + timedelta(hours=1), 2, "Sunday Jazz Brunch"),
            ]

        async def fake_resolve_dj_names(db, shows):
            return {1: "Wolfman", 2: "Nightowl"}

        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        dates = await SpinitronUpcomingScheduleService.get_dates_for_name(db, "wolfman")

        assert dates == sorted({day1.date().isoformat(), day2.date().isoformat()})

    async def test_matches_by_exact_specialty_show_title(self, db: Session, monkeypatch):
        now = datetime.now(timezone.utc)
        day1 = now + timedelta(days=5)

        async def fake_fetch_shows(end):
            return [
                _show(1, day1, day1 + timedelta(hours=1), None, "Sunday Jazz Brunch"),
            ]

        async def fake_resolve_dj_names(db, shows):
            return {}

        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        dates = await SpinitronUpcomingScheduleService.get_dates_for_name(
            db, "Sunday Jazz Brunch"
        )

        assert dates == [day1.date().isoformat()]

    async def test_no_match_returns_empty(self, db: Session, monkeypatch):
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), 1, "The Howl")]

        async def fake_resolve_dj_names(db, shows):
            return {1: "Wolfman"}

        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        dates = await SpinitronUpcomingScheduleService.get_dates_for_name(db, "Nightowl")

        assert dates == []

    async def test_second_call_is_served_from_cache(self, db: Session, monkeypatch):
        now = datetime.now(timezone.utc)
        call_count = 0

        async def fake_fetch_shows(end):
            nonlocal call_count
            call_count += 1
            return [_show(1, now, now + timedelta(hours=1), 1, "The Howl")]

        async def fake_resolve_dj_names(db, shows):
            return {1: "Wolfman"}

        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        await SpinitronUpcomingScheduleService.get_dates_for_name(db, "Wolfman")
        await SpinitronUpcomingScheduleService.get_dates_for_name(db, "Wolfman")

        assert call_count == 1


class TestPreassignScheduleEndpoint:
    def test_returns_matching_dates(
        self, client: TestClient, staff_member: Staff, monkeypatch
    ):
        async def fake_get_dates_for_name(db, name):
            assert name == "Wolfman"
            return ["2026-09-20", "2026-09-27"]

        monkeypatch.setattr(
            "app.routers.passes.SpinitronUpcomingScheduleService.get_dates_for_name",
            fake_get_dates_for_name,
        )

        response = client.get(
            "/api/passes/preassign/schedule",
            params={"name": "Wolfman"},
            headers={"X-Forwarded-User": staff_member.email},
        )

        assert response.status_code == 200
        assert response.json() == ["2026-09-20", "2026-09-27"]

    def test_requires_authentication(self, client: TestClient):
        response = client.get("/api/passes/preassign/schedule", params={"name": "Wolfman"})

        assert response.status_code == 400
