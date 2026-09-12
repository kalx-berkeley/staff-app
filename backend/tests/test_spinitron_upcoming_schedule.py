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

# A fixed anchor (noon UTC, mid-June to stay clear of any DST-transition week)
# instead of datetime.now(): noon UTC is unambiguously the same calendar day
# in Pacific time (UTC-7/8), so date-bucketing tests that aren't specifically
# about the UTC/Pacific boundary stay deterministic regardless of when the
# suite runs.
_ANCHOR = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


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


def _patch_no_future_playlists(monkeypatch):
    async def fake_fetch_future_playlists():
        return []

    monkeypatch.setattr(
        "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_future_playlists",
        fake_fetch_future_playlists,
    )


class TestGetDatesForName:
    async def test_matches_by_dj_name_case_insensitive(self, db: Session, monkeypatch):
        now = _ANCHOR
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
        _patch_no_future_playlists(monkeypatch)
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        dates = await SpinitronUpcomingScheduleService.get_dates_for_name(db, "wolfman")

        assert dates == sorted({day1.date().isoformat(), day2.date().isoformat()})

    async def test_matches_by_exact_specialty_show_title(self, db: Session, monkeypatch):
        now = _ANCHOR
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
        _patch_no_future_playlists(monkeypatch)
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        dates = await SpinitronUpcomingScheduleService.get_dates_for_name(
            db, "Sunday Jazz Brunch"
        )

        assert dates == [day1.date().isoformat()]

    async def test_no_match_returns_empty(self, db: Session, monkeypatch):
        now = _ANCHOR

        async def fake_fetch_shows(end):
            return [_show(1, now, now + timedelta(hours=1), 1, "The Howl")]

        async def fake_resolve_dj_names(db, shows):
            return {1: "Wolfman"}

        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        _patch_no_future_playlists(monkeypatch)
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        dates = await SpinitronUpcomingScheduleService.get_dates_for_name(db, "Nightowl")

        assert dates == []

    async def test_buckets_by_station_local_date_not_utc_date(
        self, db: Session, monkeypatch
    ):
        """
        An evening Pacific show should land on today's date, not tomorrow's.

        Spinitron gives `start` in UTC. A show airing at 7pm PDT (2am UTC the
        *next* day, since PDT is UTC-7) must still be bucketed under the
        Pacific calendar date it actually airs on — not the later UTC date —
        or a DJ with a show later today can look like they have no show
        until tomorrow.
        """
        # 2026-06-16T02:00:00+00:00 is 2026-06-15 19:00 PDT (7pm Pacific).
        show_start_utc = datetime(2026, 6, 16, 2, 0, tzinfo=timezone.utc)

        async def fake_fetch_shows(end):
            return [
                _show(
                    1, show_start_utc, show_start_utc + timedelta(hours=1), 1, "Night Shift"
                )
            ]

        async def fake_resolve_dj_names(db, shows):
            return {1: "Nightowl"}

        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        _patch_no_future_playlists(monkeypatch)
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        dates = await SpinitronUpcomingScheduleService.get_dates_for_name(db, "Nightowl")

        assert dates == ["2026-06-15"]

    async def test_second_call_is_served_from_cache(self, db: Session, monkeypatch):
        now = _ANCHOR
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
        _patch_no_future_playlists(monkeypatch)
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        await SpinitronUpcomingScheduleService.get_dates_for_name(db, "Wolfman")
        await SpinitronUpcomingScheduleService.get_dates_for_name(db, "Wolfman")

        assert call_count == 1

    async def test_matches_via_future_playlist_when_shows_disagrees(
        self, db: Session, monkeypatch
    ):
        """
        The "Wolfman" scenario from the request: /shows lists a generic
        placeholder for a slot that a pre-provisioned /playlists entry
        already has a specific DJ for. The playlist-only match should still
        count.
        """
        now = _ANCHOR
        day1 = now + timedelta(days=4)

        async def fake_fetch_shows(end):
            return [_show(1, day1, day1 + timedelta(hours=1), 99, "DJ Trainee")]

        async def fake_fetch_future_playlists():
            return [_show(2, day1, day1 + timedelta(hours=1), 1, None)]

        async def fake_resolve_dj_names(db, shows):
            return {99: None, 1: "Wolfman"}

        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_future_playlists",
            fake_fetch_future_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        dates = await SpinitronUpcomingScheduleService.get_dates_for_name(db, "Wolfman")

        assert dates == [day1.date().isoformat()]

    async def test_future_playlists_beyond_the_window_are_excluded(
        self, db: Session, monkeypatch
    ):
        # The window filter is computed against the real clock (not
        # SpinitronUpcomingScheduleService.SCHEDULE_WINDOW_DAYS), so the
        # "far future" anchor here must be too.
        far_future = datetime.now(timezone.utc) + timedelta(days=40)

        async def fake_fetch_shows(end):
            return []

        async def fake_fetch_future_playlists():
            return [_show(1, far_future, far_future + timedelta(hours=1), 1, None)]

        async def fake_resolve_dj_names(db, shows):
            return {1: "Wolfman"}

        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_shows",
            fake_fetch_shows,
        )
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronService.fetch_future_playlists",
            fake_fetch_future_playlists,
        )
        monkeypatch.setattr(
            "app.services.spinitron_upcoming_schedule_service.SpinitronScheduleService.resolve_dj_names",
            fake_resolve_dj_names,
        )

        dates = await SpinitronUpcomingScheduleService.get_dates_for_name(db, "Wolfman")

        assert dates == []


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
