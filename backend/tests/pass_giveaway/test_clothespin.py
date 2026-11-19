"""Tests for Clothespin: a DJ reserving a pass pair for today from the DJ shows page."""

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.common.services.leave_service import today_pt
from app.models.audit_log import AuditLog
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.specialty_show import SpecialtyShow
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from tests.personas import add_persona, dj_fields, persona_id

DJ_STUDIO = {"X-Forwarded-For": "192.168.1.100"}  # within default dj_studio_network


def _add_staff(
    db: Session,
    email: str,
    statuses: list[str],
    dj_name: str | None = None,
    department: str | None = None,
) -> Staff:
    """Create a staff member with the given statuses."""
    names = [n.strip() for n in (dj_name or "").split(",") if n.strip()]
    staff = Staff(
        email=email, name=email.split("@")[0], phone="555-0100", **dj_fields(*names)
    )
    db.add(staff)
    db.flush()
    for s in statuses:
        db.add(StaffStatus(staff_id=staff.id, status=s))
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def dj(db: Session) -> Staff:
    """An Active Sublist DJ with two DJ names."""
    return _add_staff(db, "wolf@test.com", ["Active", "Sublist DJ"], "DJ Wolfman, Wolfie")


@pytest.fixture
def show(db: Session) -> Show:
    """A published show, closing in 10 days, with two available pass pairs."""
    venue = Venue(name="Test Venue", address="123 Test St")
    db.add(venue)
    db.flush()
    show = Show(
        event_name="Test Show",
        genre=["Rock"],
        venue_id=venue.id,
        show_date=today_pt() + timedelta(days=14),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=2,
        status="published",
        planned_close_date=today_pt() + timedelta(days=10),
    )
    db.add(show)
    db.flush()
    for _ in range(2):
        db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    db.add(Pass(show_id=show.id, pass_type="staff", status="available"))
    db.commit()
    db.refresh(show)
    return show


def _clothespin(client, show_id: int, headers=None):
    return client.post(
        f"/api/shows/{show_id}/clothespin",
        headers=DJ_STUDIO if headers is None else headers,
    )


def _summary(client, show_id: int) -> dict:
    response = client.get("/api/shows", headers=DJ_STUDIO)
    assert response.status_code == 200
    return next(s for s in response.json() if s["id"] == show_id)


@pytest.fixture(autouse=True)
def wolfman_on_air(db: Session, dj: Staff, on_air):
    """The dj fixture's "DJ Wolfman" persona is on air, unless a test says otherwise."""
    return on_air(persona_id=persona_id(dj, "DJ Wolfman"), name="DJ Wolfman")


def test_reserves_a_pair_for_today_for_who_is_on_air(client, db, show, dj):
    """A studio DJ reserves an unclaimed pair for today for the on-air persona,
    and the reservation is audited."""
    response = _clothespin(client, show.id)

    assert response.status_code == 200
    body = response.json()
    assert body["pass_type"] == "pair"
    assert body["preassigned_dj"] == "DJ Wolfman"
    assert body["preassigned_persona_id"] == persona_id(dj, "DJ Wolfman")
    assert body["preassigned_date"] == today_pt().isoformat()
    assert body["preassigned_specialty_show_id"] is None

    entry = db.query(AuditLog).filter(AuditLog.event_type == "pass_preassigned").one()
    assert entry.actor_role == "dj"
    assert entry.entity_id == body["id"]
    assert entry.details["source"] == "clothespin"
    assert entry.details["dj"] == "DJ Wolfman"


def test_any_of_a_djs_personas_counts(client, show, dj, on_air):
    on_air(persona_id=persona_id(dj, "Wolfie"), name="Wolfie")
    response = _clothespin(client, show.id)
    assert response.status_code == 200
    assert response.json()["preassigned_dj"] == "Wolfie"


def test_new_student_persona_counts(client, db, show, on_air):
    """A 🆕 staff member's persona is a current staff persona."""
    newbie = _add_staff(db, "new@test.com", ["🆕"], "DJ Newbie")
    on_air(persona_id=persona_id(newbie, "DJ Newbie"), name="DJ Newbie")
    assert _clothespin(client, show.id).status_code == 200


def test_no_one_on_air_is_refused(client, show, on_air):
    on_air(None)
    response = _clothespin(client, show.id)
    assert response.status_code == 400
    assert "No one is on air" in response.json()["detail"]


def test_former_staff_persona_is_refused(client, db, show, on_air):
    """A persona of someone who isn't current staff doesn't count."""
    gone = _add_staff(db, "gone@test.com", ["Inactive"], "DJ Gone")
    on_air(persona_id=persona_id(gone, "DJ Gone"), name="DJ Gone")
    response = _clothespin(client, show.id)
    assert response.status_code == 400
    assert response.json()["detail"] == "DJ Gone isn't linked to a current staff member"


