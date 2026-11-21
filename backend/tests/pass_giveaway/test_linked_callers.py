"""Tests for linked callers (docs/pass-giveaway/specs/linked-callers/plan.md)."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.areas import PASS_GIVEAWAY_AREA
from app.models.audit_log import AuditLog
from app.models.on_air_caller import (
    CommonCallerName,
    DismissedCallerPair,
    OnAirCaller,
    OnAirCallerPhone,
)
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue

URL = "/api/pass-giveaway/admin/callers"
DJ_STUDIO = {"X-Forwarded-For": "192.168.1.100"}  # in the default dj_studio_network
NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _staff(db: Session, email: str, department: str | None = None) -> dict:
    staff = Staff(email=email, name=email.split("@")[0].title(), phone="555")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    return {"X-Forwarded-User": email}


@pytest.fixture
def promo(db: Session) -> dict:
    return _staff(db, "promo@test.com", "Promotions")


def _venue(db: Session, name: str, days: int | None = None) -> Venue:
    venue = Venue(name=name, address=f"1 {name} St", win_frequency_days=days)
    db.add(venue)
    db.commit()
    return venue


def _show(db: Session, venue: Venue, show_date: date, name: str) -> Show:
    show = Show(
        event_name=name,
        venue_id=venue.id,
        show_date=show_date,
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=1,
        status="published",
    )
    db.add(show)
    db.flush()
    db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    db.commit()
    return show


def _win(db: Session, show: Show, name: str, phone: str, days_ago: int = 1, email=None):
    p = Pass(show_id=show.id, pass_type="pair", status="given_away")
    db.add(p)
    db.flush()
    db.add(
        OnAirWinner(
            pass_id=p.id,
            venue_id=show.venue_id,
            show_id=show.id,
            recipient_name=name,
            recipient_phone=phone,
            recipient_email=email,
            created_at=NOW - timedelta(days=days_ago),
        )
    )
    db.commit()


def _events(db: Session, event_type: str) -> list[AuditLog]:
    return db.query(AuditLog).filter(AuditLog.event_type == event_type).all()


@pytest.fixture
def arena(db: Session) -> Venue:
    return _venue(db, "The Arena", days=30)


@pytest.fixture
def greek(db: Session) -> Venue:
    return _venue(db, "The Greek Theater")


# ---------------------------------------------------------------------------
# The limit check


def test_john_doe_example(client: TestClient, db, promo, arena, greek):
    """The example from the feature request, end to end."""
    _win(db, _show(db, arena, date(2026, 6, 15), "Radiohead"), "John Doe", "2125555555", 6)
    _win(
        db,
        _show(db, greek, date(2026, 6, 17), "The Chainsmokers"),
        "John Doe",
        "2128888888",
    )
    glitch = _show(db, arena, date(2026, 6, 20), "Glitch Mob")

    def check():
        return client.get(
            f"/api/venues/{arena.id}/check-winner",
            params={"phone": "212-888-8888", "show_id": glitch.id},
            headers=DJ_STUDIO,
        ).json()

    assert check() == {"eligible": True, "reason": None}

    suggestion = client.get(f"{URL}/suggestions", headers=promo).json()
    assert [s["name"] for s in suggestion] == ["John Doe"]
    assert suggestion[0]["status"] == "unreviewed"
    linked = client.post(
        URL,
        json={"phones": ["212-555-5555", "(212) 888-8888"], "note": "Same voice"},
        headers=promo,
    )
    assert linked.status_code == 200, linked.text
    assert [p["phone"] for p in linked.json()["phones"]] == ["2125555555", "2128888888"]

    data = check()
    assert data["eligible"] is False
    assert data["last_win_show"] == "Radiohead"
    assert data["last_win_venue"] == "The Arena"
    assert data["days_since"] == 5
    assert data["linked_number"] is True
    # The DJ never sees the other number
    assert "2125555555" not in str(data)
    warning = _events(db, "winner_frequency_warning")[-1]
    assert warning.details["matched_phone"] == "2125555555"
    assert warning.details["linked_number"] is True

    pair = db.query(Pass).filter(Pass.show_id == glitch.id).one()
    response = client.post(
        f"/api/passes/{pair.id}/giveaway",
        json={"recipient_name": "John Doe", "recipient_phone": "2128888888"},
        headers=DJ_STUDIO,
    )
    assert response.status_code == 200, response.text
    override = _events(db, "venue_frequency_override")[-1]
    assert override.details["matched_phone"] == "2125555555"


def test_own_number_is_not_a_linked_number(client: TestClient, db, arena):
    _win(db, _show(db, arena, date(2026, 6, 15), "First"), "Jane Doe", "5105550100")
    second = _show(db, arena, date(2026, 6, 20), "Second")
    data = client.get(
        f"/api/venues/{arena.id}/check-winner",
        params={"phone": "5105550100", "show_id": second.id},
        headers=DJ_STUDIO,
    ).json()
    assert data["eligible"] is False
    assert data["linked_number"] is False


def test_unlinking_stops_the_check(client: TestClient, db, promo, arena):
    _win(db, _show(db, arena, date(2026, 6, 15), "First"), "Jane Doe", "5105550100")
    _win(db, _show(db, arena, date(2026, 5, 1), "Old"), "Jane Doe", "5105550111")
    second = _show(db, arena, date(2026, 6, 20), "Second")
    caller = client.post(URL, json={"phones": ["5105550100", "5105550111"]}, headers=promo)
    caller_id = caller.json()["id"]

    def eligible():
        return client.get(
            f"/api/venues/{arena.id}/check-winner",
            params={"phone": "5105550111", "show_id": second.id},
            headers=DJ_STUDIO,
        ).json()["eligible"]

    assert eligible() is False
    assert client.delete(f"{URL}/{caller_id}", headers=promo).status_code == 204
    assert eligible() is True
    assert db.query(OnAirCallerPhone).count() == 0
    assert _events(db, "caller_unlinked")[0].details["phones"] == [
        "5105550100",
        "5105550111",
    ]


# ---------------------------------------------------------------------------
# Linking


def test_link_requires_known_numbers(client: TestClient, db, promo, arena):
    _win(db, _show(db, arena, date(2026, 6, 15), "First"), "Jane Doe", "5105550100")
    one = client.post(URL, json={"phones": ["5105550100"]}, headers=promo)
    assert one.status_code == 400
    unknown = client.post(URL, json={"phones": ["5105550100", "5109999999"]}, headers=promo)
    assert unknown.status_code == 400
    assert "5109999999" in unknown.json()["detail"]


def test_linking_merges_callers(client: TestClient, db, promo, arena):
    show = _show(db, arena, date(2026, 6, 15), "Show")
    for phone in ["5105550001", "5105550002", "5105550003", "5105550004"]:
        _win(db, show, "Someone", phone)
    a = client.post(
        URL, json={"phones": ["5105550001", "5105550002"], "note": "A"}, headers=promo
    ).json()
    b = client.post(
        URL, json={"phones": ["5105550003", "5105550004"], "note": "B"}, headers=promo
    ).json()

    preview = client.post(
        f"{URL}/preview", json={"phones": ["5105550002", "5105550003"]}, headers=promo
    ).json()
    assert preview == {
        "phones": ["5105550001", "5105550002", "5105550003", "5105550004"],
        "caller_ids": [a["id"], b["id"]],
        "already_linked": False,
    }
    merged = client.post(URL, json={"phones": ["5105550002", "5105550003"]}, headers=promo)
    assert merged.status_code == 200, merged.text
    assert merged.json()["id"] == a["id"]
    assert merged.json()["note"] == "A\nB"
    assert len(merged.json()["phones"]) == 4
    assert db.query(OnAirCaller).count() == 1
    entry = _events(db, "callers_linked")[-1]
    assert entry.area == PASS_GIVEAWAY_AREA
    assert entry.actor_email == "promo@test.com"
    assert entry.details["merged_caller_ids"] == [b["id"]]
    assert entry.details["added_phones"] == []

    again = client.post(URL, json={"phones": ["5105550001", "5105550004"]}, headers=promo)
    assert again.status_code == 400


def test_removing_a_number(client: TestClient, db, promo, arena):
    show = _show(db, arena, date(2026, 6, 15), "Show")
    for phone in ["5105550001", "5105550002", "5105550003"]:
        _win(db, show, "Someone", phone)
    caller = client.post(
        URL, json={"phones": ["5105550001", "5105550002", "5105550003"]}, headers=promo
    ).json()
    left = client.delete(f"{URL}/{caller['id']}/phones/5105550003", headers=promo)
    assert left.status_code == 200
    assert [p["phone"] for p in left.json()["phones"]] == ["5105550001", "5105550002"]
    gone = client.delete(f"{URL}/{caller['id']}/phones/5105550002", headers=promo)
    assert gone.status_code == 200
    assert gone.json() is None
    assert db.query(OnAirCaller).count() == 0
    assert _events(db, "caller_phone_unlinked")[-1].details["caller_deleted"] is True
    missing = client.delete(f"{URL}/{caller['id']}/phones/5105550001", headers=promo)
    assert missing.status_code == 404


def test_note(client: TestClient, db, promo, arena):
    show = _show(db, arena, date(2026, 6, 15), "Show")
    _win(db, show, "A", "5105550001")
    _win(db, show, "B", "5105550002")
    caller = client.post(URL, json={"phones": ["5105550001", "5105550002"]}, headers=promo)
    caller_id = caller.json()["id"]
    assert caller.json()["note"] is None
    updated = client.patch(
        f"{URL}/{caller_id}", json={"note": " Same email "}, headers=promo
    )
    assert updated.json()["note"] == "Same email"
    assert _events(db, "caller_note_updated")[0].details == {
        "before": None,
        "after": "Same email",
    }


def test_stale_number_has_no_wins(client: TestClient, db, promo, arena):
    show = _show(db, arena, date(2026, 6, 15), "Show")
    _win(db, show, "Jane Doe", "5105550001")
    _win(db, show, "Jane Doe", "5105550002")
    client.post(URL, json={"phones": ["5105550001", "5105550002"]}, headers=promo)
    winner = db.query(OnAirWinner).filter(OnAirWinner.recipient_phone == "5105550002").one()
    winner.recipient_phone = "5105550022"
    db.commit()
    phones = {p["phone"]: p for p in client.get(URL, headers=promo).json()[0]["phones"]}
    assert phones["5105550002"]["wins"] == 0
    assert phones["5105550001"]["names"] == ["Jane Doe"]


# ---------------------------------------------------------------------------
# Suggestions


def test_dismissing_and_a_new_number(client: TestClient, db, promo, arena):
    show = _show(db, arena, date(2026, 6, 15), "Show")
    _win(db, show, "Jane Doe", "5105550001", 3)
    _win(db, show, "Jane Doe", "5105550002", 2)
    response = client.post(
        f"{URL}/dismissals", json={"phones": ["5105550001", "5105550002"]}, headers=promo
    )
    assert response.json() == {"pairs": [["5105550001", "5105550002"]]}
    assert client.get(f"{URL}/suggestions", headers=promo).json() == []
    resolved = client.get(f"{URL}/suggestions?resolved=true", headers=promo).json()
    assert resolved[0]["status"] == "dismissed"

    _win(db, show, "Jane Doe", "5105550003")
    again = client.get(f"{URL}/suggestions", headers=promo).json()
    assert again[0]["status"] == "unreviewed"
    assert len(again[0]["phones"]) == 3

    undone = client.post(
        f"{URL}/dismissals/undo",
        json={"phones": ["5105550001", "5105550002"]},
        headers=promo,
    )
    assert undone.status_code == 200
    assert db.query(DismissedCallerPair).count() == 0
    assert len(_events(db, "caller_dismissal_undone")) == 1


def test_link_deletes_dismissals(client: TestClient, db, promo, arena):
    show = _show(db, arena, date(2026, 6, 15), "Show")
    _win(db, show, "Jane Doe", "5105550001")
    _win(db, show, "Jane Doe", "5105550002")
    client.post(
        f"{URL}/dismissals", json={"phones": ["5105550001", "5105550002"]}, headers=promo
    )
    client.post(URL, json={"phones": ["5105550001", "5105550002"]}, headers=promo)
    assert db.query(DismissedCallerPair).count() == 0
    entry = _events(db, "callers_linked")[0]
    assert entry.details["removed_dismissals"] == [["5105550001", "5105550002"]]
    # Unlinking doesn't bring the dismissal back
    caller_id = db.query(OnAirCaller).one().id
    client.delete(f"{URL}/{caller_id}", headers=promo)
    assert (
        client.get(f"{URL}/suggestions", headers=promo).json()[0]["status"] == "unreviewed"
    )


def test_partly_linked_group(client: TestClient, db, promo, arena):
    show = _show(db, arena, date(2026, 6, 15), "Show")
    for phone in ["5105550001", "5105550002", "5105550003"]:
        _win(db, show, "Jane Doe", phone)
    client.post(URL, json={"phones": ["5105550001", "5105550002"]}, headers=promo)
    group = client.get(f"{URL}/suggestions", headers=promo).json()[0]
    assert group["status"] == "partly_linked"
    assert {p["phone"]: p["caller_id"] is not None for p in group["phones"]} == {
        "5105550001": True,
        "5105550002": True,
        "5105550003": False,
    }
    # Dismissing the rest leaves the linked pair alone
    pairs = client.post(
        f"{URL}/dismissals",
        json={"phones": ["5105550001", "5105550002", "5105550003"]},
        headers=promo,
    ).json()["pairs"]
    assert pairs == [["5105550001", "5105550003"], ["5105550002", "5105550003"]]
    assert client.get(f"{URL}/suggestions", headers=promo).json() == []


def test_common_names(client: TestClient, db, promo, arena):
    show = _show(db, arena, date(2026, 6, 15), "Show")
    _win(db, show, "John Smith", "5105550001")
    _win(db, show, "Jon Smith", "5105550002")
    marked = client.post(
        f"{URL}/common-names", json={"name": "John  Smith."}, headers=promo
    )
    assert marked.json()["name"] == "john smith"
    # A group with any marked spelling is hidden
    assert client.get(f"{URL}/suggestions", headers=promo).json() == []
    by_name = client.get(f"{URL}/suggestions?name=Jon Smith", headers=promo).json()
    assert by_name[0]["status"] == "common"
    assert by_name[0]["common_names"] == ["john smith"]
    # Manual linking still works
    assert (
        client.post(
            URL, json={"phones": ["5105550001", "5105550002"]}, headers=promo
        ).status_code
        == 200
    )
    assert [c["name"] for c in client.get(f"{URL}/common-names", headers=promo).json()] == [
        "john smith"
    ]
    assert client.delete(f"{URL}/common-names/john smith", headers=promo).status_code == 204
    assert db.query(CommonCallerName).count() == 0
    assert len(_events(db, "caller_name_marked_common")) == 1
    assert len(_events(db, "caller_name_unmarked_common")) == 1


def test_flagged_groups_come_first(client: TestClient, db, promo, arena, greek):
    # At different venues: not flagged, but won most recently
    _win(db, _show(db, greek, date(2026, 6, 1), "A"), "Bob Lee", "5105550001", 1)
    _win(db, _show(db, arena, date(2026, 6, 2), "B"), "Bob Lee", "5105550002", 1)
    # 5 days apart at a 30-day venue
    _win(db, _show(db, arena, date(2026, 6, 1), "C"), "Ann Park", "5105550003", 9)
    _win(db, _show(db, arena, date(2026, 6, 6), "D"), "Ann Park", "5105550004", 8)
    groups = client.get(f"{URL}/suggestions", headers=promo).json()
    assert [(g["name"], g["flagged"]) for g in groups] == [
        ("Ann Park", True),
        ("Bob Lee", False),
    ]
    assert groups[0]["wins"][0]["show"] == "D"


def test_search(client: TestClient, db, promo, arena):
    show = _show(db, arena, date(2026, 6, 15), "Show")
    _win(db, show, "Robert Smith", "5105550001", 2)
    _win(db, show, "Bob Smith", "5105550002")
    _win(db, show, "Jane Doe", "4155550003")
    by_name = client.get(f"{URL}/search?q=smith", headers=promo).json()
    assert [r["phone"] for r in by_name] == ["5105550002", "5105550001"]
    by_digits = client.get(f"{URL}/search?q=415-555", headers=promo).json()
    assert [r["names"] for r in by_digits] == [["Jane Doe"]]


# ---------------------------------------------------------------------------
# Access


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/suggestions"),
        ("get", ""),
        ("get", "/search?q=jane"),
        ("get", "/common-names"),
        ("post", ""),
        ("post", "/preview"),
        ("post", "/dismissals"),
        ("post", "/common-names"),
        ("delete", "/1"),
    ],
)
def test_staff_and_guests_are_refused(client: TestClient, db, method, path):
    staff = _staff(db, "staff@test.com")
    kwargs = {"json": {"phones": ["1", "2"], "name": "x"}} if method == "post" else {}
    assert (
        getattr(client, method)(f"{URL}{path}", headers=staff, **kwargs).status_code == 403
    )
    assert getattr(client, method)(
        f"{URL}{path}", headers=DJ_STUDIO, **kwargs
    ).status_code in (
        401,
        403,
    )


def test_site_admins_can_link(client: TestClient, db, arena, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "site_admin_emails", "admin@test.com")
    admin = _staff(db, "admin@test.com")
    assert client.get(f"{URL}/suggestions", headers=admin).status_code == 200
