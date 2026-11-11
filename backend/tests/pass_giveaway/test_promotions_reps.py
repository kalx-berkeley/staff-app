"""Tests for what KALX promotions reps see and receive about their shows.

Covers the promotions show list's "My Shows", who gets the guest list email
when a show auto-closes, and what that guest list says.
"""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.promoter import Promoter
from app.models.promoter_owner import PromoterOwner
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.models.venue_owner import VenueOwner
from app.pass_giveaway.services.show_service import ShowService


def _rep(db: Session, email: str) -> Staff:
    staff = Staff(email=email, name=email.split("@")[0], phone="5550000000")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.flush()
    return staff


def _venue(db: Session, name: str, rep: Staff | None = None, **kwargs) -> Venue:
    venue = Venue(name=name, address="1 Main St", **kwargs)
    db.add(venue)
    db.flush()
    if rep:
        db.add(VenueOwner(venue_id=venue.id, staff_id=rep.id))
    return venue


def _promoter(db: Session, name: str, rep: Staff | None = None) -> Promoter:
    promoter = Promoter(name=name)
    db.add(promoter)
    db.flush()
    if rep:
        db.add(PromoterOwner(promoter_id=promoter.id, staff_id=rep.id))
    return promoter


def _show(db: Session, name: str, venue: Venue, promoter: Promoter | None = None) -> Show:
    show = Show(
        event_name=name,
        venue_id=venue.id,
        promoter_id=promoter.id if promoter else None,
        show_date=date(2099, 12, 31),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=1,
        status="published",
    )
    db.add(show)
    db.flush()
    return show


@pytest.fixture
def reps_and_shows(db: Session):
    """Two reps, with shows at their venues and for their promoters.

    venue_rep represents "Own Venue", whose default promoter is "Other
    Promoter". promoter_rep represents "Other Promoter", which is also the
    default promoter for "Promoted Venue".
    """
    venue_rep = _rep(db, "venue-rep@example.com")
    promoter_rep = _rep(db, "promoter-rep@example.com")
    other_promoter = _promoter(db, "Other Promoter", promoter_rep)
    own_venue = _venue(db, "Own Venue", venue_rep, promoter_id=other_promoter.id)
    promoted_venue = _venue(db, "Promoted Venue", promoter_id=other_promoter.id)
    unrelated_venue = _venue(db, "Unrelated Venue")

    _show(db, "Own venue, no promoter", own_venue)
    _show(db, "Own venue, other promoter", own_venue, other_promoter)
    _show(db, "Other promoter at unrelated venue", unrelated_venue, other_promoter)
    _show(db, "No promoter at venue with default promoter", promoted_venue)
    _show(db, "Unrelated", unrelated_venue)
    db.commit()
    return venue_rep, promoter_rep


def _my_shows(client: TestClient, rep: Staff) -> set[str]:
    response = client.get("/api/shows", headers={"X-Forwarded-User": rep.email})
    assert response.status_code == 200
    return {s["event_name"] for s in response.json() if s["is_mine"]}


def test_my_shows_for_a_venue_rep_are_the_venues_shows_without_a_promoter(
    client: TestClient, reps_and_shows
):
    """The venue's default promoter doesn't matter, only the show's own promoter."""
    venue_rep, _ = reps_and_shows

    assert _my_shows(client, venue_rep) == {"Own venue, no promoter"}


def test_my_shows_for_a_promoter_rep_are_the_shows_it_is_the_promoter_for(
    client: TestClient, reps_and_shows
):
    """Shows without a promoter at venues it's the default promoter for don't count."""
    _, promoter_rep = reps_and_shows

    assert _my_shows(client, promoter_rep) == {
        "Own venue, other promoter",
        "Other promoter at unrelated venue",
    }


def _auto_close_recipients(db: Session, show: Show) -> list[str]:
    with patch(
        "app.pass_giveaway.services.show_service.notification_service.send_email"
    ) as send_email:
        ShowService._notify_venue_owners_of_auto_close(db, show)
    return [c.kwargs["to_email"] for c in send_email.call_args_list]


def test_auto_close_email_goes_to_venue_reps_when_venue_is_its_own_promoter(db: Session):
    venue_rep = _rep(db, "venue-rep@example.com")
    _promoter(db, "Unused Promoter", _rep(db, "promoter-rep@example.com"))
    show = _show(db, "Show", _venue(db, "Venue", venue_rep))
    db.commit()

    assert _auto_close_recipients(db, show) == ["venue-rep@example.com"]


def test_auto_close_email_ignores_the_venues_default_promoter(db: Session):
    venue_rep = _rep(db, "venue-rep@example.com")
    default = _promoter(db, "Default Promoter", _rep(db, "promoter-rep@example.com"))
    show = _show(db, "Show", _venue(db, "Venue", venue_rep, promoter_id=default.id))
    db.commit()

    assert _auto_close_recipients(db, show) == ["venue-rep@example.com"]


def test_auto_close_email_goes_to_promoter_reps_not_venue_reps(db: Session):
    venue_rep = _rep(db, "venue-rep@example.com")
    promoter = _promoter(db, "Promoter", _rep(db, "promoter-rep@example.com"))
    show = _show(db, "Show", _venue(db, "Venue", venue_rep), promoter)
    db.commit()

    assert _auto_close_recipients(db, show) == ["promoter-rep@example.com"]


