"""Tests for the KALX Workforms review API for department heads."""

import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_log import AuditLog
from app.models.impersonation_session import ImpersonationSession
from app.workforms.services import review_service
from app.workforms.services.months import format_month, open_months
from app.workforms.services.records import refresh_all
from tests.workforms.conftest import as_user, make_staff

MONTH = date(2026, 9, 1)
PATH = format_month(MONTH)


@pytest.fixture
def people(db: Session, departments):
    """Mel heads Music, Ola heads Operations, Pat heads Promotions; Sam is staff."""
    return {
        "mel": make_staff(
            db, "mel@example.com", "Mel", "recMEL00000000000", heads=("Music",)
        ),
        "ola": make_staff(
            db, "ola@example.com", "Ola", "recOLA00000000000", heads=("Operations",)
        ),
        "pat": make_staff(
            db, "pat@example.com", "Pat", "recPAT00000000000", heads=("Promotions",)
        ),
        "sam": make_staff(db, "sam@example.com", "Sam", "recSAM00000000000"),
    }


def _submission(airtable, record_id, **departments):
    fields = {"Name": [record_id], "Month": MONTH.isoformat()}
    for department, hours in departments.items():
        department = department.replace("_", " ")
        fields[f"{department} : Hours"] = hours
        fields[f"{department} : Description"] = f"({hours}h): work"
    return airtable.add(fields)


def _queue(client, who, department):
    return client.get(f"/api/workforms/review/{PATH}/{department}", headers=as_user(who))


def test_non_heads_cant_review(client: TestClient, people, airtable):
    assert (
        client.get("/api/workforms/review", headers=as_user("sam@example.com")).status_code
        == 403
    )


def test_head_sees_their_departments_submissions(client: TestClient, people, airtable):
    _submission(airtable, "recSAM00000000000", Music=2, Promotions=3)
    _submission(airtable, "recPAT00000000000", Promotions=1)

    overview = client.get(
        "/api/workforms/review", headers=as_user("mel@example.com")
    ).json()
    assert overview["own_departments"] == ["Music"]
    assert overview["fallback_departments"] == []
    assert overview["is_operations_head"] is False

    body = _queue(client, "mel@example.com", "Music").json()
    assert [i["staff_name"] for i in body["items"]] == ["Sam"]
    assert body["items"][0]["hours"] == 2
    assert body["items"][0]["edited_in_airtable"] is True  # not submitted by the app
    assert (body["total"], body["reviewed"], body["remaining"]) == (1, 0, 1)

    assert _queue(client, "mel@example.com", "Promotions").status_code == 403


def test_heads_own_hours_go_to_operations(client: TestClient, people, airtable):
    _submission(airtable, "recPAT00000000000", Promotions=1)
    assert _queue(client, "pat@example.com", "Promotions").json()["items"] == []
    items = _queue(client, "ola@example.com", "Promotions").json()["items"]
    assert [i["staff_name"] for i in items] == ["Pat"]


def test_operations_head_departments(client: TestClient, people, airtable):
    overview = client.get(
        "/api/workforms/review", headers=as_user("ola@example.com")
    ).json()
    assert overview["is_operations_head"] is True
    # Special Events has no head, so it's one of Ola's own
    assert overview["own_departments"] == ["Operations", "Special Events"]
    assert overview["fallback_departments"] == ["Music", "Promotions"]


def test_operations_head_can_review_own_operations_hours(
    client: TestClient, db, people, airtable
):
    record = _submission(airtable, "recOLA00000000000", Operations=2)
    items = _queue(client, "ola@example.com", "Operations").json()["items"]
    assert [i["staff_name"] for i in items] == ["Ola"]
    response = client.put(
        f"/api/workforms/review/decisions/{record['id']}/Operations",
        json={"decision": "Approved"},
        headers=as_user("ola@example.com"),
    )
    assert response.status_code == 200
    log = db.query(AuditLog).filter(AuditLog.event_type == "workform_decision").one()
    assert log.details["self_review"] is True


def test_approve_deny_and_clear(client: TestClient, db, people, airtable):
    record = _submission(airtable, "recSAM00000000000", Music=2)
    url = f"/api/workforms/review/decisions/{record['id']}/Music"
    mel = as_user("mel@example.com")

    response = client.put(url, json={"decision": "Approved"}, headers=mel)
    assert response.status_code == 200
    assert response.json()["decision"] == "Approved"
    assert airtable.records[record["id"]]["fields"]["Music : Approved"] == ["Approved"]
    body = _queue(client, "mel@example.com", "Music").json()
    assert (body["reviewed"], body["remaining"]) == (1, 0)

    client.put(url, json={"decision": "Denied"}, headers=mel)
    assert airtable.records[record["id"]]["fields"]["Music : Approved"] == ["Denied"]

    client.put(url, json={"decision": None}, headers=mel)
    assert "Music : Approved" not in airtable.records[record["id"]]["fields"]

    logs = db.query(AuditLog).filter(AuditLog.event_type == "workform_decision").all()
    assert [(log.details["before"], log.details["after"]) for log in logs] == [
        (None, "Approved"),
        ("Approved", "Denied"),
        ("Denied", None),
    ]
    assert logs[0].actor_email == "mel@example.com"


