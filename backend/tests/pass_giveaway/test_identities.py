"""Tests for pre-assigning to personas and shows (phase 2b of the Spinitron identity plan).

Promotions pre-assign a pass pair to a staff member's persona or a show; staff
reserve (and enter the DJ lottery) as one of their own personas or a show
they're a member of; music show DJs are personas.
"""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.lottery_entry import LotteryEntry
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_dj import SpecialtyShowDJ
from app.models.specialty_show_spinitron_show import SpecialtyShowSpinitronShow
from app.models.spinitron_persona import SpinitronPersona
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.talk_show_staff import TalkShowStaff
from app.models.venue import Venue
from app.pass_giveaway.services.lottery_service import LotteryService
from tests.personas import dj_fields

PROMO = {"X-Forwarded-User": "promo@id.test"}
WOLF = {"X-Forwarded-User": "wolf@id.test"}

WOLFMAN, WOLFIE, OLD_NAME, OWL = 501, 502, 503, 601
SCHEDULE = "app.pass_giveaway.routers.passes.SpinitronUpcomingScheduleService"
SEND_EMAIL = "app.common.services.notification_service.send_email"


def _staff(db: Session, email: str, *statuses: str, personas=(), department=None):
    names = [n for _, n in personas]
    staff = Staff(
        email=email,
        name=email.split("@")[0].title(),
        phone="555-0100",
        **dj_fields(*names, ids=[i for i, _ in personas]),
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
def promo(db: Session) -> Staff:
    return _staff(db, "promo@id.test", "Active", department="Promotions")


@pytest.fixture
def wolf(db: Session) -> Staff:
    """A Sublist DJ with two personas."""
    return _staff(
        db,
        "wolf@id.test",
        "Active",
        "Sublist DJ",
        personas=[(WOLFMAN, "DJ Wolfman"), (WOLFIE, "Wolfie")],
    )


@pytest.fixture
def owl(db: Session) -> Staff:
    return _staff(db, "owl@id.test", "Active", "Sublist DJ", personas=[(OWL, "Nightowl")])


def _specialty(db: Session, name: str, category="music", dj_personas=()) -> SpecialtyShow:
    show = SpecialtyShow(name=name, category=category)
    db.add(show)
    db.flush()
    db.add(
        SpecialtyShowSpinitronShow(
            specialty_show_id=show.id, spinitron_show_id=900 + show.id
        )
    )
    for persona_id, name in dj_personas:
        db.add(
            SpecialtyShowDJ(specialty_show_id=show.id, dj_name=name, persona_id=persona_id)
        )
    db.commit()
    db.refresh(show)
    return show


def _show(db: Session, lottery=False, pairs=1) -> Show:
    venue = Venue(name="Identity Venue", address="1 Radio St")
    db.add(venue)
    db.flush()
    show = Show(
        event_name="Identity Show",
        venue_id=venue.id,
        show_date=date.today() + timedelta(days=30),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=pairs,
        status="published",
        lottery_enabled=lottery,
        lottery_window_hours=24,
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(show)
    db.flush()
    for _ in range(pairs):
        db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    db.commit()
    db.refresh(show)
    return show


def _pair(db: Session, show: Show) -> Pass:
    return db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "pair").first()


def _soon() -> str:
    return (date.today() + timedelta(days=3)).isoformat()


# ── Promotions ────────────────────────────────────────────────────────────────


def test_promotions_identities_list_staff_personas_then_shows(
    client: TestClient, db: Session, promo, wolf, owl
):
    _staff(db, "gone@id.test", personas=[(700, "Former DJ")])  # not current staff
    talk = _specialty(db, "Morning Report", category="talk")
    music = _specialty(db, "Take Five")

    response = client.get("/api/passes/preassign/identities", headers=PROMO)

    assert response.status_code == 200
    assert [
        (i["name"], i["kind"], i["persona_id"], i["specialty_show_id"])
        for i in response.json()
    ] == [
        ("DJ Wolfman", "persona", WOLFMAN, None),
        ("Nightowl", "persona", OWL, None),
        ("Wolfie", "persona", WOLFIE, None),
        ("Morning Report", "talk", None, talk.id),
        ("Take Five", "music", None, music.id),
    ]
    assert response.json()[0]["staff_name"] == "Wolf"


def test_promotions_identities_hide_inactive_personas(
    client: TestClient, db: Session, promo, wolf
):
    now = datetime.now(timezone.utc)
    db.add(SpinitronPersona(id=WOLFMAN, name="DJ Wolfman", last_playlist_at=now))
    db.add(
        SpinitronPersona(
            id=WOLFIE, name="Wolfie", last_playlist_at=now - timedelta(days=400)
        )
    )
    db.commit()

    response = client.get("/api/passes/preassign/identities", headers=PROMO)

    assert [i["name"] for i in response.json()] == ["DJ Wolfman"]


def test_promotions_preassign_to_a_show(client: TestClient, db: Session, promo):
    talk = _specialty(db, "Morning Report", category="talk")
    pair = _pair(db, _show(db))

    response = client.post(
        f"/api/passes/{pair.id}/preassign",
        json={"specialty_show_id": talk.id, "assignment_date": _soon()},
        headers=PROMO,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["preassigned_dj"] == "Morning Report"
    assert data["preassigned_specialty_show_id"] == talk.id
    assert data["preassigned_persona_id"] is None


def test_promotions_preassign_uses_the_personas_current_name(
    client: TestClient, db: Session, promo, wolf
):
    db.add(SpinitronPersona(id=WOLFMAN, name="DJ Wolfman Jack"))
    db.commit()
    pair = _pair(db, _show(db))

    response = client.post(
        f"/api/passes/{pair.id}/preassign",
        json={"persona_id": WOLFMAN, "assignment_date": _soon()},
        headers=PROMO,
    )

    assert response.json()["preassigned_dj"] == "DJ Wolfman Jack"


@pytest.mark.parametrize(
    "body",
    [
        {"persona_id": 999},  # no current staff member holds it
        {},  # neither
        {"persona_id": WOLFMAN, "specialty_show_id": 1},  # both
    ],
)
def test_promotions_preassign_refuses_a_bad_identity(
    client: TestClient, db: Session, promo, wolf, body
):
    pair = _pair(db, _show(db))

    response = client.post(
        f"/api/passes/{pair.id}/preassign",
        json={**body, "assignment_date": _soon()},
        headers=PROMO,
    )

    assert response.status_code in (400, 422)
    db.refresh(pair)
    assert pair.preassigned_dj is None


def test_removing_a_preassignment_clears_the_persona(
    client: TestClient, db: Session, promo, wolf
):
    pair = _pair(db, _show(db))
    client.post(
        f"/api/passes/{pair.id}/preassign",
        json={"persona_id": WOLFMAN, "assignment_date": _soon()},
        headers=PROMO,
    )

    response = client.delete(f"/api/passes/{pair.id}/preassign", headers=WOLF)

    assert response.status_code == 200, response.text
    assert response.json()["preassigned_persona_id"] is None


def test_staff_cannot_remove_someone_elses_persona_preassignment(
    client: TestClient, db: Session, promo, wolf, owl
):
    pair = _pair(db, _show(db))
    client.post(
        f"/api/passes/{pair.id}/preassign",
        json={"persona_id": OWL, "assignment_date": _soon()},
        headers=PROMO,
    )

    response = client.delete(f"/api/passes/{pair.id}/preassign", headers=WOLF)

    assert response.status_code == 403


def test_leave_lookup_is_by_persona(client: TestClient, db: Session, promo, wolf):
    wolf.loa_start = date.today()
    db.commit()

    response = client.get(
        "/api/passes/preassign/leave", params={"persona_id": WOLFIE}, headers=PROMO
    )

    assert response.json() == {"loa_start": date.today().isoformat(), "loa_end": None}


# ── Staff reserving for themselves ────────────────────────────────────────────


def test_my_identities_list_my_personas_and_shows_with_their_schedules(
    client: TestClient, db: Session, wolf, monkeypatch
):
    music = _specialty(db, "Take Five", dj_personas=[(WOLFIE, "Wolfie")])
    talk = _specialty(db, "Morning Report", category="talk")
    db.add(TalkShowStaff(specialty_show_id=talk.id, staff_id=wolf.id))
    _specialty(db, "Someone Else's Show")
    db.commit()

    async def fake_schedule(db, persona_id=None, specialty_show_id=None):
        if persona_id == WOLFIE:
            return {
                "dates": ["2026-12-01"],
                "talk_show_dates": {"2026-12-02": "Morning Report"},
            }
        return {"dates": [], "talk_show_dates": {}}

    monkeypatch.setattr(f"{SCHEDULE}.get_identity_schedule", fake_schedule)

    response = client.get("/api/passes/preassign/my-identities", headers=WOLF)

    assert response.status_code == 200
    data = response.json()
    assert [(i["name"], i["kind"]) for i in data] == [
        ("DJ Wolfman", "persona"),
        ("Wolfie", "persona"),
        ("Morning Report", "talk"),
        ("Take Five", "music"),
    ]
    assert data[1]["dates"] == ["2026-12-01"]
    assert data[1]["talk_show_dates"] == {"2026-12-02": "Morning Report"}
    assert data[3]["specialty_show_id"] == music.id


def test_self_preassign_as_a_chosen_persona(client: TestClient, db: Session, wolf):
    pair = _pair(db, _show(db))

    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json={"assignment_date": _soon(), "persona_id": WOLFIE},
        headers=WOLF,
    )

    assert response.status_code == 200, response.text
    assert response.json()["preassigned_dj"] == "Wolfie"
    assert response.json()["preassigned_persona_id"] == WOLFIE


def test_self_preassign_defaults_to_my_first_persona(client: TestClient, db: Session, wolf):
    pair = _pair(db, _show(db))

    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json={"assignment_date": _soon()},
        headers=WOLF,
    )

    assert response.json()["preassigned_persona_id"] == WOLFMAN


