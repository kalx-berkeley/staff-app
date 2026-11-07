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
from app.models.staff_pass_alternate import StaffPassAlternate
from app.models.venue import Venue
from app.pass_giveaway.routers.legacy_import import (
    import_legacy_show,
    merge_legacy_show,
)
from app.pass_giveaway.services.alternate_service import AlternateService
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
        wheelchair_accessible="yes",
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
    venue = _venue(db, email_address_requirement="all")

    with pytest.raises(HTTPException) as exc:
        import_legacy_show(_import(venue, on_air_winners=[WINNER]), staff, db)

    assert exc.value.status_code == 422
    assert "email" in exc.value.detail
    assert db.query(Show).count() == 0


def test_import_accepts_winner_email_when_the_venue_requires_it(db: Session, staff: Staff):
    venue = _venue(db, email_address_requirement="all")
    winner = WINNER.model_copy(update={"recipient_email": "caller@example.com"})

    result = import_legacy_show(_import(venue, on_air_winners=[winner]), staff, db)

    assert result.on_air_winners_created == 1


def test_import_at_movie_theater_keeps_movie_rating(db: Session, staff: Staff):
    """A movie theater show gets its movie rating and no age restriction."""
    venue = _venue(db, venue_type="movie_theater")

    result = import_legacy_show(_import(venue, movie_rating="PG"), staff, db)

    show = db.query(Show).filter(Show.id == result.show_id).one()
    assert show.movie_rating == "PG"
    assert show.age_restriction is None


def test_import_at_movie_theater_requires_movie_rating(db: Session, staff: Staff):
    venue = _venue(db, venue_type="movie_theater")

    with pytest.raises(HTTPException) as exc:
        import_legacy_show(_import(venue), staff, db)

    assert exc.value.status_code == 400
    assert "movie rating" in exc.value.detail
    assert db.query(Show).count() == 0


def test_import_at_music_venue_drops_movie_rating(db: Session, staff: Staff):
    venue = _venue(db)

    result = import_legacy_show(
        _import(venue, age_restriction="21+", movie_rating="R"), staff, db
    )

    show = db.query(Show).filter(Show.id == result.show_id).one()
    assert show.age_restriction == "21+"
    assert show.movie_rating is None


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


def _more_staff(db: Session, count: int) -> list[Staff]:
    members = [
        Staff(email=f"member{i}@test.com", name=f"Member {i}", phone="555-0003")
        for i in range(count)
    ]
    db.add_all(members)
    db.commit()
    return members


def _claim(member: Staff, **guest) -> StaffPassImport:
    return StaffPassImport(staff_id=member.id, **guest)


def test_import_queues_alternates_in_the_order_given(db: Session, staff: Staff):
    venue = _venue(db)
    a, b, first, second = _more_staff(db, 4)

    result = import_legacy_show(
        _import(
            venue,
            staff_passes=[_claim(a), _claim(b)],
            alternates=[_claim(first, has_guest=True, guest_name=" Pal "), _claim(second)],
        ),
        staff,
        db,
    )

    assert result.alternates_added == 2
    queue = AlternateService.waiting_entries(db, result.show_id)
    assert [e.staff_id for e in queue] == [first.id, second.id]
    assert queue[0].has_guest and queue[0].guest_name == "Pal"
    assert queue[0].guest_fallback == "attend_alone"
    assert queue[1].guest_name is None


def test_merge_adds_alternates_behind_those_already_waiting(db: Session, staff: Staff):
    show = _show_with_passes(db, _venue(db))
    a, b, waiting, new = _more_staff(db, 4)
    merge_legacy_show(
        show.id,
        LegacyShowMerge(staff_passes=[_claim(a), _claim(b)], alternates=[_claim(waiting)]),
        staff,
        db,
    )

    result = merge_legacy_show(
        show.id, LegacyShowMerge(alternates=[_claim(new)]), staff, db
    )

    assert result.alternates_added == 1
    queue = AlternateService.waiting_entries(db, show.id)
    assert [e.staff_id for e in queue] == [waiting.id, new.id]


