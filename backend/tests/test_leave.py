"""Tests for leave of absence: when staff are on leave, and what it blocks or flags."""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.lottery_entry import LotteryEntry
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_genre_preference import StaffGenrePreference
from app.models.staff_pass_alternate import StaffPassAlternate
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.services.lottery_service import LotteryService
from app.services.leave_service import (
    format_leave,
    leave_covers_show,
    leave_is_current_or_upcoming,
    on_leave,
    today_pt,
)

SEND_EMAIL = "app.services.notification_service.send_email"
SHOW_DATE = date(2030, 6, 15)

# ── Fixtures & helpers ────────────────────────────────────────────────────────


def _make_staff(
    db: Session,
    name: str,
    loa_start: date | None = None,
    loa_end: date | None = None,
    statuses: tuple[str, ...] = ("Active",),
    departments: tuple[str, ...] = (),
    dj_name: str | None = None,
) -> Staff:
    staff = Staff(
        email=f"{name.lower()}@leave.test",
        name=name,
        phone="555-0000",
        loa_start=loa_start,
        loa_end=loa_end,
        dj_name=dj_name,
    )
    db.add(staff)
    db.flush()
    for s in statuses:
        db.add(StaffStatus(staff_id=staff.id, status=s))
    for d in departments:
        db.add(StaffDepartment(staff_id=staff.id, department=d))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def promo(db: Session) -> Staff:
    return _make_staff(db, "Promo", departments=("Promotions",))


@pytest.fixture
def venue(db: Session) -> Venue:
    v = Venue(name="Leave Venue", address="1 Leave St")
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _make_show(db: Session, venue: Venue, staff_passes: int = 2, **kwargs) -> Show:
    show = Show(
        event_name="Leave Show",
        venue_id=venue.id,
        show_date=kwargs.pop("show_date", SHOW_DATE),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=staff_passes,
        status="published",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        **kwargs,
    )
    db.add(show)
    db.commit()
    db.refresh(show)
    for _ in range(staff_passes):
        db.add(Pass(show_id=show.id, pass_type="staff", status="available"))
    db.commit()
    return show


def _h(staff: Staff) -> dict:
    return {"X-Forwarded-User": staff.email}


def _available(db: Session, show: Show) -> Pass:
    return (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id, Pass.pass_type == "staff", Pass.status == "available"
        )
        .order_by(Pass.id)
        .first()
    )


# ── leave_service ─────────────────────────────────────────────────────────────


def test_on_leave_is_inclusive_and_handles_one_sided_leave():
    both = Staff(loa_start=date(2030, 3, 1), loa_end=date(2030, 3, 31))
    assert not on_leave(both, date(2030, 2, 28))
    assert on_leave(both, date(2030, 3, 1))
    assert on_leave(both, date(2030, 3, 31))
    assert not on_leave(both, date(2030, 4, 1))

    start_only = Staff(loa_start=date(2030, 3, 1))
    assert not on_leave(start_only, date(2030, 2, 28))
    assert on_leave(start_only, date(2099, 1, 1))

    end_only = Staff(loa_end=date(2030, 3, 31))
    assert on_leave(end_only, date(2000, 1, 1))
    assert not on_leave(end_only, date(2030, 4, 1))

    assert not on_leave(Staff(), date(2030, 3, 1))


def test_leave_covers_show_only_when_every_day_is_covered():
    leave = Staff(loa_start=date(2030, 6, 1), loa_end=date(2030, 6, 15))
    one_day = Show(show_date=date(2030, 6, 15))
    festival_ending_after = Show(
        show_start_date=date(2030, 6, 14), show_date=date(2030, 6, 16)
    )
    festival_inside = Show(show_start_date=date(2030, 6, 2), show_date=date(2030, 6, 3))
    assert leave_covers_show(leave, one_day)
    assert not leave_covers_show(leave, festival_ending_after)
    assert leave_covers_show(leave, festival_inside)


def test_leave_is_current_or_upcoming_and_format():
    today = date(2030, 6, 1)
    assert leave_is_current_or_upcoming(Staff(loa_end=date(2030, 6, 1)), today)
    assert not leave_is_current_or_upcoming(Staff(loa_end=date(2030, 5, 31)), today)
    assert leave_is_current_or_upcoming(Staff(loa_start=date(2020, 1, 1)), today)
    assert not leave_is_current_or_upcoming(Staff(), today)

    assert (
        format_leave(Staff(loa_start=date(2030, 3, 1), loa_end=date(2030, 6, 1)))
        == "Mar 1, 2030 – Jun 1, 2030"
    )
    assert format_leave(Staff(loa_start=date(2030, 3, 1))) == "from Mar 1, 2030"
    assert format_leave(Staff(loa_end=date(2030, 6, 1))) == "until Jun 1, 2030"


