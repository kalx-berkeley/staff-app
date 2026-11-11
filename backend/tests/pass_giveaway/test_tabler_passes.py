"""Tests for tabler passes: co-announce staff passes for the KALX Co-Announce Table."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.common.areas import PASS_GIVEAWAY_AREA
from app.models.audit_log import AuditLog
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_pass_alternate import StaffPassAlternate
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.pass_giveaway.services.show_service import ShowService

SEND_EMAIL = "app.common.services.notification_service.send_email"


@pytest.fixture
def venue(db: Session):
    v = Venue(name="Table Venue", address="1 Swag St")
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _make_staff(
    db: Session, name: str, department: str | None = None, status: str = "Active"
) -> Staff:
    staff = Staff(email=f"{name.lower()}@table.test", name=name, phone="5105550000")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status=status))
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def promo(db: Session):
    return _make_staff(db, "Pat", "Promotions")


@pytest.fixture
def pub(db: Session):
    return _make_staff(db, "Penny", "Publicity")


@pytest.fixture
def pub2(db: Session):
    return _make_staff(db, "Quinn", "Publicity")


@pytest.fixture
def plain(db: Session):
    return _make_staff(db, "Sam")


def _h(staff: Staff) -> dict:
    return {"X-Forwarded-User": staff.email}


def _show_body(venue: Venue, **overrides) -> dict:
    body = {
        "event_name": "Table Show",
        "venue_id": venue.id,
        "show_date": str(date.today() + timedelta(days=30)),
        "show_time": "20:00:00",
        "age_restriction": "all_ages",
        "wheelchair_accessible": "yes",
        "num_pass_pairs": 3,
        "co_announce": True,
    }
    body.update(overrides)
    return body


def _create(client, promo, venue, **overrides) -> dict:
    resp = client.post("/api/shows", json=_show_body(venue, **overrides), headers=_h(promo))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _publish(db: Session, show_id: int) -> Show:
    show = db.query(Show).filter(Show.id == show_id).first()
    show.status = "published"
    show.published_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    return show


def _counts(db: Session, show_id: int) -> tuple[int, int]:
    db.expire_all()
    passes = db.query(Pass).filter(Pass.show_id == show_id).all()
    return (
        sum(1 for p in passes if p.pass_type == "staff"),
        sum(1 for p in passes if p.pass_type == "tabler"),
    )


def _claim_tabler(client, show_id, staff):
    return client.post(f"/api/shows/{show_id}/tabler-passes/claim", headers=_h(staff))


def _claim_staff(client, db, show_id, staff):
    p = (
        db.query(Pass)
        .filter(
            Pass.show_id == show_id, Pass.pass_type == "staff", Pass.status == "available"
        )
        .order_by(Pass.id)
        .first()
    )
    return client.post(f"/api/passes/{p.id}/claim", json={}, headers=_h(staff))


def _update(client, promo, show_id, **body):
    return client.put(f"/api/shows/{show_id}", json=body, headers=_h(promo))


# ── Setting the count ─────────────────────────────────────────────────────────


def test_co_announce_show_defaults_to_two_tabler_passes(client, db, promo, venue):
    data = _create(client, promo, venue)
    assert data["num_tabler_passes"] == 2
    assert data["num_staff_passes"] == 3
    assert data["available_staff_count"] == 1
    assert data["available_tabler_count"] == 2
    assert _counts(db, data["id"]) == (1, 2)


def test_show_without_co_announce_has_no_tabler_passes(client, db, promo, venue):
    data = _create(client, promo, venue, co_announce=False)
    assert data["num_tabler_passes"] == 0
    assert _counts(db, data["id"]) == (3, 0)


def test_tabler_passes_need_co_announce(client, promo, venue):
    resp = client.post(
        "/api/shows",
        json=_show_body(venue, co_announce=False, num_tabler_passes=1),
        headers=_h(promo),
    )
    assert resp.status_code == 422


def test_tabler_passes_cant_exceed_staff_passes(client, promo, venue):
    resp = client.post(
        "/api/shows", json=_show_body(venue, num_tabler_passes=4), headers=_h(promo)
    )
    assert resp.status_code == 422
    assert "Staff Pass Adjustment" in resp.text


def test_raising_count_beyond_unclaimed_staff_passes_is_refused(
    client, db, promo, venue, plain
):
    data = _create(client, promo, venue, num_tabler_passes=1)
    _publish(db, data["id"])
    assert _claim_staff(client, db, data["id"], plain).status_code == 200
    resp = _update(client, promo, data["id"], num_tabler_passes=3)
    assert resp.status_code == 400
    assert "1 of the 3 staff passes are claimed" in resp.json()["detail"]
    assert _counts(db, data["id"]) == (2, 1)


def test_raising_and_lowering_unclaimed_count(client, db, promo, venue):
    data = _create(client, promo, venue, num_tabler_passes=1)
    assert _update(client, promo, data["id"], num_tabler_passes=3).status_code == 200
    assert _counts(db, data["id"]) == (0, 3)
    resp = _update(client, promo, data["id"], num_tabler_passes=0)
    assert resp.status_code == 200
    assert _counts(db, data["id"]) == (3, 0)


def test_staff_pass_adjustment_makes_room(client, db, promo, venue):
    data = _create(client, promo, venue)
    resp = _update(client, promo, data["id"], staff_pass_adjustment=2)
    assert resp.status_code == 200
    assert _counts(db, data["id"]) == (3, 2)


# ── Claiming ──────────────────────────────────────────────────────────────────


def test_publicity_member_claims_a_tabler_pass(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    with patch(SEND_EMAIL) as send:
        resp = _claim_tabler(client, data["id"], pub)
    assert resp.status_code == 200, resp.text
    assert resp.json()["pass_type"] == "tabler"
    assert resp.json()["has_guest"] is False
    send.assert_not_called()
    show = client.get(f"/api/shows/{data['id']}", headers=_h(pub)).json()
    assert [t["staff_name"] for t in show["tablers"]] == ["Penny"]
    assert show["available_tabler_count"] == 1
    entry = db.query(AuditLog).filter(AuditLog.event_type == "pass_claimed").one()
    assert entry.area == PASS_GIVEAWAY_AREA


def test_new_student_in_publicity_can_claim(client, db, promo, venue):
    newbie = _make_staff(db, "Nova", "Publicity", status="🆕")
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    assert _claim_tabler(client, data["id"], newbie).status_code == 200


def test_non_publicity_staff_cant_claim(client, db, promo, venue, plain):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    resp = _claim_tabler(client, data["id"], plain)
    assert resp.status_code == 403


def test_one_tabler_pass_per_person(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    assert _claim_tabler(client, data["id"], pub).status_code == 200
    resp = _claim_tabler(client, data["id"], pub)
    assert resp.status_code == 400
    assert "already have a tabler pass" in resp.json()["detail"]


def test_all_tabler_passes_claimed(client, db, promo, venue, pub, pub2):
    data = _create(client, promo, venue, num_tabler_passes=1)
    _publish(db, data["id"])
    assert _claim_tabler(client, data["id"], pub).status_code == 200
    resp = _claim_tabler(client, data["id"], pub2)
    assert resp.status_code == 400
    assert "have been claimed" in resp.json()["detail"]


def test_tabler_cant_also_claim_staff_pass(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    assert _claim_tabler(client, data["id"], pub).status_code == 200
    resp = _claim_staff(client, db, data["id"], pub)
    assert resp.status_code == 400
    assert "tabler pass" in resp.json()["detail"]


def test_staff_pass_holder_cant_claim_tabler_pass(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    assert _claim_staff(client, db, data["id"], pub).status_code == 200
    resp = _claim_tabler(client, data["id"], pub)
    assert resp.status_code == 400
    assert "staff pass" in resp.json()["detail"]


def test_tabler_cant_join_alternate_list(client, db, promo, venue, pub, plain):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    assert _claim_staff(client, db, data["id"], plain).status_code == 200
    assert _claim_tabler(client, data["id"], pub).status_code == 200
    resp = client.post(f"/api/shows/{data['id']}/alternates", json={}, headers=_h(pub))
    assert resp.status_code == 400
    assert "tabler pass" in resp.json()["detail"]


def test_alternate_cant_claim_tabler_pass(client, db, promo, venue, pub, plain):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    assert _claim_staff(client, db, data["id"], plain).status_code == 200
    resp = client.post(f"/api/shows/{data['id']}/alternates", json={}, headers=_h(pub))
    assert resp.status_code == 201, resp.text
    resp = _claim_tabler(client, data["id"], pub)
    assert resp.status_code == 400
    assert "alternate list" in resp.json()["detail"]


def test_tabler_passes_are_first_come_on_lottery_shows(client, db, promo, venue, pub):
    data = _create(client, promo, venue, lottery_enabled=True)
    _publish(db, data["id"])
    assert _claim_tabler(client, data["id"], pub).status_code == 200


def test_tabler_cant_enter_lottery(client, db, promo, venue, pub):
    data = _create(client, promo, venue, lottery_enabled=True)
    _publish(db, data["id"])
    assert _claim_tabler(client, data["id"], pub).status_code == 200
    resp = client.post(
        f"/api/shows/{data['id']}/lottery/enter/staff", json={}, headers=_h(pub)
    )
    assert resp.status_code == 400
    assert "tabler pass" in resp.json()["detail"]


def test_no_claims_after_close(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    show = _publish(db, data["id"])
    show.status = "closed"
    db.commit()
    assert _claim_tabler(client, data["id"], pub).status_code == 400


def test_tabler_releases_own_pass(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    pass_id = _claim_tabler(client, data["id"], pub).json()["id"]
    with patch(SEND_EMAIL) as send:
        resp = client.delete(f"/api/passes/{pass_id}/claim", headers=_h(pub))
    assert resp.status_code == 200
    assert resp.json()["pass_type"] == "tabler"
    assert resp.json()["status"] == "available"
    send.assert_not_called()


def test_my_claims_include_tabler_pass(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    _claim_tabler(client, data["id"], pub)
    claims = client.get("/api/passes/staff/my-claims", headers=_h(pub)).json()
    assert [c["pass_type"] for c in claims] == ["tabler"]


# ── Promotions ────────────────────────────────────────────────────────────────


def test_promotions_assigns_any_current_staff(client, db, promo, venue, plain):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    with patch(SEND_EMAIL) as send:
        resp = client.post(
            f"/api/shows/{data['id']}/tabler-passes/assign",
            json={"staff_id": plain.id},
            headers=_h(promo),
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["staff_id"] == plain.id
    assert send.call_args.kwargs["to_email"] == plain.email
    assert "tabler pass" in send.call_args.kwargs["subject"]
    # The assigned tabler can release it themselves
    resp = client.delete(f"/api/passes/{resp.json()['id']}/claim", headers=_h(plain))
    assert resp.status_code == 200


def test_staff_cant_assign(client, db, promo, venue, pub, plain):
    data = _create(client, promo, venue)
    resp = client.post(
        f"/api/shows/{data['id']}/tabler-passes/assign",
        json={"staff_id": plain.id},
        headers=_h(pub),
    )
    assert resp.status_code == 403


def test_promotions_release_emails_tabler(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    pass_id = _claim_tabler(client, data["id"], pub).json()["id"]
    with patch(SEND_EMAIL) as send:
        resp = client.delete(f"/api/passes/{pass_id}/claim", headers=_h(promo))
    assert resp.status_code == 200
    assert send.call_args.kwargs["to_email"] == pub.email
    assert "released" in send.call_args.kwargs["subject"]


# ── Lowering counts ───────────────────────────────────────────────────────────


def test_lowering_count_with_claims_needs_confirmation(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    _claim_tabler(client, data["id"], pub)
    # The unclaimed one goes without asking
    assert _update(client, promo, data["id"], num_tabler_passes=1).status_code == 200
    resp = _update(client, promo, data["id"], num_tabler_passes=0)
    assert resp.status_code == 409
    assert resp.json()["detail"]["tablers"] == ["Penny"]
    assert _counts(db, data["id"]) == (2, 1)

    with patch(SEND_EMAIL) as send:
        resp = _update(
            client, promo, data["id"], num_tabler_passes=0, confirm_release_tablers=True
        )
    assert resp.status_code == 200
    assert _counts(db, data["id"]) == (3, 0)
    assert send.call_args.kwargs["to_email"] == pub.email


def test_turning_off_co_announce_releases_tablers(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    _claim_tabler(client, data["id"], pub)
    resp = _update(client, promo, data["id"], co_announce=False)
    assert resp.status_code == 409
    with patch(SEND_EMAIL):
        resp = _update(
            client, promo, data["id"], co_announce=False, confirm_release_tablers=True
        )
    assert resp.status_code == 200
    assert resp.json()["num_tabler_passes"] == 0
    assert _counts(db, data["id"]) == (3, 0)


def test_freed_tabler_pass_goes_to_alternate(client, db, promo, venue, pub, plain):
    data = _create(client, promo, venue, num_pass_pairs=2, num_tabler_passes=1)
    _publish(db, data["id"])
    first = _make_staff(db, "Fay")
    assert _claim_staff(client, db, data["id"], first).status_code == 200
    resp = client.post(f"/api/shows/{data['id']}/alternates", json={}, headers=_h(plain))
    assert resp.status_code == 201, resp.text
    with patch(SEND_EMAIL):
        assert _update(client, promo, data["id"], num_tabler_passes=0).status_code == 200
    entry = db.query(StaffPassAlternate).filter_by(staff_id=plain.id).one()
    assert entry.status == "promoted"


def test_lowering_staff_passes_removes_unclaimed_tabler_passes_before_claims(
    client, db, promo, venue, plain
):
    # 3 staff passes: 1 staff (claimed) and 2 tabler (unclaimed)
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    assert _claim_staff(client, db, data["id"], plain).status_code == 200
    resp = _update(client, promo, data["id"], num_pass_pairs=2, num_tabler_passes=1)
    assert resp.status_code == 200, resp.text
    assert _counts(db, data["id"]) == (1, 1)
    # Lowering only the pairs takes the unclaimed tabler pass, not the staff claim
    resp = _update(client, promo, data["id"], num_pass_pairs=1)
    assert resp.status_code == 200, resp.text
    assert resp.json()["num_tabler_passes"] == 0
    assert _counts(db, data["id"]) == (1, 0)


def test_lowering_staff_passes_bumps_tabler_claims_last(
    client, db, promo, venue, pub, plain
):
    data = _create(client, promo, venue, num_pass_pairs=2, num_tabler_passes=1)
    _publish(db, data["id"])
    assert _claim_staff(client, db, data["id"], plain).status_code == 200
    assert _claim_tabler(client, data["id"], pub).status_code == 200
    # Down to 1 staff pass: the staff claim goes first
    with patch(SEND_EMAIL):
        resp = _update(client, promo, data["id"], num_pass_pairs=1, staff_pass_adjustment=0)
    assert resp.status_code == 200, resp.text
    assert _counts(db, data["id"]) == (0, 1)
    # Down to 0: the tabler claim goes, after confirming
    resp = _update(client, promo, data["id"], staff_pass_adjustment=-1)
    assert resp.status_code == 409
    with patch(SEND_EMAIL) as send:
        resp = _update(
            client,
            promo,
            data["id"],
            staff_pass_adjustment=-1,
            confirm_release_tablers=True,
        )
    assert resp.status_code == 200, resp.text
    assert _counts(db, data["id"]) == (0, 0)
    assert any(c.kwargs["to_email"] == pub.email for c in send.call_args_list)
    assert "Penny" in [s["name"] for s in resp.json()["pass_adjustment"]["affected_staff"]]


# ── Guest list and cancellation ───────────────────────────────────────────────


def test_guest_list_marks_tablers(client, db, promo, venue, pub, plain):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    _claim_staff(client, db, data["id"], plain)
    _claim_tabler(client, data["id"], pub)
    db.expire_all()
    show = db.query(Show).filter(Show.id == data["id"]).one()
    lines = ShowService._build_guest_list_text(show).splitlines()
    assert "1 pass for Sam" in lines
    assert "1 pass for Penny (KALX Co-Announce Table)" in lines


def test_deleting_show_tells_tablers(client, db, promo, venue, pub):
    data = _create(client, promo, venue)
    _publish(db, data["id"])
    _claim_tabler(client, data["id"], pub)
    with patch(SEND_EMAIL) as send:
        resp = client.delete(f"/api/shows/{data['id']}", headers=_h(promo))
    assert resp.status_code == 204
    to_pub = [c for c in send.call_args_list if c.kwargs["to_email"] == pub.email]
    assert to_pub and "tabler pass" in to_pub[0].kwargs["body_text"]