def _guest_list_show(db: Session, promoter: Promoter | None = None, **venue_kwargs) -> Show:
    """A show with an on-air winner, a staff claim alone and one with a guest."""
    show = _show(db, "Show", _venue(db, "Venue", **venue_kwargs), promoter)
    now = datetime.now(timezone.utc)
    pair = Pass(show_id=show.id, pass_type="pair", status="given_away")
    db.add(pair)
    db.flush()
    db.add(
        OnAirWinner(
            pass_id=pair.id,
            venue_id=show.venue_id,
            show_id=show.id,
            recipient_name="Caller",
            recipient_phone="5551234567",
            recipient_email="caller@example.com",
            given_away_by_dj="DJ Test",
        )
    )
    solo = _rep(db, "solo@example.com")
    host = _rep(db, "host@example.com")
    db.add(
        Pass(
            show_id=show.id,
            pass_type="staff",
            status="claimed",
            staff_id=solo.id,
            claimed_at=now,
        )
    )
    primary = Pass(
        show_id=show.id,
        pass_type="staff",
        status="claimed",
        staff_id=host.id,
        claimed_at=now,
        has_guest=True,
        guest_name="Jamie",
    )
    db.add(primary)
    db.flush()
    db.add(
        Pass(
            show_id=show.id,
            pass_type="staff",
            status="claimed",
            staff_id=host.id,
            claimed_at=now,
            guest_of_pass_id=primary.id,
        )
    )
    db.commit()
    db.refresh(show)
    return show


def test_guest_list_counts_a_staff_member_and_guest_as_a_pair(db: Session):
    show = _guest_list_show(db)

    lines = ShowService._build_guest_list_text(show).splitlines()[1:]

    assert lines == [
        "",
        "On-air giveaway winners:",
        "1 pair of passes for Caller and a guest",
        "",
        "KALX staff:",
        "1 pass for solo",
        "1 pair of passes for host and a guest",
    ]


def test_guest_list_names_a_staff_guest_when_the_venue_requires_it(db: Session):
    show = _guest_list_show(db, staff_guest_requires_name=True)

    lines = ShowService._build_guest_list_text(show).splitlines()[1:]

    assert lines[-2:] == ["1 pass for host", "1 pass for Jamie"]


@pytest.mark.parametrize(
    ("requirement", "caller_email", "staff_email"),
    [("none", False, False), ("staff_passes", False, True), ("all", True, True)],
)
def test_guest_list_includes_the_email_addresses_the_venue_wants(
    db: Session, requirement, caller_email, staff_email
):
    show = _guest_list_show(db, email_address_requirement=requirement)

    text = ShowService._build_guest_list_text(show)

    assert ("caller@example.com" in text) == caller_email
    assert ("solo@example.com" in text) == staff_email
    assert ("host@example.com" in text) == staff_email


def test_guest_list_uses_the_shows_promoters_settings_not_the_venues(db: Session):
    promoter = _promoter(db, "Promoter")
    promoter.email_address_requirement = "staff_passes"
    promoter.staff_guest_requires_name = True
    show = _guest_list_show(
        db, promoter, email_address_requirement="all", requires_phone_number=True
    )

    lines = ShowService._build_guest_list_text(show).splitlines()[1:]

    assert lines == [
        "",
        "On-air giveaway winners:",
        "1 pair of passes for Caller and a guest",
        "",
        "KALX staff:",
        "1 pass for solo (solo@example.com)",
        "1 pass for host (host@example.com)",
        "1 pass for Jamie",
    ]


def test_show_response_has_the_shows_promoters_guest_list_settings(
    client: TestClient, db: Session
):
    rep = _rep(db, "promoter-rep@example.com")
    promoter = _promoter(db, "Promoter", rep)
    promoter.email_address_requirement = "all"
    show = _show(db, "Show", _venue(db, "Venue", staff_guest_requires_name=True), promoter)
    db.commit()

    response = client.get(f"/api/shows/{show.id}", headers={"X-Forwarded-User": rep.email})

    assert response.status_code == 200
    assert response.json()["guest_list_requirements"] == {
        "requires_phone_number": False,
        "email_address_requirement": "all",
        "requires_email_address": True,
        "staff_guest_requires_name": False,
    }


@pytest.mark.parametrize(
    ("requirement", "requires_email_address"),
    [("none", False), ("staff_passes", False), ("all", True)],
)
def test_venue_email_address_requirement_round_trips(
    client: TestClient, db: Session, requirement, requires_email_address
):
    """Only "all" has DJs collect on-air winners' email addresses."""
    rep = _rep(db, "venue-rep@example.com")
    venue = _venue(db, "Venue", rep)
    db.commit()

    response = client.put(
        f"/api/venues/{venue.id}",
        json={"email_address_requirement": requirement},
        headers={"X-Forwarded-User": rep.email},
    )

    assert response.status_code == 200
    assert response.json()["email_address_requirement"] == requirement
    assert response.json()["requires_email_address"] is requires_email_address


def test_promoter_email_address_requirement_round_trips(client: TestClient, db: Session):
    rep = _rep(db, "promoter-rep@example.com")
    promoter = _promoter(db, "Promoter", rep)
    db.commit()

    response = client.put(
        f"/api/promoters/{promoter.id}",
        json={"email_address_requirement": "staff_passes"},
        headers={"X-Forwarded-User": rep.email},
    )

    assert response.status_code == 200
    assert response.json()["email_address_requirement"] == "staff_passes"
