"""Tests for the legacy paper-form import's venue guest list rules.

The router is only registered when LEGACY_IMPORT_ENABLED is on, so these
call its endpoint functions directly.
"""

from datetime import date, time

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.venue import Venue
from app.pass_giveaway.routers.legacy_import import (
    import_legacy_show,
    merge_legacy_show,
)
from app.pass_giveaway.schemas.legacy_import import (
    LegacyShowImport,
    LegacyShowMerge,
    OnAirWinnerImport,
    StaffPassImport,
)


@pytest.fixture
def staff(db: Session) -> Staff:
    staff = Staff(email="staff@test.com", name="Test Staff", phone="555-0002")
    db.add(staff)
    db.commit()
    return staff


def _venue(db: Session, **rules) -> Venue:
    venue = Venue(name="Strict Venue", address="1 Main St", **rules)
    db.add(venue)
    db.commit()
    return venue


def _show_with_passes(db: Session, venue: Venue) -> Show:
    show = Show(
        event_name="Existing Show",
        genre=["rock"],
        venue_id=venue.id,
        show_date=date(2099, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add(show)
    db.flush()
    for pass_type in ("pair", "pair", "staff", "staff"):
        db.add(Pass(show_id=show.id, pass_type=pass_type, status="available"))
    db.commit()
    return show


def _import(venue: Venue, **lists) -> LegacyShowImport:
    return LegacyShowImport(
        event_name="Paper Show",
        venue_id=venue.id,
        show_date=date(2099, 12, 31),
        show_time=time(20, 0),
        num_pass_pairs=2,
        **lists,
    )


WINNER = OnAirWinnerImport(recipient_name="Caller", recipient_phone="555-1234")


def test_import_requires_winner_email_when_the_venue_does(db: Session, staff: Staff):
    venue = _venue(db, requires_email_address=True)

    with pytest.raises(HTTPException) as exc:
        import_legacy_show(_import(venue, on_air_winners=[WINNER]), staff, db)

    assert exc.value.status_code == 422
    assert "email" in exc.value.detail
    assert db.query(Show).count() == 0


def test_import_accepts_winner_email_when_the_venue_requires_it(db: Session, staff: Staff):
    venue = _venue(db, requires_email_address=True)
    winner = WINNER.model_copy(update={"recipient_email": "caller@example.com"})

    result = import_legacy_show(_import(venue, on_air_winners=[winner]), staff, db)

    assert result.on_air_winners_created == 1


def test_merge_requires_guest_name_when_the_venue_does(db: Session, staff: Staff):
    venue = _venue(db, staff_guest_requires_name=True)
    show = _show_with_passes(db, venue)
    claim = StaffPassImport(staff_id=staff.id, has_guest=True, guest_name="  ")

    with pytest.raises(HTTPException) as exc:
        merge_legacy_show(show.id, LegacyShowMerge(staff_passes=[claim]), staff, db)

    assert exc.value.status_code == 422
    assert "guest" in exc.value.detail
    assert db.query(Pass).filter(Pass.status == "claimed").count() == 0


def test_merge_keeps_the_guest_as_a_hold_on_the_claim(db: Session, staff: Staff):
    venue = _venue(db, staff_guest_requires_name=True)
    show = _show_with_passes(db, venue)
    claim = StaffPassImport(staff_id=staff.id, has_guest=True, guest_name="Pal")

    merge_legacy_show(show.id, LegacyShowMerge(staff_passes=[claim]), staff, db)

    primary, hold = (
        db.query(Pass)
        .filter(Pass.show_id == show.id, Pass.pass_type == "staff")
        .order_by(Pass.id)
        .all()
    )
    assert primary.has_guest and primary.guest_name == "Pal"
    assert hold.guest_of_pass_id == primary.id