# ── Getting a staff pass ──────────────────────────────────────────────────────


def test_claim_is_blocked_during_leave(client: TestClient, db: Session, venue):
    show = _make_show(db, venue)
    away = _make_staff(db, "Away", loa_start=date(2030, 6, 1), loa_end=date(2030, 6, 30))

    resp = client.post(f"/api/passes/{_available(db, show).id}/claim", headers=_h(away))

    assert resp.status_code == 409
    assert (
        resp.json()["detail"]
        == "You're on leave of absence Jun 1, 2030 – Jun 30, 2030, so you can't claim"
        " passes for this show."
    )


def test_promotions_claim_is_blocked_during_leave(client: TestClient, db: Session, venue):
    show = _make_show(db, venue)
    promo = _make_staff(
        db, "AwayPromo", loa_start=date(2030, 6, 1), departments=("Promotions",)
    )

    resp = client.post(f"/api/passes/{_available(db, show).id}/claim", headers=_h(promo))

    assert resp.status_code == 409


def test_claim_is_allowed_when_leave_ends_during_a_multi_day_show(
    client: TestClient, db: Session, venue
):
    show = _make_show(db, venue, show_start_date=date(2030, 6, 14))
    back = _make_staff(db, "Back", loa_end=date(2030, 6, 14))

    resp = client.post(f"/api/passes/{_available(db, show).id}/claim", headers=_h(back))

    assert resp.status_code == 200, resp.text


def test_lottery_entry_is_blocked_during_leave(client: TestClient, db: Session, venue):
    show = _make_show(db, venue, lottery_enabled=True, lottery_window_hours=24)
    away = _make_staff(db, "Away", loa_start=date(2030, 6, 1))

    resp = client.post(f"/api/shows/{show.id}/lottery/enter/staff", headers=_h(away))

    assert resp.status_code == 409
    assert db.query(LotteryEntry).count() == 0


def test_alternate_queue_join_is_blocked_during_leave(
    client: TestClient, db: Session, venue
):
    show = _make_show(db, venue, staff_passes=0)
    away = _make_staff(db, "Away", loa_start=date(2030, 6, 1))

    resp = client.post(f"/api/shows/{show.id}/alternates", headers=_h(away))

    assert resp.status_code == 409
    assert db.query(StaffPassAlternate).count() == 0


# ── Lottery draw and alternates ───────────────────────────────────────────────


