"""Tests for SpinitronShowTitlesService and the specialty-shows Spinitron endpoints."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.spinitron_service import SpinitronShowItem
from app.services.spinitron_show_titles_service import SpinitronShowTitlesService
from app.models.specialty_show import SpecialtyShow
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


class TestGetUpcomingTitles:
    async def test_returns_distinct_sorted_titles(self, db: Session, monkeypatch):
        now = datetime.now(timezone.utc)

        async def fake_fetch_shows(end):
            return [
                _show(1, now, now + timedelta(hours=1), 1, "The Howl"),
                _show(2, now, now + timedelta(hours=1), 2, "Sunday Jazz Brunch"),
                _show(3, now, now + timedelta(hours=1), 1, "The Howl"),
                _show(4, now, now + timedelta(hours=1), None, None),
            ]

        monkeypatch.setattr(
            "app.services.spinitron_show_titles_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )

        titles = await SpinitronShowTitlesService.get_upcoming_titles(db)

        assert titles == ["Sunday Jazz Brunch", "The Howl"]

    async def test_second_call_is_served_from_cache(self, db: Session, monkeypatch):
        now = datetime.now(timezone.utc)
        call_count = 0

        async def fake_fetch_shows(end):
            nonlocal call_count
            call_count += 1
            return [_show(1, now, now + timedelta(hours=1), 1, "The Howl")]

        monkeypatch.setattr(
            "app.services.spinitron_show_titles_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )

        await SpinitronShowTitlesService.get_upcoming_titles(db)
        await SpinitronShowTitlesService.get_upcoming_titles(db)

        assert call_count == 1


class TestGetDjHistoryForTitle:
    async def test_matches_by_exact_title_and_dedupes(self, db: Session, monkeypatch):
        now = datetime.now(timezone.utc)

        async def fake_fetch_playlists(start, end):
            return [
                _show(
                    1,
                    now - timedelta(days=10),
                    now - timedelta(days=10),
                    1,
                    "Sunday Jazz Brunch",
                ),
                _show(
                    2,
                    now - timedelta(days=3),
                    now - timedelta(days=3),
                    2,
                    "Sunday Jazz Brunch",
                ),
                _show(
                    3,
                    now - timedelta(days=1),
                    now - timedelta(days=1),
                    1,
                    "Sunday Jazz Brunch",
                ),
                _show(4, now - timedelta(days=1), now - timedelta(days=1), 3, "The Howl"),
            ]

        async def fake_resolve_dj_names(db, shows):
            return {1: "Wolfman", 2: "Nightowl", 3: "Wolfman"}

        monkeypatch.setattr(
            "app.services.spinitron_show_titles_service.SpinitronService.fetch_playlists",
            fake_fetch_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_show_titles_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        djs = await SpinitronShowTitlesService.get_dj_history_for_title(
            db, "Sunday Jazz Brunch"
        )

        assert djs == ["Wolfman", "Nightowl"]

    async def test_no_match_returns_empty(self, db: Session, monkeypatch):
        now = datetime.now(timezone.utc)

        async def fake_fetch_playlists(start, end):
            return [_show(1, now, now, 1, "The Howl")]

        async def fake_resolve_dj_names(db, shows):
            return {1: "Wolfman"}

        monkeypatch.setattr(
            "app.services.spinitron_show_titles_service.SpinitronService.fetch_playlists",
            fake_fetch_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_show_titles_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        djs = await SpinitronShowTitlesService.get_dj_history_for_title(
            db, "Sunday Jazz Brunch"
        )

        assert djs == []


class TestEndpoints:
    def test_upcoming_titles_route_not_swallowed_by_show_id_route(
        self, client: TestClient, staff_member: Staff, monkeypatch
    ):
        async def fake_get_upcoming_titles(db):
            return ["Sunday Jazz Brunch"]

        monkeypatch.setattr(
            "app.routers.specialty_shows.SpinitronShowTitlesService.get_upcoming_titles",
            fake_get_upcoming_titles,
        )

        response = client.get(
            "/api/specialty-shows/upcoming-titles",
            headers={"X-Forwarded-User": staff_member.email},
        )

        assert response.status_code == 200
        assert response.json() == ["Sunday Jazz Brunch"]

    def test_dj_history_route(
        self, client: TestClient, db: Session, staff_member: Staff, monkeypatch
    ):
        now = datetime.now(timezone.utc)
        show = SpecialtyShow(name="Sunday Jazz Brunch", created_at=now, updated_at=now)
        db.add(show)
        db.commit()
        db.refresh(show)

        async def fake_get_dj_history_for_title(db, title):
            assert title == "Sunday Jazz Brunch"
            return ["Wolfman", "Nightowl"]

        monkeypatch.setattr(
            "app.routers.specialty_shows.SpinitronShowTitlesService.get_dj_history_for_title",
            fake_get_dj_history_for_title,
        )

        response = client.get(
            f"/api/specialty-shows/{show.id}/dj-history",
            headers={"X-Forwarded-User": staff_member.email},
        )

        assert response.status_code == 200
        assert response.json() == ["Wolfman", "Nightowl"]

    def test_dj_history_route_404s_for_missing_show(
        self, client: TestClient, staff_member: Staff
    ):
        response = client.get(
            "/api/specialty-shows/999999/dj-history",
            headers={"X-Forwarded-User": staff_member.email},
        )

        assert response.status_code == 404