def test_merge_alternate_is_promoted_when_a_pass_frees_up(db: Session, staff: Staff):
    show = _show_with_passes(db, _venue(db))
    a, b, alternate = _more_staff(db, 3)
    merge_legacy_show(
        show.id,
        LegacyShowMerge(
            staff_passes=[_claim(a), _claim(b)], alternates=[_claim(alternate)]
        ),
        staff,
        db,
    )

    released = db.query(Pass).filter(Pass.show_id == show.id, Pass.staff_id == a.id).one()
    released.status = "available"
    released.staff_id = None
    db.flush()
    AlternateService.fill_open_passes(db, show, trigger="test")
    db.commit()

    assert released.staff_id == alternate.id
    assert AlternateService.waiting_entries(db, show.id) == []


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param(lambda a, b: [_claim(a)], id="pass left over"),
        pytest.param(lambda a, b: [_claim(a, has_guest=True)], id="pass held for a guest"),
    ],
)
def test_import_rejects_alternates_unless_staff_hold_every_pass(
    db: Session, staff: Staff, claims
):
    venue = _venue(db)
    a, b, alternate = _more_staff(db, 3)

    with pytest.raises(HTTPException) as exc:
        import_legacy_show(
            _import(venue, staff_passes=claims(a, b), alternates=[_claim(alternate)]),
            staff,
            db,
        )

    assert exc.value.status_code == 422
    assert "every staff pass" in exc.value.detail
    assert db.query(Show).count() == 0
    assert db.query(StaffPassAlternate).count() == 0


def test_merge_rollback_keeps_show_a_draft_when_alternates_are_rejected(
    db: Session, staff: Staff
):
    show = _show_with_passes(db, _venue(db))
    show.status = "draft"
    db.commit()
    a, alternate = _more_staff(db, 2)

    with pytest.raises(HTTPException):
        merge_legacy_show(
            show.id,
            LegacyShowMerge(staff_passes=[_claim(a)], alternates=[_claim(alternate)]),
            staff,
            db,
        )

    db.refresh(show)
    assert show.status == "draft"
    assert db.query(Pass).filter(Pass.status == "claimed").count() == 0


def test_alternate_cannot_also_hold_a_pass(db: Session, staff: Staff):
    venue = _venue(db)
    a, b = _more_staff(db, 2)

    with pytest.raises(HTTPException) as exc:
        import_legacy_show(
            _import(venue, staff_passes=[_claim(a), _claim(b)], alternates=[_claim(a)]),
            staff,
            db,
        )

    assert exc.value.status_code == 422
    assert "already has a staff pass" in exc.value.detail


def test_alternate_cannot_be_listed_twice(db: Session, staff: Staff):
    venue = _venue(db)
    a, b, alternate = _more_staff(db, 3)

    with pytest.raises(HTTPException) as exc:
        import_legacy_show(
            _import(
                venue,
                staff_passes=[_claim(a), _claim(b)],
                alternates=[_claim(alternate), _claim(alternate)],
            ),
            staff,
            db,
        )

    assert exc.value.status_code == 422
    assert "already on the alternate list" in exc.value.detail


def test_alternate_must_exist(db: Session, staff: Staff):
    venue = _venue(db)
    a, b = _more_staff(db, 2)

    with pytest.raises(HTTPException) as exc:
        import_legacy_show(
            _import(
                venue,
                staff_passes=[_claim(a), _claim(b)],
                alternates=[StaffPassImport(staff_id=99999)],
            ),
            staff,
            db,
        )

    assert exc.value.status_code == 404
    assert db.query(Show).count() == 0


def test_alternate_guest_needs_a_name_when_the_venue_does(db: Session, staff: Staff):
    venue = _venue(db, staff_guest_requires_name=True)
    a, b, alternate = _more_staff(db, 3)

    with pytest.raises(HTTPException) as exc:
        import_legacy_show(
            _import(
                venue,
                staff_passes=[_claim(a), _claim(b)],
                alternates=[_claim(alternate, has_guest=True, guest_name="  ")],
            ),
            staff,
            db,
        )

    assert exc.value.status_code == 422
    assert "guest" in exc.value.detail
    assert db.query(Show).count() == 0
