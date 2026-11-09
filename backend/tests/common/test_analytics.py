"""Tests for KALX Staff Analytics' common parts: windows, access, beacon, rollup."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.areas import COMMON_AREA
from app.common.services import tracking_service
from app.common.services.analytics_rollup import roll_up_old_events
from app.common.services.analytics_window import parse_window, preset_window
from app.config import settings
from app.models.analytics_event import AnalyticsDailyCount, AnalyticsEvent
from app.models.impersonation_session import ImpersonationSession
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus


def _staff(db: Session, email: str, department: str | None = None, active=True) -> Staff:
    staff = Staff(email=email, name=email.split("@")[0], phone="")
    db.add(staff)
    db.flush()
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    if active:
        db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    return staff


def _as(email: str) -> dict:
    return {"X-Forwarded-User": email}


# ---------------------------------------------------------------------------
# Windows


@pytest.mark.parametrize(
    "preset,today,start,end",
    [
        ("last_30_days", date(2026, 11, 9), date(2026, 10, 11), date(2026, 11, 9)),
        ("last_month", date(2026, 11, 9), date(2026, 10, 1), date(2026, 10, 31)),
        ("last_month", date(2026, 1, 15), date(2025, 12, 1), date(2025, 12, 31)),
        ("this_quarter", date(2026, 11, 9), date(2026, 10, 1), date(2026, 11, 9)),
        ("last_quarter", date(2026, 11, 9), date(2026, 7, 1), date(2026, 9, 30)),
        ("last_quarter", date(2026, 2, 1), date(2025, 10, 1), date(2025, 12, 31)),
        ("this_year", date(2026, 11, 9), date(2026, 1, 1), date(2026, 11, 9)),
        ("last_year", date(2026, 11, 9), date(2025, 1, 1), date(2025, 12, 31)),
    ],
)
def test_presets(preset, today, start, end):
    window = preset_window(preset, today)
    assert (window.start, window.end) == (start, end)


def test_custom_range_and_errors():
    window = parse_window(None, date(2026, 1, 5), date(2026, 2, 5))
    assert (window.start, window.end, window.preset) == (
        date(2026, 1, 5),
        date(2026, 2, 5),
        None,
    )
    assert parse_window(None, None, None, today=date(2026, 11, 9)).preset == "last_30_days"
    with pytest.raises(ValueError):
        parse_window(None, date(2026, 2, 5), date(2026, 1, 5))
    with pytest.raises(ValueError):
        parse_window("forever", None, None)


def test_window_bounds_are_pacific_midnight():
    window = parse_window(None, date(2026, 7, 1), date(2026, 7, 1))
    # PDT is UTC-7
    assert window.start_utc == datetime(2026, 7, 1, 7, 0)
    assert window.end_utc == datetime(2026, 7, 2, 7, 0)


def test_normalization():
    assert tracking_service.normalize_dj_name("  DJ   Marmot ") == "dj marmot"
    assert tracking_service.normalize_dj_name("   ") is None
    assert tracking_service.normalize_person_name("Jane  Doe.") == "jane doe"
    assert tracking_service.normalize_phone("+1 (510) 555-1234") == "5105551234"
    assert tracking_service.normalize_phone("510-555-1234") == "5105551234"


# ---------------------------------------------------------------------------
# Access


def test_promotions_and_site_admins_can_read_tabs(
    client: TestClient, db: Session, monkeypatch
):
    _staff(db, "promo@example.com", department="Promotions")
    _staff(db, "admin@example.com")
    _staff(db, "staff@example.com")
    monkeypatch.setattr(settings, "site_admin_emails", "admin@example.com")

    for email in ("promo@example.com", "admin@example.com"):
        r = client.get("/api/analytics/tabs/overview", headers=_as(email))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["window"]["preset"] == "last_30_days"
        assert all("explanation" in m for m in body["metrics"])

    assert (
        client.get(
            "/api/analytics/tabs/overview", headers=_as("staff@example.com")
        ).status_code
        == 403
    )
    assert (
        client.get("/api/analytics/tabs/nope", headers=_as("promo@example.com")).status_code
        == 404
    )
    r = client.get(
        "/api/analytics/tabs/overview?from=2026-02-01&to=2026-01-01",
        headers=_as("promo@example.com"),
    )
    assert r.status_code == 400


@pytest.mark.parametrize(
    "tab", ["overview", "venues", "djs", "reps", "short_links", "usage"]
)
def test_every_tab_renders_with_no_data(client: TestClient, db: Session, tab):
    _staff(db, "promo@example.com", department="Promotions")
    r = client.get(
        f"/api/analytics/tabs/{tab}?preset=all_time", headers=_as("promo@example.com")
    )
    assert r.status_code == 200, r.text
    assert r.json()["metrics"]


def test_venue_and_dj_pages_handle_missing_things(client: TestClient, db: Session):
    _staff(db, "promo@example.com", department="Promotions")
    r = client.get(
        "/api/analytics/tabs/venue?venue_id=999", headers=_as("promo@example.com")
    )
    assert r.status_code == 200
    assert r.json()["metrics"] == []
    r = client.get("/api/analytics/tabs/dj?dj=unknown", headers=_as("promo@example.com"))
    assert r.json()["title"] == "Unknown DJ"


# ---------------------------------------------------------------------------
# Active-day beacon


def test_beacon_records_one_active_day_per_subsite(client: TestClient, db: Session):
    _staff(db, "staff@example.com")
    for _ in range(3):
        r = client.post(
            "/api/analytics/beacon",
            json={"subsite": "directory"},
            headers=_as("staff@example.com"),
        )
        assert r.status_code == 204
    client.post(
        "/api/analytics/beacon",
        json={"subsite": "workforms"},
        headers=_as("staff@example.com"),
    )
    rows = db.query(AnalyticsEvent).filter(AnalyticsEvent.event_type == "active_day").all()
    assert sorted(r.dimension for r in rows) == ["directory", "workforms"]
    assert (
        client.post(
            "/api/analytics/beacon",
            json={"subsite": "elsewhere"},
            headers=_as("staff@example.com"),
        ).status_code
        == 400
    )


def test_beacon_skips_non_staff_and_impersonation(
    client: TestClient, db: Session, monkeypatch
):
    _staff(db, "gone@example.com", active=False)
    _staff(db, "admin@example.com")
    _staff(db, "target@example.com")
    monkeypatch.setattr(settings, "environment", "staging")
    db.add(
        ImpersonationSession(
            real_email="admin@example.com", impersonated_email="target@example.com"
        )
    )
    db.commit()
    client.post(
        "/api/analytics/beacon", json={"subsite": "home"}, headers=_as("gone@example.com")
    )
    client.post(
        "/api/analytics/beacon", json={"subsite": "home"}, headers=_as("admin@example.com")
    )
    assert db.query(AnalyticsEvent).count() == 0


def test_usage_tab_counts_active_days(client: TestClient, db: Session):
    _staff(db, "promo@example.com", department="Promotions")
    _staff(db, "staff@example.com")
    client.post(
        "/api/analytics/beacon",
        json={"subsite": "directory"},
        headers=_as("staff@example.com"),
    )
    client.post(
        "/api/analytics/beacon", json={"subsite": "home"}, headers=_as("staff@example.com")
    )
    r = client.get("/api/analytics/tabs/usage", headers=_as("promo@example.com"))
    metrics = {m["id"]: m for m in r.json()["metrics"]}
    assert metrics["users_per_day"]["rows"][-1]["users"] == 1
    users = metrics["users"]["rows"]
    assert users == [{"name": "staff", "days": 1, "last_seen": users[0]["last_seen"]}]
    assert {row["subsite"] for row in metrics["users_by_subsite"]["rows"]} == {
        "KALX Staff Directory",
        "Home page",
    }
    assert metrics["users"]["explanation"]["data_since"] is not None


# ---------------------------------------------------------------------------
# Rollup


def test_rollup_keeps_counts(db: Session):
    now = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)
    old = (now - timedelta(days=tracking_service.RAW_RETENTION_DAYS + 5)).replace(
        tzinfo=None
    )
    recent = (now - timedelta(days=3)).replace(tzinfo=None)
    for when, email in [
        (old, "a@example.com"),
        (old, "a@example.com"),
        (old, "b@example.com"),
        (recent, "a@example.com"),
    ]:
        db.add(
            AnalyticsEvent(
                occurred_at=when,
                event_type="active_day",
                area=COMMON_AREA,
                actor_email=email,
                dimension="home",
                ref="dropped",
            )
        )
    db.commit()
    start, end = date(2020, 1, 1), date(2026, 12, 31)
    before = sum(
        c.count for c in tracking_service.event_counts(db, ["active_day"], start, end)
    )
    since_before = tracking_service.data_since(db, ["active_day"])

    assert roll_up_old_events(db, now=now) == 3
    assert roll_up_old_events(db, now=now) == 0

    assert db.query(AnalyticsEvent).count() == 1
    rolled = {r.actor_email: r.count for r in db.query(AnalyticsDailyCount).all()}
    assert rolled == {"a@example.com": 2, "b@example.com": 1}
    after = sum(
        c.count for c in tracking_service.event_counts(db, ["active_day"], start, end)
    )
    assert after == before == 4
    assert tracking_service.data_since(db, ["active_day"]) == since_before


def test_rollup_job_is_listed(client: TestClient, db: Session, monkeypatch):
    _staff(db, "admin@example.com")
    monkeypatch.setattr(settings, "site_admin_emails", "admin@example.com")
    r = client.get("/api/admin/job-statuses", headers=_as("admin@example.com"))
    assert "analytics_rollup" in {j["id"] for j in r.json()}
