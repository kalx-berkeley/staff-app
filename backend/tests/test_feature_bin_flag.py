"""Tests for the in_feature_bin flag on the shows API."""

import pytest
from datetime import date, time
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.feature_bin_release import FeatureBinRelease
from app.models.show import Show
from app.models.show_band import ShowBand
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.services.feature_bin_service import FeatureBinService


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
def featured_show(db: Session, test_venue):
    """A published show tagged with an artist that has a feature bin release."""
    db.add(
        FeatureBinRelease(
            artist="Mighty Mighty Bosstones",
            album="Live and Direct",
            added_date="3/14",
            dot="RED",
            media_url="https://example.com/album",
        )
    )
    show = Show(
        event_name="Bosstones show",
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
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
            band_name="Mighty Mighty Bosstones",
            start_pos=0,
            end_pos=10,
        )
    )
    db.commit()
    db.refresh(show)
    return show


@pytest.fixture
def unfeatured_show(db: Session, test_venue):
    show = Show(
        event_name="Some Other Show",
        venue_id=test_venue.id,
        show_date=date(2024, 12, 30),
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
    client: TestClient, test_promotions_staff, featured_show, unfeatured_show
):
    response = client.get(
        "/api/shows", headers={"X-Forwarded-User": test_promotions_staff.email}
    )
    assert response.status_code == 200
    data = response.json()
    by_name = {show["event_name"]: show for show in data}

    featured = by_name["Bosstones show"]
    assert featured["in_feature_bin"] is True
    assert len(featured["feature_bin_releases"]) == 1
    release = featured["feature_bin_releases"][0]
    assert release["artist"] == "Mighty Mighty Bosstones"
    assert release["album"] == "Live and Direct"
    assert release["added_date"] == "3/14"
    assert release["dot"] == "RED"

    unfeatured = by_name["Some Other Show"]
    assert unfeatured["in_feature_bin"] is False
    assert unfeatured["feature_bin_releases"] == []


def test_get_show_flags_matched_show(
    client: TestClient, test_promotions_staff, featured_show
):
    response = client.get(
        f"/api/shows/{featured_show.id}",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["in_feature_bin"] is True
    assert data["feature_bin_releases"][0]["artist"] == "Mighty Mighty Bosstones"


def test_manual_sync_reports_not_configured_when_sheet_unset(
    client: TestClient, test_promotions_staff, monkeypatch
):
    monkeypatch.setattr(settings, "feature_bin_sheet_id", None)
    monkeypatch.setattr(settings, "feature_bin_sheet_gid", None)

    response = client.post(
        "/api/admin/jobs/feature_bin_sync/run",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "not configured" in data["message"]


def test_manual_sync_runs_when_configured(
    client: TestClient, test_promotions_staff, monkeypatch
):
    monkeypatch.setattr(settings, "feature_bin_sheet_id", "some-id")
    monkeypatch.setattr(settings, "feature_bin_sheet_gid", "some-gid")
    monkeypatch.setattr(
        FeatureBinService,
        "fetch_sheet_csv",
        staticmethod(
            lambda: ("Group1,,\nAdded,Artist,Album\n3/14,Some Artist,Some Album\n")
        ),
    )

    response = client.post(
        "/api/admin/jobs/feature_bin_sync/run",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "1" in data["message"]
