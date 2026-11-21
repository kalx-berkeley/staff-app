"""Tests for keeping staff who are under 21, going by their birth year, out of 21+ shows."""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.services.leave_service import today_pt
from app.common.services.user_service import UserService, _birth_year
from app.models.audit_log import AuditLog
from app.models.lottery_entry import LotteryEntry
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_pass_alternate import StaffPassAlternate
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.pass_giveaway.services import age_check

SEND_EMAIL = "app.common.services.notification_service.send_email"
SHOW_DATE = date(2030, 6, 15)

UNDER_21_DETAIL = (
    "This show is 21+. Going by the birth year in your staff record, you'll be"
    " under 21 on Jun 15, 2030, so you can't get a pass for it."
)


def _make_staff(
    db: Session,
    name: str,
    birth_year: int | None = None,
    departments: tuple[str, ...] = (),
    statuses: tuple[str, ...] = ("Active",),
) -> Staff:
    staff = Staff(
        email=f"{name.lower()}@age.test", name=name, phone="555-0000", birth_year=birth_year
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
def venue(db: Session) -> Venue:
    v = Venue(name="Bar Venue", address="21 Bar St")
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _make_show(
    db: Session,
    venue: Venue,
    staff_passes: int = 2,
    tabler_passes: int = 0,
    age_restriction: str = "21+",
    **kwargs,
) -> Show:
    show = Show(
        event_name="Bar Show",
        venue_id=venue.id,
        show_date=kwargs.pop("show_date", SHOW_DATE),
        show_time=time(20, 0),
        age_restriction=age_restriction,
        wheelchair_accessible="yes",
        num_pass_pairs=staff_passes + tabler_passes,
        status=kwargs.pop("status", "published"),
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        co_announce=tabler_passes > 0,
        num_tabler_passes=tabler_passes,
        **kwargs,
    )
    db.add(show)
    db.commit()
    db.refresh(show)
    for _ in range(staff_passes):
        db.add(Pass(show_id=show.id, pass_type="staff", status="available"))
    for _ in range(tabler_passes):
        db.add(Pass(show_id=show.id, pass_type="tabler", status="available"))
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


# ── The check ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "birth_year, expected",
    [
        (2010, age_check.UNDER_21),  # 20 at most on the show date
        (2009, age_check.MAYBE_UNDER_21),  # 21 if their birthday has passed, else 20
        (2008, None),  # 21 or 22
        (None, None),
    ],
)
def test_check_by_birth_year(birth_year, expected):
    show = Show(age_restriction="21+", show_date=SHOW_DATE)
    assert age_check.check(show, Staff(birth_year=birth_year)) == expected


@pytest.mark.parametrize("restriction", ["all_ages", "18+", None])
def test_check_only_applies_to_21_plus_shows(restriction):
    show = Show(age_restriction=restriction, show_date=SHOW_DATE)
    assert age_check.check(show, Staff(birth_year=2015)) is None


def test_multi_day_show_is_judged_by_its_first_day():
    show = Show(
        age_restriction="21+",
        show_start_date=date(2029, 12, 30),
        show_date=date(2030, 1, 2),
    )
    # 2030 - 2009 would be "maybe", but on Dec 30, 2029 they're 20 at most
    assert age_check.check(show, Staff(birth_year=2009)) == age_check.UNDER_21


@pytest.mark.parametrize(
    "value, expected",
    [
        (2005, 2005),
        (2005.0, 2005),
        (" 2005 ", 2005),
        ("", None),
        (None, None),
        ("05", None),
        ("2005-01-01", None),
        (1850, None),
        (date.today().year + 1, None),
        (True, None),
    ],
)
def test_birth_year_field_parsing(value, expected):
    assert _birth_year(value) == expected


# ── Getting a pass ────────────────────────────────────────────────────────────


def test_claim_is_blocked_when_under_21(client: TestClient, db: Session, venue):
    show = _make_show(db, venue)
    young = _make_staff(db, "Young", birth_year=2010)

    resp = client.post(f"/api/passes/{_available(db, show).id}/claim", headers=_h(young))

    assert resp.status_code == 409
    assert resp.json()["detail"] == UNDER_21_DETAIL
    assert _available(db, show) is not None


def test_claim_is_allowed_when_maybe_under_21(client: TestClient, db: Session, venue):
    show = _make_show(db, venue)
    maybe = _make_staff(db, "Maybe", birth_year=2009)

    resp = client.post(f"/api/passes/{_available(db, show).id}/claim", headers=_h(maybe))

    assert resp.status_code == 200, resp.text


def test_claim_is_allowed_when_show_isnt_21_plus(client: TestClient, db: Session, venue):
    show = _make_show(db, venue, age_restriction="18+")
    young = _make_staff(db, "Young", birth_year=2010)

    resp = client.post(f"/api/passes/{_available(db, show).id}/claim", headers=_h(young))

    assert resp.status_code == 200, resp.text