def test_self_preassign_refuses_someone_elses_persona(
    client: TestClient, db: Session, wolf, owl
):
    pair = _pair(db, _show(db))

    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json={"assignment_date": _soon(), "persona_id": OWL},
        headers=WOLF,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "That isn't one of your DJ personas"


def test_self_preassign_for_my_music_show_is_the_shows(
    client: TestClient, db: Session, wolf
):
    music = _specialty(db, "Take Five", dj_personas=[(WOLFIE, "Wolfie")])
    pair = _pair(db, _show(db))

    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json={"assignment_date": _soon(), "specialty_show_id": music.id},
        headers=WOLF,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["preassigned_dj"] == "Take Five"
    assert data["preassigned_specialty_show_id"] == music.id
    assert data["preassigned_persona_id"] is None


def test_music_show_membership_is_by_persona_not_name(
    client: TestClient, db: Session, wolf, owl
):
    """A DJ row with Wolfie's name but another persona doesn't make Wolf a member."""
    music = _specialty(db, "Take Five", dj_personas=[(OWL, "Wolfie")])
    pair = _pair(db, _show(db))

    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json={"assignment_date": _soon(), "specialty_show_id": music.id},
        headers=WOLF,
    )

    assert response.status_code == 403


# ── DJ lottery ────────────────────────────────────────────────────────────────