def test_cant_decide_on_other_departments_or_own_hours(
    client: TestClient, people, airtable
):
    record = _submission(airtable, "recMEL00000000000", Music=2, Promotions=1)
    mel = as_user("mel@example.com")
    for department in ("Music", "Promotions"):
        response = client.put(
            f"/api/workforms/review/decisions/{record['id']}/{department}",
            json={"decision": "Approved"},
            headers=mel,
        )
        assert response.status_code == 403
    response = client.put(
        f"/api/workforms/review/decisions/{record['id']}/Special Events",
        json={"decision": "Approved"},
        headers=as_user("ola@example.com"),
    )
    assert response.status_code == 404  # no Special Events hours


def test_review_shows_submitted_entries_late_and_loa(
    client: TestClient, db, people, airtable
):
    # Submit through the app, in an open month, as someone with a leave
    month = open_months()[0]
    lou = make_staff(
        db,
        "lou@example.com",
        "Lou",
        "recLOU00000000000",
        loa_start=month.replace(day=10),
        loa_end=month.replace(day=20),
    )
    headers = as_user(lou.email)
    path = f"/api/workforms/me/{format_month(month)}"
    client.post(
        f"{path}/entries",
        headers=headers,
        json={
            "department": "Music",
            "hours": 2,
            "description": "Filing",
            "work_date": month.replace(day=12).isoformat(),
        },
    )
    client.post(
        f"{path}/entries",
        headers=headers,
        json={
            "department": "Music",
            "hours": 1,
            "description": "Sorting",
        },
    )
    airtable.created_time = "2099-01-01T00:00:00.000Z"
    assert client.post(f"{path}/submit", headers=headers).status_code == 200

    body = client.get(
        f"/api/workforms/review/{format_month(month)}/Music",
        headers=as_user("mel@example.com"),
    ).json()
    (item,) = body["items"]
    assert item["hours"] == 3
    assert item["edited_in_airtable"] is False
    assert item["is_late"] is True
    assert item["loa_overlaps_month"] is True
    assert [e["loa_flag"] for e in item["entries"]] == ["inside", "may_overlap"]

    # A hand edit of the hours in Airtable
    (record,) = airtable.records.values()
    record["fields"]["Music : Hours"] = 5
    asyncio.run(refresh_all(db))
    review_service._reset_for_testing()
    item = client.get(
        f"/api/workforms/review/{format_month(month)}/Music",
        headers=as_user("mel@example.com"),
    ).json()["items"][0]
    assert item["hours"] == 5
    assert item["edited_in_airtable"] is True
    assert sum(e["hours"] for e in item["entries"]) == 3


def test_default_month_is_latest_with_pending(client: TestClient, people, airtable):
    _submission(airtable, "recSAM00000000000", Music=2)
    client.get(f"/api/workforms/review/{PATH}/pending", headers=as_user("mel@example.com"))
    overview = client.get(
        "/api/workforms/review", headers=as_user("mel@example.com")
    ).json()
    assert overview["default_month"] == PATH
    assert overview["default_department"] == "Music"
    pending = client.get(
        f"/api/workforms/review/{PATH}/pending", headers=as_user("mel@example.com")
    ).json()
    assert pending["pending"] == {"Music": 1}


def test_impersonating_a_head_can_decide(
    client: TestClient, db, people, airtable, monkeypatch
):
    monkeypatch.setattr(settings, "environment", "staging")
    record = _submission(airtable, "recSAM00000000000", Music=2)
    db.add(
        ImpersonationSession(
            real_email="sam@example.com", impersonated_email="mel@example.com"
        )
    )
    db.commit()
    response = client.put(
        f"/api/workforms/review/decisions/{record['id']}/Music",
        json={"decision": "Approved"},
        headers=as_user("sam@example.com"),
    )
    assert response.status_code == 200


def test_users_me_reports_department_heads(client: TestClient, people):
    me = client.get("/api/users/me", headers=as_user("mel@example.com")).json()
    assert me["is_department_head"] is True
    me = client.get("/api/users/me", headers=as_user("sam@example.com")).json()
    assert me["is_department_head"] is False
