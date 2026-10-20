"""Tests for the KALX Workforms staff API: entries, submitting and past workforms."""

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.workform import Workform, WorkformEntry
from app.workforms.services import months
from app.workforms.services.months import (
    deadline,
    format_month,
    is_late,
    open_months,
    parse_month,
    previous_month,
)
from app.workforms.services.records import refresh_all
from app.workforms.services.workform_service import combine
from tests.workforms.conftest import as_user, make_staff

AMY = "amy@example.com"
AMY_ID = "recAMY00000000000"


@pytest.fixture
def amy(db: Session, departments):
    return make_staff(db, AMY, "Amy Adams", AMY_ID, departments=("Promotions",))


def _this_month() -> date:
    return open_months()[0]


def _month_path(month: date | None = None) -> str:
    return format_month(month or _this_month())


def _add(client, month=None, **body):
    entry = {"department": "Promotions", "hours": 2, "description": "Tabling"}
    entry.update(body)
    return client.post(
        f"/api/workforms/me/{_month_path(month)}/entries", json=entry, headers=as_user(AMY)
    )


# --- months and deadlines ---


def test_open_months_are_this_month_and_last():
    assert open_months(date(2026, 1, 15)) == [date(2026, 1, 1), date(2025, 12, 1)]


def test_deadline_is_end_of_the_5th_pacific():
    due = deadline(date(2026, 10, 1))
    # 23:59:59 PST on Nov 5 is 07:59:59 UTC on Nov 6
    assert due == datetime(2026, 11, 6, 7, 59, 59, tzinfo=timezone.utc)
    assert not is_late(date(2026, 10, 1), datetime(2026, 11, 6, 7, 59, 59))
    assert is_late(date(2026, 10, 1), datetime(2026, 11, 6, 8, 0, 0))


def test_parse_month_rejects_bad_values():
    assert parse_month("2026-10") == date(2026, 10, 1)
    for bad in ("2026-13", "26-10", "2026-1", "october"):
        with pytest.raises(ValueError):
            parse_month(bad)


# --- combining entries ---


def test_combine_sorts_dated_entries_first_and_formats_lines():
    entries = [
        WorkformEntry(
            id=1,
            department="Promotions",
            hours=3,
            description="Inventory",
            work_date=None,
            created_at=datetime(2026, 10, 1),
        ),
        WorkformEntry(
            id=2,
            department="Promotions",
            hours=1.5,
            description="Postered",
            work_date=date(2026, 10, 17),
            created_at=datetime(2026, 10, 2),
        ),
        WorkformEntry(
            id=3,
            department="Promotions",
            hours=2,
            description="Ran the table",
            work_date=date(2026, 10, 3),
            created_at=datetime(2026, 10, 3),
        ),
        WorkformEntry(
            id=4,
            department="Music",
            hours=0.25,
            description="Filing",
            work_date=None,
            created_at=datetime(2026, 10, 4),
        ),
    ]
    blocks = combine(entries)
    assert list(blocks) == ["Music", "Promotions"]
    assert blocks["Promotions"]["hours"] == 6.5
    assert (
        blocks["Promotions"]["description"]
        == "10-03 (2h): Ran the table\n10-17 (1.5h): Postered\n(3h): Inventory"
    )
    assert blocks["Music"]["description"] == "(0.25h): Filing"


# --- entries ---