def test_dj_lottery_entry_keeps_the_persona_and_the_draw_copies_it(
    client: TestClient, db: Session, wolf
):
    show = _show(db, lottery=True)

    response = client.post(
        f"/api/shows/{show.id}/lottery/enter/dj",
        json={"assignment_date": _soon(), "persona_id": WOLFIE},
        headers=WOLF,
    )

    assert response.status_code == 201, response.text
    assert response.json()["persona_id"] == WOLFIE
    assert response.json()["dj_name"] == "Wolfie"

    with patch(SEND_EMAIL):
        LotteryService.run_lottery(db, show.id)

    pair = _pair(db, show)
    assert (pair.preassigned_dj, pair.preassigned_persona_id) == ("Wolfie", WOLFIE)


def test_dj_lottery_entry_for_a_music_show_keeps_the_member_persona(
    client: TestClient, db: Session, wolf
):
    music = _specialty(db, "Take Five", dj_personas=[(WOLFIE, "Wolfie")])
    show = _show(db, lottery=True)

    response = client.post(
        f"/api/shows/{show.id}/lottery/enter/dj",
        json={"assignment_date": _soon(), "specialty_show_id": music.id},
        headers=WOLF,
    )

    assert response.status_code == 201, response.text
    entry = db.query(LotteryEntry).one()
    assert (entry.persona_id, entry.dj_name, entry.specialty_show_id) == (
        WOLFIE,
        "Wolfie",
        music.id,
    )

    with patch(SEND_EMAIL):
        LotteryService.run_lottery(db, show.id)

    pair = _pair(db, show)
    assert pair.preassigned_specialty_show_id == music.id
    assert pair.preassigned_persona_id is None