def _entry(db: Session, show: Show, staff: Staff) -> LotteryEntry:
    now = datetime.now(timezone.utc)
    entry = LotteryEntry(
        show_id=show.id,
        entry_type="staff",
        staff_id=staff.id,
        status="pending",
        entered_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.commit()
    return entry


def test_lottery_drops_entrants_on_leave(db: Session, venue):
    """An entrant whose leave was added after they entered isn't drawn or queued
    as an alternate, but still gets the usual "not selected" email."""
    show = _make_show(db, venue, staff_passes=1, lottery_enabled=True)
    away = _make_staff(db, "Away", loa_start=date(2030, 6, 1))
    here = _make_staff(db, "Here")
    away_entry = _entry(db, show, away)
    here_entry = _entry(db, show, here)

    with patch(SEND_EMAIL) as send_email:
        LotteryService.run_lottery(db, show.id)

    db.refresh(away_entry)
    db.refresh(here_entry)
    assert away_entry.status == "lost"
    assert here_entry.status == "won"
    assert db.query(StaffPassAlternate).filter_by(staff_id=away.id).count() == 0
    away_emails = [
        c.kwargs for c in send_email.call_args_list if c.kwargs["to_email"] == away.email
    ]
    assert len(away_emails) == 1
    assert "you were not selected" in away_emails[0]["body_text"]


def test_alternates_on_leave_are_skipped_but_keep_their_place(
    client: TestClient, db: Session, venue
):
    show = _make_show(db, venue, staff_passes=1)
    holder = _make_staff(db, "Holder")
    away = _make_staff(db, "Away")
    next_up = _make_staff(db, "Next")
    held = _available(db, show)
    assert (
        client.post(f"/api/passes/{held.id}/claim", headers=_h(holder)).status_code == 200
    )
    for staff in (away, next_up):
        assert (
            client.post(f"/api/shows/{show.id}/alternates", headers=_h(staff)).status_code
            == 201
        )
    # Leave added in Airtable after joining the queue.
    away.loa_start = date(2030, 6, 1)
    db.commit()

    with patch(SEND_EMAIL):
        resp = client.delete(f"/api/passes/{held.id}/claim", headers=_h(holder))
    assert resp.status_code == 200, resp.text

    db.expire_all()
    assert db.get(Pass, held.id).staff_id == next_up.id
    waiting = db.query(StaffPassAlternate).filter_by(staff_id=away.id).one()
    assert waiting.status == "waiting"


# ── Flags for promotions ──────────────────────────────────────────────────────


def test_pass_list_flags_claimants_on_leave(client: TestClient, db: Session, venue, promo):
    show = _make_show(db, venue)
    away = _make_staff(db, "Away")
    here = _make_staff(db, "Here")
    for staff in (away, here):
        client.post(f"/api/passes/{_available(db, show).id}/claim", headers=_h(staff))
    away.loa_start = date(2030, 6, 1)
    away.loa_end = date(2030, 6, 30)
    db.commit()

    resp = client.get(f"/api/shows/{show.id}/passes", headers=_h(promo))

    by_staff = {p["staff_id"]: p for p in resp.json() if p["staff_id"]}
    assert by_staff[away.id]["staff_on_leave"] is True
    assert by_staff[away.id]["staff_loa_start"] == "2030-06-01"
    assert by_staff[away.id]["staff_loa_end"] == "2030-06-30"
    assert by_staff[here.id]["staff_on_leave"] is False
    assert by_staff[here.id]["staff_loa_start"] is None


def test_genre_suggestions_label_djs_on_leave_and_sort_them_last(
    client: TestClient, db: Session, venue, promo
):
    show = _make_show(db, venue, genre=["Rock"])
    today = today_pt()
    for name, loa_start in (("Aaron", today), ("Zed", None)):
        dj = _make_staff(
            db, name, loa_start=loa_start, statuses=("Active", "Sublist DJ"), dj_name=name
        )
        db.add(StaffGenrePreference(staff_id=dj.id, genres=["rock"]))
    db.commit()

    resp = client.get(
        "/api/passes/preassign/suggest-by-genre",
        params={"show_id": show.id},
        headers=_h(promo),
    )

    assert [(s["name"], s["on_leave"]) for s in resp.json()] == [
        ("Zed", False),
        ("Aaron", True),
    ]
    assert resp.json()[1]["loa_start"] == today.isoformat()


def test_preassign_leave_lookup(client: TestClient, db: Session, promo):
    today = today_pt()
    _make_staff(
        db,
        "Away",
        loa_start=today,
        loa_end=today + timedelta(days=9),
        dj_name="DJ A, Alt A",
    )
    _make_staff(db, "Past", loa_end=today - timedelta(days=1), dj_name="DJ P")

    def lookup(name: str):
        resp = client.get(
            "/api/passes/preassign/leave", params={"name": name}, headers=_h(promo)
        )
        assert resp.status_code == 200
        return resp.json()

    assert lookup("alt a") == {
        "loa_start": today.isoformat(),
        "loa_end": (today + timedelta(days=9)).isoformat(),
    }
    assert lookup("DJ P") is None
    assert lookup("Nobody") is None


# ── What staff see ────────────────────────────────────────────────────────────


def test_me_includes_leave_dates(client: TestClient, db: Session):
    away = _make_staff(db, "Away", loa_start=date(2030, 6, 1))

    profile = client.get("/api/users/me", headers=_h(away)).json()["profile"]

    assert profile["loa_start"] == "2030-06-01"
    assert profile["loa_end"] is None


def test_directory_shows_current_and_upcoming_leave_only(client: TestClient, db: Session):
    today = today_pt()
    viewer = _make_staff(db, "Viewer")
    _make_staff(db, "Current", loa_start=today - timedelta(days=1), loa_end=today)
    _make_staff(db, "Upcoming", loa_start=today + timedelta(days=1))
    _make_staff(db, "Past", loa_end=today - timedelta(days=1))

    entries = {
        e["name"]: e for e in client.get("/api/directory", headers=_h(viewer)).json()
    }

    assert entries["Current"]["on_leave"] is True
    assert entries["Current"]["loa_end"] == today.isoformat()
    assert entries["Upcoming"]["on_leave"] is False
    assert entries["Upcoming"]["loa_start"] == (today + timedelta(days=1)).isoformat()
    assert entries["Past"]["on_leave"] is False
    assert entries["Past"]["loa_end"] is None
    assert entries["Viewer"]["loa_start"] is None