def test_new_staff_can_use_workforms(client: TestClient, db: Session, departments):
    make_staff(db, "new@example.com", "Nia New", "recNEW", statuses=("🆕",))
    headers = as_user("new@example.com")

    response = client.post(
        f"/api/workforms/me/{_month_path(None)}/entries",
        json={"department": "Promotions", "hours": 1, "description": "Training"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert client.get("/api/workforms/me", headers=headers).status_code == 200


def test_add_update_and_delete_entries(client: TestClient, amy):
    response = _add(client, work_date=_this_month().isoformat())
    assert response.status_code == 201, response.text
    entry_id = response.json()["id"]

    response = client.put(
        f"/api/workforms/me/{_month_path()}/entries/{entry_id}",
        json={"department": "Music", "hours": 1.25, "description": " Filing "},
        headers=as_user(AMY),
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Filing"

    workform = client.get(f"/api/workforms/me/{_month_path()}", headers=as_user(AMY)).json()
    assert workform["status"] == "draft"
    assert [e["department"] for e in workform["entries"]] == ["Music"]

    response = client.delete(
        f"/api/workforms/me/{_month_path()}/entries/{entry_id}", headers=as_user(AMY)
    )
    assert response.status_code == 204
    workform = client.get(f"/api/workforms/me/{_month_path()}", headers=as_user(AMY)).json()
    assert workform["status"] == "not_started"


@pytest.mark.parametrize(
    "body",
    [
        {"hours": 0},
        {"hours": -1},
        {"hours": 1.1},
        {"description": "   "},
        {"department": "Nonexistent"},
        {"work_date": "1999-01-01"},
    ],
)
def test_invalid_entries_are_refused(client: TestClient, amy, body):
    assert _add(client, **body).status_code == 422


def test_large_hours_and_future_dates_in_the_month_are_allowed(client: TestClient, amy):
    month = _this_month()
    last = months.last_day_of_month(month)
    assert _add(client, hours=250.75, work_date=last.isoformat()).status_code == 201


def test_older_months_are_closed(client: TestClient, amy):
    old = previous_month(previous_month(_this_month()))
    assert _add(client, month=old).status_code == 400
    response = client.post(
        f"/api/workforms/me/{format_month(old)}/submit", headers=as_user(AMY)
    )
    assert response.status_code == 400


def test_last_month_is_open(client: TestClient, amy):
    assert _add(client, month=previous_month(_this_month())).status_code == 201


def test_another_users_entry_is_not_found(client: TestClient, db, amy):
    entry_id = _add(client).json()["id"]
    make_staff(db, "bob@example.com", "Bob Brown", "recBOB00000000000")
    response = client.delete(
        f"/api/workforms/me/{_month_path()}/entries/{entry_id}",
        headers=as_user("bob@example.com"),
    )
    assert response.status_code == 404


def test_inactive_staff_cant_use_workforms(client: TestClient, db, departments):
    make_staff(db, "gone@example.com", "Gone", "recGONE0000000000", statuses=("Alumni",))
    response = client.get("/api/workforms/me", headers=as_user("gone@example.com"))
    assert response.status_code == 403


def test_departments_list_own_first(client: TestClient, amy):
    response = client.get("/api/workforms/departments", headers=as_user(AMY))
    assert response.json() == {
        "own": ["Promotions"],
        "other": ["Music", "Operations", "Special Events"],
    }


def test_loa_flags_on_entries(client: TestClient, db, departments):
    month = _this_month()
    make_staff(
        db,
        "lou@example.com",
        "Lou",
        "recLOU00000000000",
        loa_start=month.replace(day=10),
        loa_end=month.replace(day=20),
    )
    headers = as_user("lou@example.com")
    path = f"/api/workforms/me/{_month_path()}/entries"
    base = {"department": "Music", "hours": 1, "description": "x"}
    inside = client.post(
        path, json={**base, "work_date": month.replace(day=15).isoformat()}, headers=headers
    ).json()
    outside = client.post(
        path, json={**base, "work_date": month.replace(day=2).isoformat()}, headers=headers
    ).json()
    undated = client.post(path, json=base, headers=headers).json()
    assert inside["loa_flag"] == "inside"
    assert outside["loa_flag"] is None
    assert undated["loa_flag"] == "may_overlap"


def test_leave_overlapping_the_month_is_flagged(client: TestClient, db, departments, amy):
    month = _this_month()
    make_staff(
        db,
        "lou@example.com",
        "Lou",
        "recLOU00000000000",
        loa_start=month.replace(day=10),
        loa_end=month.replace(day=20),
    )
    lou = client.get(
        f"/api/workforms/me/{_month_path()}", headers=as_user("lou@example.com")
    )
    assert lou.json()["loa_overlaps_month"] is True
    summaries = client.get("/api/workforms/me", headers=as_user("lou@example.com")).json()
    flags = {w["month"]: w["loa_overlaps_month"] for w in summaries["workforms"]}
    assert flags[_month_path()] is True
    previous = format_month(previous_month(month.replace(day=1)))
    assert flags.get(previous, False) is False

    amy_month = client.get(f"/api/workforms/me/{_month_path()}", headers=as_user(AMY))
    assert amy_month.json()["loa_overlaps_month"] is False


# --- submitting ---


def test_submit_creates_an_airtable_record(client: TestClient, db, amy, airtable):
    _add(client, hours=2, description="Ran the table", work_date=_this_month().isoformat())
    _add(client, department="Music", hours=1, description="Filing")

    response = client.post(
        f"/api/workforms/me/{_month_path()}/submit", headers=as_user(AMY)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "submitted"
    assert body["has_unsent_changes"] is False
    assert body["results"]["Promotions"]["hours"] == 2

    (record,) = airtable.records.values()
    fields = record["fields"]
    assert fields["Name"] == [AMY_ID]
    assert fields["Month"] == _this_month().isoformat()
    assert fields["Promotions : Hours"] == 2
    assert (
        fields["Promotions : Description"] == f"{_this_month():%m}-01 (2h): Ran the table"
    )
    assert fields["Music : Description"] == "(1h): Filing"
    assert "Promotions : Approved" not in fields

    workform = db.query(Workform).one()
    assert workform.airtable_record_id == record["id"]
    assert (
        db.query(AuditLog).filter(AuditLog.event_type == "workform_submitted").count() == 1
    )


def test_zero_hour_workform(client: TestClient, amy, airtable):
    response = client.post(
        f"/api/workforms/me/{_month_path()}/submit", headers=as_user(AMY)
    )
    assert response.status_code == 200
    (record,) = airtable.records.values()
    assert set(record["fields"]) == {"Name", "Month", "Created Time"}
    me = client.get("/api/workforms/me", headers=as_user(AMY)).json()
    assert me["workforms"][0]["status"] == "submitted"
    assert me["workforms"][0]["total_hours"] == 0


def test_resubmit_updates_the_record_and_clears_removed_departments(
    client: TestClient, amy, airtable
):
    _add(client, department="Music", hours=1, description="Filing")
    promotions_id = _add(client).json()["id"]
    client.post(f"/api/workforms/me/{_month_path()}/submit", headers=as_user(AMY))

    client.delete(
        f"/api/workforms/me/{_month_path()}/entries/{promotions_id}", headers=as_user(AMY)
    )
    pending = client.get(f"/api/workforms/me/{_month_path()}", headers=as_user(AMY)).json()
    assert pending["has_unsent_changes"] is True

    response = client.post(
        f"/api/workforms/me/{_month_path()}/submit", headers=as_user(AMY)
    )
    assert response.status_code == 200
    (record,) = airtable.records.values()
    assert "Promotions : Hours" not in record["fields"]
    assert record["fields"]["Music : Hours"] == 1
    assert response.json()["has_unsent_changes"] is False


def test_submit_updates_a_hand_made_record(client: TestClient, amy, airtable):
    existing = airtable.add({"Name": [AMY_ID], "Month": _this_month().isoformat()})
    _add(client)
    client.post(f"/api/workforms/me/{_month_path()}/submit", headers=as_user(AMY))
    assert list(airtable.records) == [existing["id"]]
    assert airtable.records[existing["id"]]["fields"]["Promotions : Hours"] == 2


def test_locked_once_a_department_decides(client: TestClient, amy, airtable):
    _add(client)
    client.post(f"/api/workforms/me/{_month_path()}/submit", headers=as_user(AMY))
    (record,) = airtable.records.values()
    # A decision made by hand in Airtable, not yet in the local copy
    record["fields"]["Promotions : Approved"] = ["Approved"]

    response = client.post(
        f"/api/workforms/me/{_month_path()}/submit", headers=as_user(AMY)
    )
    assert response.status_code == 409
    assert _add(client).status_code == 409
    workform = client.get(f"/api/workforms/me/{_month_path()}", headers=as_user(AMY)).json()
    assert workform["status"] == "locked"
    assert workform["results"]["Promotions"]["decision"] == "Approved"


def test_missing_department_column_is_reported(client: TestClient, db, amy, airtable):
    airtable.columns -= {"Special Events : Hours"}
    _add(client, department="Special Events")
    response = client.post(
        f"/api/workforms/me/{_month_path()}/submit", headers=as_user(AMY)
    )
    assert response.status_code == 502
    assert "Special Events : Hours" in response.json()["detail"]
    assert db.query(Workform).one().airtable_record_id is None


def test_submit_needs_an_airtable_record_id(client: TestClient, db, departments, airtable):
    make_staff(db, "new@example.com", "New", None)
    response = client.post(
        f"/api/workforms/me/{_month_path()}/submit", headers=as_user("new@example.com")
    )
    assert response.status_code == 422


def test_late_submission_of_last_month(client: TestClient, amy, airtable):
    last = previous_month(_this_month())
    # Created a second after the deadline
    airtable.created_time = (deadline(last) + timedelta(seconds=1)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    response = client.post(
        f"/api/workforms/me/{format_month(last)}/submit", headers=as_user(AMY)
    )
    assert response.status_code == 200
    assert response.json()["is_late"] is True


def test_history_lists_past_workforms(client: TestClient, amy, airtable, db):
    old = previous_month(previous_month(_this_month()))
    airtable.add({
        "Name": [AMY_ID],
        "Month": old.isoformat(),
        "Promotions : Hours": 4,
        "Promotions : Description": "(4h): Tabling",
        "Promotions : Approved": ["Denied"],
        "Music : Hours": 1,
        "Music : Approved": ["Approved"],
    })
    asyncio.run(refresh_all(db))
    me = client.get("/api/workforms/me", headers=as_user(AMY)).json()
    assert me["open_months"] == [_month_path(), format_month(previous_month(_this_month()))]
    past = next(w for w in me["workforms"] if w["month"] == format_month(old))
    assert past["status"] == "locked"
    assert past["is_open"] is False
    assert past["total_hours"] == 5
    assert past["results"]["Promotions"]["decision"] == "Denied"
    assert past["results"]["Music"]["decision"] == "Approved"


def test_preferences(client: TestClient, amy):
    response = client.get("/api/workforms/preferences", headers=as_user(AMY))
    assert response.json() == {
        "reminder_emails_enabled": True,
        "review_emails_enabled": True,
        "is_department_head": False,
    }
    response = client.put(
        "/api/workforms/preferences",
        json={"reminder_emails_enabled": False, "review_emails_enabled": True},
        headers=as_user(AMY),
    )
    assert response.json()["reminder_emails_enabled"] is False


def test_site_admins_can_view_someones_workforms(client: TestClient, amy, airtable, db):
    make_staff(
        db,
        "boss@example.com",
        "Boss",
        "recBOSS0000000000",
        statuses=("Active", "Paid Staff"),
    )
    client.post(
        f"/api/workforms/me/{_month_path()}/entries",
        json={"department": "Promotions", "hours": 2, "description": "Tabling"},
        headers=as_user(AMY),
    )
    history = client.get(
        f"/api/workforms/staff/{amy.id}", headers=as_user("boss@example.com")
    )
    assert history.status_code == 200
    assert history.json()["staff_name"] == "Amy Adams"
    month = client.get(
        f"/api/workforms/staff/{amy.id}/{_month_path()}",
        headers=as_user("boss@example.com"),
    ).json()
    assert month["staff_name"] == "Amy Adams"
    assert [e["description"] for e in month["entries"]] == ["Tabling"]


def test_only_site_admins_can_view_someones_workforms(client: TestClient, amy, db):
    make_staff(db, "bob@example.com", "Bob", "recBOB00000000000")
    for path in (
        f"/api/workforms/staff/{amy.id}",
        f"/api/workforms/staff/{amy.id}/{_month_path()}",
    ):
        assert client.get(path, headers=as_user("bob@example.com")).status_code == 403


def test_monthly_hours_for_the_directory(client: TestClient, amy, airtable, db):
    from app.workforms.services.summary import monthly_hours

    old = previous_month(previous_month(_this_month()))
    airtable.add({
        "Name": [AMY_ID],
        "Month": old.isoformat(),
        "Promotions : Hours": 4,
        "Promotions : Approved": ["Approved"],
        "Music : Hours": 2,
    })
    asyncio.run(refresh_all(db))
    client.post(
        f"/api/workforms/me/{_month_path()}/entries",
        json={"department": "Promotions", "hours": 1.5, "description": "Tabling"},
        headers=as_user(AMY),
    )
    hours = monthly_hours(db, amy, [_this_month(), old])
    assert hours[_this_month()].status == "draft"
    assert hours[_this_month()].reported_hours == 1.5
    assert hours[old].status == "locked"
    assert hours[old].reported_hours == 6
    assert [(d.department, d.hours, d.decision) for d in hours[old].departments] == [
        ("Music", 2, None),
        ("Promotions", 4, "Approved"),
    ]