# ── Clothespin ────────────────────────────────────────────────────────────────


def test_clothespin_records_the_typed_names_persona(client: TestClient, db: Session, wolf):
    show = _show(db)
    show.planned_close_date = date.today() + timedelta(days=10)
    db.commit()

    response = client.post(
        f"/api/shows/{show.id}/clothespin",
        json={"dj_name": "wolfie"},
        headers={"X-Forwarded-For": "192.168.1.100"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["preassigned_persona_id"] == WOLFIE


# ── Music show DJ editor ──────────────────────────────────────────────────────


def test_dj_editor_adds_and_removes_personas(
    client: TestClient, db: Session, promo, wolf, owl
):
    music = _specialty(db, "Take Five", dj_personas=[(OWL, "Nightowl")])

    response = client.put(
        f"/api/specialty-shows/{music.id}",
        json={"dj_persona_ids": [WOLFIE]},
        headers=PROMO,
    )

    assert response.status_code == 200, response.text
    assert response.json()["djs"] == [{"persona_id": WOLFIE, "name": "Wolfie"}]
    row = db.query(SpecialtyShowDJ).one()
    assert (row.persona_id, row.dj_name) == (WOLFIE, "Wolfie")


def test_dj_editor_refuses_a_persona_no_current_staff_member_holds(
    client: TestClient, db: Session, promo
):
    music = _specialty(db, "Take Five")

    response = client.put(
        f"/api/specialty-shows/{music.id}", json={"dj_persona_ids": [999]}, headers=PROMO
    )

    assert response.status_code == 400
    assert db.query(SpecialtyShowDJ).count() == 0


def test_dj_editor_keeps_a_dj_who_is_no_longer_staff(
    client: TestClient, db: Session, promo, wolf
):
    music = _specialty(db, "Take Five", dj_personas=[(OLD_NAME, "Old DJ")])

    response = client.put(
        f"/api/specialty-shows/{music.id}",
        json={"dj_persona_ids": [OLD_NAME, WOLFMAN]},
        headers=PROMO,
    )

    assert response.status_code == 200, response.text
    assert [d["persona_id"] for d in response.json()["djs"]] == [OLD_NAME, WOLFMAN]


def test_dj_editor_keeps_djs_with_no_persona(client: TestClient, db: Session, promo, wolf):
    music = _specialty(db, "Take Five")
    db.add(SpecialtyShowDJ(specialty_show_id=music.id, dj_name="Unmatched Name"))
    db.commit()

    response = client.put(
        f"/api/specialty-shows/{music.id}",
        json={"dj_persona_ids": [WOLFMAN]},
        headers=PROMO,
    )

    assert response.status_code == 200, response.text
    assert response.json()["djs"] == [
        {"persona_id": None, "name": "Unmatched Name"},
        {"persona_id": WOLFMAN, "name": "DJ Wolfman"},
    ]


def test_dj_options_offer_staff_personas_and_the_shows_own_djs(
    client: TestClient, db: Session, promo, wolf
):
    now = datetime.now(timezone.utc)
    db.add(SpinitronPersona(id=WOLFMAN, name="DJ Wolfman", last_playlist_at=now))
    db.add(SpinitronPersona(id=WOLFIE, name="Wolfie"))  # no recent playlist
    db.commit()
    music = _specialty(db, "Take Five", dj_personas=[(WOLFIE, "Wolfie")])

    everyone = client.get("/api/specialty-shows/dj-options", headers=PROMO).json()
    for_show = client.get(
        "/api/specialty-shows/dj-options", params={"show_id": music.id}, headers=PROMO
    ).json()

    assert [o["persona_id"] for o in everyone] == [WOLFMAN]
    assert [o["persona_id"] for o in for_show] == [WOLFMAN, WOLFIE]


def test_mine_lists_music_shows_by_persona(client: TestClient, db: Session, wolf):
    music = _specialty(db, "Take Five", dj_personas=[(WOLFIE, "Wolfie")])

    response = client.get("/api/specialty-shows/mine", headers=WOLF)

    assert [(s["id"], s["is_dj"]) for s in response.json()] == [(music.id, True)]
