"""Tests for the work types department heads offer staff in KALX Workforms."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.services.user_service import UserService
from app.models.audit_log import AuditLog
from app.workforms.services.departments import sync_department_heads
from app.workforms.services.months import format_month, open_months
from tests.workforms.conftest import as_user, make_staff

MEL = "mel@example.com"
OLA = "ola@example.com"
SAM = "sam@example.com"


@pytest.fixture
def people(db: Session, departments):
    """Mel heads Music, Ola heads Operations; Sam is staff."""
    return {
        "mel": make_staff(db, MEL, "Mel", "recMEL00000000000", heads=("Music",)),
        "ola": make_staff(db, OLA, "Ola", "recOLA00000000000", heads=("Operations",)),
        "sam": make_staff(db, SAM, "Sam", "recSAM00000000000", departments=("Music",)),
    }


def _set(client, who, department, work_types, allow_free_text=True):
    return client.put(
        f"/api/workforms/review/work-types/{department}",
        json={"work_types": work_types, "allow_free_text": allow_free_text},
        headers=as_user(who),
    )


def _add(client, description, department="Music"):
    return client.post(
        f"/api/workforms/me/{format_month(open_months()[0])}/entries",
        json={"department": department, "hours": 1, "description": description},
        headers=as_user(SAM),
    )


def test_departments_have_no_work_types_by_default(client: TestClient, people):
    response = client.get("/api/workforms/review/work-types/Music", headers=as_user(MEL))
    assert response.json() == {"work_types": [], "allow_free_text": True}
    departments = client.get("/api/workforms/departments", headers=as_user(SAM)).json()
    assert departments["work_types"] == {}


def test_head_sets_work_types(client: TestClient, db, people):
    response = _set(client, MEL, "Music", [" Filing  CDs ", "Reviews", "", "reviews"])
    assert response.status_code == 200
    assert response.json() == {
        "work_types": ["Filing CDs", "Reviews"],
        "allow_free_text": True,
    }

    departments = client.get("/api/workforms/departments", headers=as_user(SAM)).json()
    assert departments["work_types"] == {
        "Music": {"work_types": ["Filing CDs", "Reviews"], "allow_free_text": True}
    }
    log = (
        db.query(AuditLog)
        .filter(AuditLog.event_type == "workform_work_types_updated")
        .one()
    )
    assert log.actor_email == MEL


def test_who_can_set_work_types(client: TestClient, people):
    assert _set(client, SAM, "Music", ["Reviews"]).status_code == 403
    assert _set(client, MEL, "Promotions", ["Tabling"]).status_code == 403
    assert (
        client.get(
            "/api/workforms/review/work-types/Promotions", headers=as_user(MEL)
        ).status_code
        == 403
    )
    # Operations heads can set any department's, as they can review any
    assert _set(client, OLA, "Promotions", ["Tabling"]).status_code == 200


def test_requiring_a_work_type_needs_one(client: TestClient, people):
    response = _set(client, MEL, "Music", [], allow_free_text=False)
    assert response.status_code == 422
    assert _set(client, MEL, "Music", ["x" * 101]).status_code == 422
    assert _set(client, MEL, "Music", [f"Type {i}" for i in range(51)]).status_code == 422


def test_free_text_allowed_alongside_work_types(client: TestClient, people):
    _set(client, MEL, "Music", ["Reviews"])
    assert _add(client, "Reviews").status_code == 201
    assert _add(client, "Something else").status_code == 201


def test_staff_must_choose_a_work_type_when_required(client: TestClient, people):
    _set(client, MEL, "Music", ["Reviews", "Filing CDs"], allow_free_text=False)

    response = _add(client, "Something else")
    assert response.status_code == 422
    assert response.json()["detail"] == "Choose one of the Music types of work"
    assert _add(client, " Filing CDs ").status_code == 201
    # Other departments aren't affected
    assert _add(client, "Tabling", department="Promotions").status_code == 201

    # Changing an entry checks it too
    entry = _add(client, "Reviews").json()
    response = client.put(
        f"/api/workforms/me/{format_month(open_months()[0])}/entries/{entry['id']}",
        json={"department": "Music", "hours": 2, "description": "Other"},
        headers=as_user(SAM),
    )
    assert response.status_code == 422


def test_removing_all_work_types_allows_free_text(client: TestClient, people):
    _set(client, MEL, "Music", ["Reviews"], allow_free_text=False)
    _set(client, MEL, "Music", [], allow_free_text=True)
    assert _add(client, "Anything").status_code == 201


async def test_work_types_survive_the_department_sync(client: TestClient, db, people):
    _set(client, MEL, "Music", ["Reviews"], allow_free_text=False)

    heads_table = [{
        "id": "recDH1",
        "fields": {"Department": ["recDEPMUSIC"], "Department Heads": ["recMEL"]},
    }]
    with (
        patch.object(
            UserService, "fetch_airtable_records", AsyncMock(return_value=heads_table)
        ),
        patch.object(
            UserService,
            "fetch_department_names",
            AsyncMock(return_value={"recDEPMUSIC": "Music"}),
        ),
    ):
        await sync_department_heads(db, {"errors": []})

    assert _add(client, "Something else").status_code == 422
