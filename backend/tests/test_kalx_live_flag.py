"""Tests for the on_kalx_live flag on the shows API."""

from datetime import date, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.kalx_live_appearance import KalxLiveAppearance
from app.models.show import Show
from app.models.show_band import ShowBand
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.services.kalx_live_service import KalxLiveService


@pytest.fixture
def test_venue(db: Session):
    venue = Venue(name="Test Venue", address="123 Test St")
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@pytest.fixture
def test_promotions_staff(db: Session):
    staff = Staff(email="promotions@test.com", name="Test Promotions", phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def kalx_live_show(db: Session, test_venue):
    """A published show tagged with an artist that recently played KALX Live!."""
    db.add(
        KalxLiveAppearance(
            band_name="Warm Spell", event_date=date.today() - timedelta(days=10)
        )
    )
    show = Show(
        event_name="Warm Spell show",
        venue_id=test_venue.id,
        show_date=date(2026, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add(show)
    db.flush()
    db.add(
        ShowBand(
            show_id=show.id,
            musicbrainz_id="fake-mbid",
            band_name="Warm Spell",
            start_pos=0,
            end_pos=10,
        )
    )
    db.commit()
    db.refresh(show)
    return show


@pytest.fixture
def non_kalx_live_show(db: Session, test_venue):
    show = Show(
        event_name="Some Other Show",
        venue_id=test_venue.id,
        show_date=date(2026, 12, 30),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add(show)
    db.commit()
    db.refresh(show)
    return show


def test_list_shows_flags_matched_show(
    client: TestClient, test_promotions_staff, kalx_live_show, non_kalx_live_show
):
    response = client.get(
        "/api/shows", headers={"X-Forwarded-User": test_promotions_staff.email}
    )
    assert response.status_code == 200
    data = response.json()
    by_name = {show["event_name"]: show for show in data}

    flagged = by_name["Warm Spell show"]
    assert flagged["on_kalx_live"] is True
    assert len(flagged["kalx_live_appearances"]) == 1
    assert flagged["kalx_live_appearances"][0]["band_name"] == "Warm Spell"

    unflagged = by_name["Some Other Show"]
    assert unflagged["on_kalx_live"] is False
    assert unflagged["kalx_live_appearances"] == []


def test_get_show_flags_matched_show(
    client: TestClient, test_promotions_staff, kalx_live_show
):
    response = client.get(
        f"/api/shows/{kalx_live_show.id}",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["on_kalx_live"] is True
    assert data["kalx_live_appearances"][0]["band_name"] == "Warm Spell"


def test_manual_sync_reports_not_configured_when_calendar_unset(
    client: TestClient, test_promotions_staff, monkeypatch
):
    monkeypatch.setattr(settings, "kalx_live_calendar_id", None)

    response = client.post(
        "/api/admin/jobs/kalx_live_sync/run",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "not configured" in data["message"]


def test_manual_sync_runs_when_configured(
    client: TestClient, test_promotions_staff, monkeypatch
):
    monkeypatch.setattr(settings, "kalx_live_calendar_id", "some-calendar-id")
    monkeypatch.setattr(
        KalxLiveService,
        "fetch_ics",
        staticmethod(
            lambda: (
                b"BEGIN:VCALENDAR\n"
                b"VERSION:2.0\n"
                b"BEGIN:VEVENT\n"
                b"DTSTART;TZID=America/Los_Angeles:20250308T190000\n"
                b"UID:evt1@google.com\n"
                b"SUMMARY:Some Band on KALX Live!\n"
                b"END:VEVENT\n"
                b"END:VCALENDAR\n"
            )
        ),
    )

    response = client.post(
        "/api/admin/jobs/kalx_live_sync/run",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "1" in data["message"]
