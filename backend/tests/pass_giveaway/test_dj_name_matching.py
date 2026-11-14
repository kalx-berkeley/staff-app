"""Tests for matching DJ names typed as text to Spinitron personas and shows."""

from datetime import date, time

import pytest
from sqlalchemy.orm import Session

from app.models.analytics_event import AnalyticsDailyCount
from app.models.dj_name_mapping import DjNameMapping
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_dj import SpecialtyShowDJ
from app.models.staff import Staff
from app.models.venue import Venue
from app.pass_giveaway.services.dj_name_matching import (
    AMBIGUOUS,
    PERSONA,
    SHOW,
    UNATTRIBUTED,
    UNMATCHED,
    build_directory,
    name_uses,
)

# Spinitron's persona directory: two personas share "DJ Twin"
SPINITRON = {
    1: "DJ Lite",
    2: "DJ Twin",
    3: "DJ Twin",
    4: "Take Five",
    5: "DJ Dup",
    6: "DJ Dup",
}


@pytest.fixture
def setup(db: Session) -> dict:
    db.add(
        Staff(
            email="twin@example.com",
            name="Twin",
            phone="",
            spinitron_ids=[2],
            dj_personas=[{"id": 2, "name": "DJ Twin"}],
        )
    )
    music = SpecialtyShow(name="Take Five")
    talk = SpecialtyShow(name="Morning Report", category="talk")
    gone = SpecialtyShow(name="Gone Show", deleted=True)
    db.add_all([music, talk, gone])
    db.commit()
    return {"music": music, "talk": talk}


def _directory(db: Session):
    return build_directory(db, SPINITRON)


def test_names_match_personas_and_shows(db: Session, setup):
    directory = _directory(db)
    assert directory.match("  dj   LITE ").kind == PERSONA
    assert directory.match("dj lite").persona_id == 1
    talk = directory.match("morning report")
    assert (talk.kind, talk.specialty_show_id) == (SHOW, setup["talk"].id)
    # Deleted shows aren't matched
    assert directory.match("Gone Show").kind == UNMATCHED
    assert directory.match("").kind == UNATTRIBUTED


def test_a_shared_persona_name_prefers_the_one_staff_member(db: Session, setup):
    directory = _directory(db)
    assert directory.match("DJ Twin").persona_id == 2
    assert directory.match("DJ Dup").kind == AMBIGUOUS


def test_a_name_shared_by_a_show_and_a_persona_is_ambiguous(db: Session, setup):
    match = _directory(db).match("Take Five")
    assert match.kind == AMBIGUOUS
    assert "Take Five" in match.reason


def test_mappings_win_and_can_leave_a_name_unattributed(db: Session, setup):
    db.add_all([
        DjNameMapping(name_key="take five", specialty_show_id=setup["music"].id),
        DjNameMapping(name_key="unknown"),
        DjNameMapping(name_key="dj fooo", persona_id=1),
    ])
    db.commit()
    directory = _directory(db)
    assert directory.match("Take Five").specialty_show_id == setup["music"].id
    assert directory.match("Unknown").kind == UNATTRIBUTED
    assert directory.match("DJ Fooo").persona_id == 1
    # Music show DJs must be personas, even when mapped to a show
    assert directory.match("Take Five", allow_show=False).kind == UNMATCHED


def test_unmatched_names_suggest_close_ones(db: Session, setup):
    assert _directory(db).suggestions("DJ Liteee") == ["DJ Lite"]


def test_name_uses_counts_rows_per_column(db: Session, setup):
    venue = Venue(name="V", address="1 St")
    db.add(venue)
    db.flush()
    show = Show(
        event_name="S",
        venue_id=venue.id,
        show_date=date(2026, 12, 1),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=3,
    )
    db.add(show)
    db.flush()
    passes = [
        Pass(show_id=show.id, pass_type="pair", status="given_away", given_away_by_dj=n)
        for n in ("DJ Lite", "dj lite", "DJ Fooo")
    ]
    # The text says something else, but the show ID settles it
    passes.append(
        Pass(
            show_id=show.id,
            pass_type="pair",
            status="available",
            preassigned_dj="Old Name",
            preassigned_specialty_show_id=setup["talk"].id,
        )
    )
    db.add_all(passes)
    db.flush()
    db.add(
        OnAirWinner(
            pass_id=passes[0].id,
            venue_id=venue.id,
            show_id=show.id,
            recipient_name="R",
            recipient_phone="5555550100",
            given_away_by_dj="  ",
        )
    )
    db.add(SpecialtyShowDJ(specialty_show_id=setup["music"].id, dj_name="Morning Report"))
    db.add(
        AnalyticsDailyCount(
            day=date(2025, 1, 1),
            event_type="giveaway_visit",
            area="pass_giveaway",
            dj_name="dj lite",
            count=7,
        )
    )
    db.commit()

    uses = {(u.column.label, u.name): u for u in name_uses(db, _directory(db))}
    assert uses[("passes.given_away_by_dj", "DJ Lite")].rows == 1
    assert uses[("passes.given_away_by_dj", "dj lite")].match.persona_id == 1
    assert uses[("passes.given_away_by_dj", "DJ Fooo")].match.kind == UNMATCHED
    preassigned = uses[("passes.preassigned_dj", "Old Name")].match
    assert preassigned.specialty_show_id == setup["talk"].id
    # A music show's DJ can't be a show
    assert uses[("specialty_show_djs.dj_name", "Morning Report")].match.kind == UNMATCHED
    assert uses[("analytics_daily_count.dj_name", "dj lite")].rows == 7
    # Blank names are left out
    assert not any(label == "on_air_winners.given_away_by_dj" for label, _ in uses)