def test_adding_a_guest_is_blocked_when_under_21(client: TestClient, db: Session, venue):
    """Someone who claimed before their birth year arrived can't add a guest."""
    show = _make_show(db, venue)
    young = _make_staff(db, "Young")
    pass_id = _available(db, show).id
    assert client.post(f"/api/passes/{pass_id}/claim", headers=_h(young)).status_code == 200
    young.birth_year = 2010
    db.commit()

    resp = client.post(
        f"/api/passes/{pass_id}/guest",
        json={"guest_name": None, "guest_fallback": "attend_alone"},
        headers=_h(young),
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == UNDER_21_DETAIL


def test_lottery_entry_is_blocked_when_under_21(client: TestClient, db: Session, venue):
    show = _make_show(db, venue, lottery_enabled=True, lottery_window_hours=24)
    young = _make_staff(db, "Young", birth_year=2010)

    resp = client.post(f"/api/shows/{show.id}/lottery/enter/staff", headers=_h(young))

    assert resp.status_code == 409
    assert resp.json()["detail"] == UNDER_21_DETAIL
    assert db.query(LotteryEntry).count() == 0


def test_alternate_list_join_is_blocked_when_under_21(
    client: TestClient, db: Session, venue
):
    show = _make_show(db, venue, staff_passes=0)
    young = _make_staff(db, "Young", birth_year=2010)

    resp = client.post(f"/api/shows/{show.id}/alternates", headers=_h(young))

    assert resp.status_code == 409
    assert db.query(StaffPassAlternate).count() == 0


def test_tabler_claim_is_blocked_when_under_21(client: TestClient, db: Session, venue):
    show = _make_show(db, venue, tabler_passes=1)
    young = _make_staff(db, "Young", birth_year=2010, departments=("Publicity",))

    resp = client.post(f"/api/shows/{show.id}/tabler-passes/claim", headers=_h(young))

    assert resp.status_code == 409
    assert resp.json()["detail"] == UNDER_21_DETAIL


def test_promotions_cant_assign_a_tabler_pass_to_someone_under_21(
    client: TestClient, db: Session, venue
):
    show = _make_show(db, venue, tabler_passes=1)
    promo = _make_staff(db, "Promo", departments=("Promotions",))
    young = _make_staff(db, "Young", birth_year=2010)

    with patch(SEND_EMAIL):
        resp = client.post(
            f"/api/shows/{show.id}/tabler-passes/assign",
            json={"staff_id": young.id},
            headers=_h(promo),
        )

    assert resp.status_code == 409
    assert (
        resp.json()["detail"]
        == "This show is 21+. Going by the birth year in their staff record, Young will"
        " be under 21 on Jun 15, 2030, so they can't get a pass for it."
    )


def test_assigning_a_tabler_who_might_be_under_21_warns_promotions_and_them(
    client: TestClient, db: Session, venue
):
    show = _make_show(db, venue, tabler_passes=1)
    promo = _make_staff(db, "Promo", departments=("Promotions",))
    maybe = _make_staff(db, "Maybe", birth_year=2009)

    with patch(SEND_EMAIL) as send:
        resp = client.post(
            f"/api/shows/{show.id}/tabler-passes/assign",
            json={"staff_id": maybe.id},
            headers=_h(promo),
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["staff_age_check"] == "maybe_under_21"
    assert "birth_year" not in resp.json()
    body = send.call_args.kwargs["body_text"]
    assert age_check.MAYBE_UNDER_21_WARNING in body


# ── The signed-in staff member's checks ───────────────────────────────────────


def test_my_age_checks_lists_only_upcoming_21_plus_shows_with_a_result(
    client: TestClient, db: Session, venue
):
    year = today_pt().year
    staff = _make_staff(db, "Teen", birth_year=year - 19)
    under = _make_show(db, venue, show_date=date(year + 1, 6, 1))  # 20 at most
    maybe = _make_show(db, venue, show_date=date(year + 2, 6, 1))  # 20 or 21
    _make_show(db, venue, show_date=date(year + 3, 6, 1))  # 21 or 22
    _make_show(db, venue, show_date=date(year + 1, 6, 1), age_restriction="18+")
    _make_show(db, venue, show_date=date(year + 1, 6, 1), status="draft")
    _make_show(db, venue, show_date=today_pt() - timedelta(days=1))

    resp = client.get("/api/shows/my-age-checks", headers=_h(staff))

    assert resp.status_code == 200, resp.text
    assert resp.json() == {str(under.id): "under_21", str(maybe.id): "maybe_under_21"}


def test_my_age_checks_is_empty_without_a_birth_year(
    client: TestClient, db: Session, venue
):
    _make_show(db, venue, show_date=today_pt() + timedelta(days=1))
    nobody = _make_staff(db, "Nobody")

    resp = client.get("/api/shows/my-age-checks", headers=_h(nobody))

    assert resp.status_code == 200
    assert resp.json() == {}


def test_birth_year_isnt_in_users_me(client: TestClient, db: Session):
    young = _make_staff(db, "Young", birth_year=2010)

    resp = client.get("/api/users/me", headers=_h(young))

    assert resp.status_code == 200
    assert "2010" not in resp.text
    assert "birth" not in resp.text.lower()


# ── Airtable sync ─────────────────────────────────────────────────────────────


def _record(birth_year) -> dict:
    return {
        "id": "recYoungAAAAAAAAA",
        "fields": {
            "Email address": "young@age.test",
            "Name": "Young",
            "Status": ["Active"],
            "Birth year": birth_year,
        },
    }


@pytest.mark.asyncio
async def test_sync_stores_birth_year_and_audits_changes_without_it(db: Session):
    async def sync(birth_year):
        with (
            patch.object(
                UserService,
                "fetch_airtable_records",
                new_callable=AsyncMock,
                return_value=[_record(birth_year)],
            ),
            patch.object(
                UserService,
                "fetch_department_names",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("app.common.services.user_service.download_photo", AsyncMock()),
        ):
            await UserService.sync_from_airtable(db)
        db.expire_all()
        return db.query(Staff).filter_by(email="young@age.test").one()

    assert (await sync(2005)).birth_year == 2005
    assert (await sync("2006")).birth_year == 2006
    assert (await sync(None)).birth_year is None

    changes = [
        e.details["changes"]["birth_year"]
        for e in db.query(AuditLog).filter_by(event_type="airtable_sync_changed")
        if "birth_year" in e.details["changes"]
    ]
    assert changes == ["changed", "changed"]
    assert not any(
        "2005" in str(e.details) or "2006" in str(e.details) for e in db.query(AuditLog)
    )
