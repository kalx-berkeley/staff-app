"""Tests for the app-wide admin API (KALX Staff Admin)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.areas import COMMON_AREA, PASS_GIVEAWAY_AREA, WORKFORMS_AREA
from app.common.services.audit_service import log_event
from app.config import settings
from app.models.impersonation_session import ImpersonationSession
from app.models.job_log import JobLog
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.workform_department import DepartmentHead


def _make_staff(
    db: Session,
    email: str,
    *,
    department: str | None = None,
    head_of: str | None = None,
    active: bool = True,
    paid: bool = False,
) -> Staff:
    staff = Staff(
        email=email, name=email.split("@")[0], phone="", airtable_record_id=f"rec-{email}"
    )
    db.add(staff)
    db.flush()
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    if active:
        db.add(StaffStatus(staff_id=staff.id, status="Active"))
    if paid:
        db.add(StaffStatus(staff_id=staff.id, status="Paid Staff"))
    if head_of:
        db.add(DepartmentHead(department=head_of, staff_airtable_record_id=f"rec-{email}"))
    db.commit()
    return staff


def _as(email: str) -> dict:
    return {"X-Forwarded-User": email}


@pytest.fixture
def staging(monkeypatch):
    monkeypatch.setattr(settings, "environment", "staging")


@pytest.mark.parametrize(
    "kwargs,listed,site_admin,promotions_admin",
    [
        ({"department": "Promotions"}, False, False, True),
        ({"head_of": "Music"}, False, True, False),
        ({"paid": True}, False, True, False),
        ({}, True, True, False),
        ({"department": "Promotions", "paid": True}, False, True, True),
        ({}, False, False, False),
        ({"head_of": "Music", "active": False}, False, False, False),
        ({"paid": True, "active": False}, False, False, False),
        ({"department": "Promotions", "active": False}, False, False, False),
        ({"active": False}, True, False, False),
    ],
    ids=[
        "promotions",
        "department-head",
        "paid-staff",
        "listed-email",
        "paid-promotions",
        "staff",
        "inactive-head",
        "inactive-paid-staff",
        "inactive-promotions",
        "inactive-listed-email",
    ],
)
def test_who_is_an_admin(
    client: TestClient,
    db: Session,
    monkeypatch,
    kwargs,
    listed,
    site_admin,
    promotions_admin,
):
    if listed:
        monkeypatch.setattr(
            settings, "site_admin_emails", "other@example.com, SOMEONE@example.com"
        )
    _make_staff(db, "someone@example.com", **kwargs)
    headers = _as("someone@example.com")

    me = client.get("/api/users/me", headers=headers).json()
    jobs = client.get("/api/admin/job-statuses", headers=headers)
    run = client.post("/api/admin/jobs/nope/run", headers=headers)
    schedules = client.get("/api/pass-giveaway/admin/auto-close-schedules", headers=headers)

    assert me["is_site_admin"] is site_admin
    assert me["is_promotions_admin"] is promotions_admin
    either = site_admin or promotions_admin
    assert jobs.status_code == (200 if either else 403)
    assert schedules.status_code == (200 if either else 403)
    # 404 for an unknown job once past the site admin check
    assert run.status_code == (404 if site_admin else 403)


def test_job_statuses_list_every_sub_sites_jobs(client: TestClient, db: Session):
    _make_staff(db, "head@example.com", head_of="Music")
    db.add(JobLog(job_id="workform_records_refresh", trigger="scheduled"))
    db.commit()

    response = client.get("/api/admin/job-statuses", headers=_as("head@example.com"))

    assert response.status_code == 200
    jobs = {job["id"]: job for job in response.json()}
    assert jobs["airtable_user_sync"]["area"] == "Common"
    assert jobs["feature_bin_sync"]["area"] == "Radio Pass Giveaway"
    assert jobs["workform_records_refresh"]["area"] == "KALX Workforms"
    assert jobs["workform_records_refresh"]["last_run_at"] is not None
    assert jobs["workform_emails"]["can_run"] is False
    assert jobs["feature_bin_sync"]["can_run"] is True


def test_cannot_run_a_job_that_is_not_runnable(client: TestClient, db: Session):
    _make_staff(db, "head@example.com", head_of="Music")

    response = client.post(
        "/api/admin/jobs/workform_emails/run", headers=_as("head@example.com")
    )

    assert response.status_code == 400


def test_promotions_admins_cannot_run_jobs(client: TestClient, db: Session, monkeypatch):
    _make_staff(db, "promo@example.com", department="Promotions")
    monkeypatch.setattr(settings, "airtable_api_key", None)

    response = client.post(
        "/api/admin/jobs/workform_records_refresh/run", headers=_as("promo@example.com")
    )

    assert response.status_code == 403


def test_run_workforms_refresh_reports_unconfigured_airtable(
    client: TestClient, db: Session, monkeypatch
):
    _make_staff(db, "head@example.com", head_of="Music")
    monkeypatch.setattr(settings, "airtable_api_key", None)

    response = client.post(
        "/api/admin/jobs/workform_records_refresh/run", headers=_as("head@example.com")
    )

    assert response.status_code == 200
    assert response.json()["success"] is False


def _log_one_event_per_area(db: Session) -> None:
    log_event(db, event_type="airtable_sync_added", area=COMMON_AREA)
    log_event(db, event_type="show_created", area=PASS_GIVEAWAY_AREA)
    log_event(db, event_type="workform_decision", area=WORKFORMS_AREA)


def test_site_admins_see_every_areas_audit_log(client: TestClient, db: Session):
    _make_staff(db, "head@example.com", head_of="Music")
    _log_one_event_per_area(db)

    everything = client.get("/api/admin/audit-log", headers=_as("head@example.com"))
    workforms = client.get(
        "/api/admin/audit-log",
        params={"area": WORKFORMS_AREA},
        headers=_as("head@example.com"),
    )

    assert everything.status_code == 200
    assert {e["area"] for e in everything.json()} == {
        COMMON_AREA,
        PASS_GIVEAWAY_AREA,
        WORKFORMS_AREA,
    }
    assert [e["event_type"] for e in workforms.json()] == ["workform_decision"]


def test_promotions_admins_see_only_the_pass_giveaways_audit_log(
    client: TestClient, db: Session
):
    _make_staff(db, "promo@example.com", department="Promotions")
    _log_one_event_per_area(db)

    everything = client.get("/api/admin/audit-log", headers=_as("promo@example.com"))
    workforms = client.get(
        "/api/admin/audit-log",
        params={"area": WORKFORMS_AREA},
        headers=_as("promo@example.com"),
    )

    assert everything.status_code == 200
    assert [e["event_type"] for e in everything.json()] == ["show_created"]
    assert workforms.json() == []


def test_department_head_can_impersonate_in_staging(
    client: TestClient, db: Session, staging
):
    _make_staff(db, "head@example.com", head_of="Music")
    _make_staff(db, "staff@example.com")

    users = client.get("/api/admin/users", headers=_as("head@example.com"))
    start = client.post(
        "/api/admin/impersonate",
        json={"email": "staff@example.com"},
        headers=_as("head@example.com"),
    )
    me = client.get("/api/users/me", headers=_as("head@example.com"))

    assert {u["email"] for u in users.json()} == {"head@example.com", "staff@example.com"}
    assert start.status_code == 200
    # Still a site admin while acting as a non-admin, so they can reach the admin tools
    assert me.json()["email"] == "staff@example.com"
    assert me.json()["is_department_head"] is False
    assert me.json()["is_site_admin"] is True


def test_promotions_admins_cannot_impersonate(client: TestClient, db: Session, staging):
    _make_staff(db, "promo@example.com", department="Promotions")
    _make_staff(db, "staff@example.com")

    users = client.get("/api/admin/users", headers=_as("promo@example.com"))
    start = client.post(
        "/api/admin/impersonate",
        json={"email": "staff@example.com"},
        headers=_as("promo@example.com"),
    )

    assert users.status_code == 403
    assert start.status_code == 403


def test_impersonation_is_staging_only(client: TestClient, db: Session):
    _make_staff(db, "head@example.com", head_of="Music")

    response = client.post(
        "/api/admin/impersonate",
        json={"email": "head@example.com"},
        headers=_as("head@example.com"),
    )

    assert response.status_code == 403


def test_non_admin_cannot_impersonate(client: TestClient, db: Session, staging):
    _make_staff(db, "staff@example.com")

    response = client.post(
        "/api/admin/impersonate",
        json={"email": "staff@example.com"},
        headers=_as("staff@example.com"),
    )

    assert response.status_code == 403


def test_anyone_can_end_their_own_impersonation(client: TestClient, db: Session, staging):
    # e.g. someone who stopped heading a department mid-impersonation
    _make_staff(db, "former-head@example.com")
    db.add(
        ImpersonationSession(
            real_email="former-head@example.com", impersonated_email="x@example.com"
        )
    )
    db.commit()

    response = client.delete(
        "/api/admin/impersonate", headers=_as("former-head@example.com")
    )

    assert response.status_code == 200
    assert db.query(ImpersonationSession).count() == 0
