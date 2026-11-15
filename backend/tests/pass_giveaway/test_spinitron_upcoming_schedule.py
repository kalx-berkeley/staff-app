"""Tests for SpinitronUpcomingScheduleService and the pre-assignment schedule endpoints."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.services.spinitron_service import SpinitronShowItem
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_spinitron_show import SpecialtyShowSpinitronShow
from app.models.staff import Staff
from app.models.staff_status import StaffStatus
from app.pass_giveaway.services.spinitron_upcoming_schedule_service import (
    SpinitronUpcomingScheduleService,
)
from tests.personas import dj_fields

UPCOMING_SERVICE = "app.pass_giveaway.services.spinitron_upcoming_schedule_service"
PASSES_ROUTER = "app.pass_giveaway.routers.passes"

# A fixed anchor (noon UTC, mid-June to stay clear of any DST-transition week)
# instead of datetime.now(): noon UTC is unambiguously the same calendar day
# in Pacific time (UTC-7/8), so date-bucketing tests that aren't specifically
# about the UTC/Pacific boundary stay deterministic regardless of when the
# suite runs.
_ANCHOR = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

WOLFMAN = 1
NIGHTOWL = 2


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
    persona_id: int | None,
    title: str | None = None,
) -> SpinitronShowItem:
    """A `/shows` item: *id* is the Spinitron show."""
    return SpinitronShowItem(
        id=id,
        start=start,
        end=start + timedelta(hours=1),
        persona_id=persona_id,
        title=title,
    )


def _playlist(
    id: int, start: datetime, persona_id: int | None, show_id: int | None = None
) -> SpinitronShowItem:
    """A future `/playlists` item, belonging to Spinitron show *show_id*."""
    return SpinitronShowItem(
        id=id,
        start=start,
        end=start + timedelta(hours=1),
        persona_id=persona_id,
        title=None,
        show_id=show_id,
    )


def _patch_schedule(monkeypatch, shows=(), playlists=()):
    async def fake_fetch_shows(end):
        return list(shows)

    async def fake_fetch_future_playlists():
        return list(playlists)

    monkeypatch.setattr(
        f"{UPCOMING_SERVICE}.SpinitronService.fetch_shows", fake_fetch_shows
    )
    monkeypatch.setattr(
        f"{UPCOMING_SERVICE}.SpinitronService.fetch_future_playlists",
        fake_fetch_future_playlists,
    )


def _specialty(db: Session, name: str, spinitron_show_id: int, category="music"):
    show = SpecialtyShow(name=name, category=category)
    db.add(show)
    db.flush()
    db.add(
        SpecialtyShowSpinitronShow(
            specialty_show_id=show.id, spinitron_show_id=spinitron_show_id
        )
    )
    db.commit()
    return show


async def _schedule(db, persona_id=None, specialty_show_id=None):
    return await SpinitronUpcomingScheduleService.get_identity_schedule(
        db, persona_id, specialty_show_id
    )


class TestGetIdentitySchedule:
    async def test_a_personas_dates(self, db: Session, monkeypatch):
        day1 = _ANCHOR + timedelta(days=3)
        day2 = _ANCHOR + timedelta(days=10)
        _patch_schedule(
            monkeypatch,
            shows=[
                _show(100, day1, WOLFMAN),
                _show(100, day2, WOLFMAN),
                _show(101, _ANCHOR, NIGHTOWL),
            ],
        )

        schedule = await _schedule(db, persona_id=WOLFMAN)

        assert schedule == {
            "dates": [day1.date().isoformat(), day2.date().isoformat()],
            "talk_show_dates": {},
        }

    async def test_a_show_is_found_by_its_spinitron_show_not_its_title(
        self, db: Session, monkeypatch
    ):
        brunch = _specialty(db, "Sunday Jazz Brunch", 300)
        day1 = _ANCHOR + timedelta(days=5)
        day2 = _ANCHOR + timedelta(days=6)
        _patch_schedule(
            monkeypatch,
            shows=[
                _show(300, day1, WOLFMAN, "Brunch"),
                _show(301, day2, None, brunch.name),
            ],
        )

        schedule = await _schedule(db, specialty_show_id=brunch.id)

        assert schedule["dates"] == [day1.date().isoformat()]

    async def test_a_persona_counts_on_its_music_show_days_but_not_its_talk_show_days(
        self, db: Session, monkeypatch
    ):
        _specialty(db, "Take Five", 300)
        talk = _specialty(db, "Morning Report", 400, category="talk")
        music_day = _ANCHOR + timedelta(days=1)
        talk_day = _ANCHOR + timedelta(days=2)
        _patch_schedule(
            monkeypatch,
            playlists=[
                _playlist(1, music_day, WOLFMAN, show_id=300),
                _playlist(2, talk_day, WOLFMAN, show_id=400),
            ],
        )

        schedule = await _schedule(db, persona_id=WOLFMAN)

        assert schedule == {
            "dates": [music_day.date().isoformat()],
            "talk_show_dates": {talk_day.date().isoformat(): talk.name},
        }

    async def test_no_match_returns_empty(self, db: Session, monkeypatch):
        _patch_schedule(monkeypatch, shows=[_show(100, _ANCHOR, WOLFMAN)])

        assert (await _schedule(db, persona_id=NIGHTOWL))["dates"] == []

    async def test_buckets_by_station_local_date_not_utc_date(
        self, db: Session, monkeypatch
    ):
        """
        An evening Pacific show should land on today's date, not tomorrow's.

        Spinitron gives `start` in UTC. A show airing at 7pm PDT (2am UTC the
        *next* day, since PDT is UTC-7) must still be bucketed under the
        Pacific calendar date it actually airs on.
        """
        # 2026-06-16T02:00:00+00:00 is 2026-06-15 19:00 PDT (7pm Pacific).
        start = datetime(2026, 6, 16, 2, 0, tzinfo=timezone.utc)
        _patch_schedule(monkeypatch, shows=[_show(100, start, NIGHTOWL)])

        assert (await _schedule(db, persona_id=NIGHTOWL))["dates"] == ["2026-06-15"]

    async def test_playlist_evening_show_buckets_to_pacific_date_not_utc_date(
        self, db: Session, monkeypatch
    ):
        # 2026-09-15T01:00:00+00:00 is 2026-09-14 18:00 PDT (6pm Pacific).
        start = datetime(2026, 9, 15, 1, 0, tzinfo=timezone.utc)
        _patch_schedule(monkeypatch, playlists=[_playlist(1, start, WOLFMAN)])

        assert (await _schedule(db, persona_id=WOLFMAN))["dates"] == ["2026-09-14"]

    async def test_matches_via_future_playlist_when_shows_disagrees(
        self, db: Session, monkeypatch
    ):
        """
        /shows lists a generic placeholder for a slot that a pre-provisioned
        /playlists entry already has a specific DJ for. The playlist-only
        match still counts.
        """
        day = _ANCHOR + timedelta(days=4)
        _patch_schedule(
            monkeypatch,
            shows=[_show(100, day, 99, "DJ Trainee")],
            playlists=[_playlist(2, day, WOLFMAN)],
        )

        assert (await _schedule(db, persona_id=WOLFMAN))["dates"] == [
            day.date().isoformat()
        ]

    async def test_future_playlists_beyond_the_window_are_excluded(
        self, db: Session, monkeypatch
    ):
        # The window filter is computed against the real clock, so the "far
        # future" anchor here must be too.
        far_future = datetime.now(timezone.utc) + timedelta(days=70)
        _patch_schedule(monkeypatch, playlists=[_playlist(1, far_future, WOLFMAN)])

        assert (await _schedule(db, persona_id=WOLFMAN))["dates"] == []

    async def test_second_call_is_served_from_cache(self, db: Session, monkeypatch):
        calls = 0

        async def fake_fetch_shows(end):
            nonlocal calls
            calls += 1
            return [_show(100, _ANCHOR, WOLFMAN)]

        _patch_schedule(monkeypatch)
        monkeypatch.setattr(
            f"{UPCOMING_SERVICE}.SpinitronService.fetch_shows", fake_fetch_shows
        )

        await _schedule(db, persona_id=WOLFMAN)
        await _schedule(db, persona_id=WOLFMAN)

        assert calls == 1


class TestGetIdentitiesForDate:
    async def test_lists_personas_and_shows_on_the_date(self, db: Session, monkeypatch):
        music = _specialty(db, "Take Five", 300)
        talk = _specialty(db, "Morning Report", 400, category="talk")
        day = _ANCHOR + timedelta(days=3)
        _patch_schedule(
            monkeypatch,
            shows=[
                _show(100, day, WOLFMAN),
                # A music show: the show, and its DJ's persona
                _show(300, day + timedelta(hours=2), NIGHTOWL),
                # A talk show: the show only
                _show(400, day + timedelta(hours=4), 77),
                # Neither a show nor a persona
                _show(500, day + timedelta(hours=6), None, "FREEFORM"),
                _show(100, day + timedelta(days=7), 55),
            ],
        )

        found = await SpinitronUpcomingScheduleService.get_identities_for_date(
            db, day.date().isoformat()
        )

        assert found == [
            {"persona_id": WOLFMAN, "specialty_show_id": None},
            {"persona_id": None, "specialty_show_id": music.id},
            {"persona_id": NIGHTOWL, "specialty_show_id": None},
            {"persona_id": None, "specialty_show_id": talk.id},
        ]


class TestSuggestByDateEndpoint:
    def test_suggests_staff_personas_and_shows(
        self, client: TestClient, staff_member: Staff, db: Session, monkeypatch
    ):
        dj = Staff(
            email="wolf@test.com",
            name="Wolf",
            phone="",
            **dj_fields("Wolfman", ids=[WOLFMAN]),
        )
        db.add(dj)
        db.flush()
        db.add(StaffStatus(staff_id=dj.id, status="Active"))
        db.commit()
        brunch = _specialty(db, "Sunday Jazz Brunch", 300)

        async def fake_get_identities_for_date(db, date):
            assert date == "2026-09-20"
            return [
                {"persona_id": WOLFMAN, "specialty_show_id": None},
                # No staff member holds this persona
                {"persona_id": NIGHTOWL, "specialty_show_id": None},
                {"persona_id": None, "specialty_show_id": brunch.id},
            ]

        monkeypatch.setattr(
            f"{PASSES_ROUTER}.SpinitronUpcomingScheduleService.get_identities_for_date",
            fake_get_identities_for_date,
        )

        response = client.get(
            "/api/passes/preassign/suggest-by-date",
            params={"date": "2026-09-20"},
            headers={"X-Forwarded-User": staff_member.email},
        )

        assert response.status_code == 200
        assert [
            (s["name"], s["persona_id"], s["specialty_show_id"], s["specialty_category"])
            for s in response.json()
        ] == [
            ("Sunday Jazz Brunch", None, brunch.id, "music"),
            ("Wolfman", WOLFMAN, None, None),
        ]

    def test_requires_authentication(self, client: TestClient):
        response = client.get(
            "/api/passes/preassign/suggest-by-date", params={"date": "2026-09-20"}
        )

        assert response.status_code == 400


class TestPreassignScheduleEndpoint:
    def test_returns_a_personas_schedule(
        self, client: TestClient, staff_member: Staff, monkeypatch
    ):
        async def fake_get_identity_schedule(db, persona_id, specialty_show_id):
            assert (persona_id, specialty_show_id) == (WOLFMAN, None)
            return {"dates": ["2026-09-20"], "talk_show_dates": {"2026-09-27": "News"}}

        monkeypatch.setattr(
            f"{PASSES_ROUTER}.SpinitronUpcomingScheduleService.get_identity_schedule",
            fake_get_identity_schedule,
        )

        response = client.get(
            "/api/passes/preassign/schedule",
            params={"persona_id": WOLFMAN},
            headers={"X-Forwarded-User": staff_member.email},
        )

        assert response.status_code == 200
        assert response.json() == {
            "dates": ["2026-09-20"],
            "talk_show_dates": {"2026-09-27": "News"},
        }

    def test_needs_exactly_one_identity(self, client: TestClient, staff_member: Staff):
        headers = {"X-Forwarded-User": staff_member.email}
        for params in ({}, {"persona_id": 1, "specialty_show_id": 2}):
            response = client.get(
                "/api/passes/preassign/schedule", params=params, headers=headers
            )
            assert response.status_code == 400

    def test_requires_authentication(self, client: TestClient):
        response = client.get("/api/passes/preassign/schedule", params={"persona_id": 1})

        assert response.status_code == 400