@pytest.mark.parametrize("category", ["music", "talk"])
def test_during_a_specialty_show_the_reservation_is_the_shows(
    client, db, show, dj, on_air, category
):
    specialty = SpecialtyShow(name="Pacific Drift", category=category)
    db.add(specialty)
    db.commit()
    on_air(
        kind=category,
        name="Pacific Drift",
        specialty_show_id=specialty.id,
        persona_id=persona_id(dj, "DJ Wolfman") if category == "music" else None,
    )

    response = _clothespin(client, show.id)

    assert response.status_code == 200
    assert response.json()["preassigned_dj"] == "Pacific Drift"
    assert response.json()["preassigned_specialty_show_id"] == specialty.id
    assert response.json()["preassigned_persona_id"] is None


def test_signed_in_staff_outside_the_studio_cannot_clothespin(client, db, show, dj):
    """Outside the studio, in production, signed-in staff (even promotions) can't."""
    promo = _add_staff(db, "promo@test.com", ["Active"], department="Promotions")
    for email in (dj.email, promo.email):
        response = _clothespin(client, show.id, {"X-Forwarded-User": email})
        assert response.status_code == 401


def test_staging_sublist_dj_can_clothespin(client, show, dj, monkeypatch):
    """In staging a signed-in Sublist DJ can test Clothespin remotely."""
    from app import config

    monkeypatch.setattr(config.settings, "environment", "staging")
    response = _clothespin(client, show.id, {"X-Forwarded-User": dj.email})
    assert response.status_code == 200


def test_skips_pairs_reserved_for_other_djs(client, db, show, dj, on_air):
    """Only an unclaimed pair is reserved; once none are left, it's refused."""
    pairs = db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "pair").all()
    pairs[0].preassigned_persona_id = add_persona(db, "Someone Else")
    pairs[0].preassigned_date = today_pt()
    db.commit()

    first = _clothespin(client, show.id)
    assert first.status_code == 200
    assert first.json()["id"] == pairs[1].id

    on_air(persona_id=persona_id(dj, "Wolfie"), name="Wolfie")
    second = _clothespin(client, show.id)
    assert second.status_code == 409
    assert second.json()["detail"] == "No unclaimed pass pairs are left for this show"

    db.refresh(pairs[0])
    assert pairs[0].preassigned_to == "Someone Else"


def test_refuses_a_second_pair_for_today(client, show, dj):
    """A DJ who already has a pair reserved for today can't take another."""
    assert _clothespin(client, show.id).status_code == 200
    response = _clothespin(client, show.id)
    assert response.status_code == 409
    assert "already has a pass pair reserved for today" in response.json()["detail"]


def test_a_reservation_for_another_day_does_not_block(client, db, show, dj):
    """A pair the DJ reserved for another date doesn't stop a reservation for today."""
    pair = db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "pair").first()
    pair.preassigned_persona_id = persona_id(dj, "DJ Wolfman")
    pair.preassigned_date = today_pt() + timedelta(days=3)
    db.commit()

    response = _clothespin(client, show.id)
    assert response.status_code == 200
    assert response.json()["id"] != pair.id


@pytest.mark.parametrize(
    "change, detail",
    [
        (
            lambda show: (
                setattr(show, "lottery_enabled", True),
                setattr(show, "lottery_window_hours", 24),
                setattr(show, "published_at", datetime.now(timezone.utc)),
            ),
            "DJ lottery is still open",
        ),
        (
            lambda show: setattr(show, "dj_preassign_prohibition_days", 14),
            "not allowed within",
        ),
        (
            lambda show: setattr(
                show, "planned_close_date", today_pt() - timedelta(days=1)
            ),
            "planned close date has passed",
        ),
        (lambda show: setattr(show, "status", "closed"), "published shows"),
    ],
    ids=["lottery", "prohibition-window", "past-close-date", "closed"],
)
def test_show_rules_block_clothespin(client, db, show, dj, change, detail):
    """The show's rules refuse Clothespin, and the show list says it isn't available."""
    assert _summary(client, show.id)["clothespin_available"] is True
    assert _summary(client, show.id)["unassigned_pair_count"] == 2

    change(show)
    db.commit()

    response = _clothespin(client, show.id)
    assert response.status_code == 409
    assert detail in response.json()["detail"]
    if show.status == "published":
        assert _summary(client, show.id)["clothespin_available"] is False


def test_prohibition_window_allows_dates_outside_it(client, db, show, dj):
    """A prohibition window that today is outside of doesn't block."""
    show.dj_preassign_prohibition_days = 5
    db.commit()
    assert _clothespin(client, show.id).status_code == 200


def test_show_list_reports_no_unclaimed_pairs(client, db, show, dj):
    """The show list says Clothespin isn't available once every pair is claimed."""
    for pair in db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "pair"):
        pair.preassigned_persona_id = add_persona(db, "Someone Else")
        pair.preassigned_date = today_pt()
    db.commit()

    summary = _summary(client, show.id)
    assert summary["available_pair_count"] == 2
    assert summary["unassigned_pair_count"] == 0
    assert summary["clothespin_available"] is False


def test_unknown_show_is_404(client, dj):
    """Clothespin on a show that doesn't exist is a 404."""
    assert _clothespin(client, 9999).status_code == 404


def test_my_giveaways_lists_the_reservation(client, show, dj):
    """The on-air DJ's pre-assigned list has their Clothespin reservation."""
    reserved = _clothespin(client, show.id).json()

    response = client.get("/api/passes/my-giveaways", headers=DJ_STUDIO)
    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [reserved["id"]]
