"""Tests for the show list's planned_close_passed flag.

Once a show's planned close time passes, passes can't be claimed or given away,
even if the show hasn't been closed yet. The staff and DJ show pages use the
flag to leave such shows out of their "available" filters.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.common.services.leave_service import today_pt
from app.models.show import Show
from app.models.venue import Venue

DJ_STUDIO = {"X-Forwarded-For": "192.168.1.100"}  # within default dj_studio_network
_LA = ZoneInfo("America/Los_Angeles")


@pytest.fixture
def show(db: Session) -> Show:
    """A published show with no planned close time."""
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
        num_pass_pairs=1,
        status="published",
    )
    db.add(show)
    db.commit()
    db.refresh(show)
    return show


def _summary(client, show_id: int) -> dict:
    response = client.get("/api/shows", headers=DJ_STUDIO)
    assert response.status_code == 200
    return next(s for s in response.json() if s["id"] == show_id)


def _set_planned_close(db: Session, show: Show, at: datetime) -> None:
    show.planned_close_date = at.date()
    show.planned_close_time = at.time().replace(microsecond=0)
    db.commit()


def test_no_planned_close_time(client, show):
    """A show without a planned close time hasn't passed it."""
    assert _summary(client, show.id)["planned_close_passed"] is False


def test_planned_close_time_still_ahead(client, db, show):
    """A planned close time later today hasn't passed."""
    _set_planned_close(db, show, datetime.now(_LA) + timedelta(hours=1))
    assert _summary(client, show.id)["planned_close_passed"] is False


def test_planned_close_time_passed(client, db, show):
    """A planned close time an hour ago has passed, though the show is still published."""
    _set_planned_close(db, show, datetime.now(_LA) - timedelta(hours=1))
    summary = _summary(client, show.id)
    assert summary["status"] == "published"
    assert summary["planned_close_passed"] is True
