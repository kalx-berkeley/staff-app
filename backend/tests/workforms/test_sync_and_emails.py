"""Tests for the department heads sync, dropping drafts, and workform emails."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.job_log import JobLog
from app.models.workform import Workform, WorkformEntry
from app.models.workform_department import DepartmentHead, WorkformDepartment
from app.models.workform_preferences import WorkformPreferences
from app.common.services.user_service import UserService
from app.workforms.services import notifications
from app.workforms.services.departments import drop_inactive_drafts, sync_department_heads
from tests.workforms.conftest import make_staff


async def test_sync_department_heads_resolves_departments(db: Session):
    db.add(WorkformDepartment(name="Old"))
    db.commit()
    heads_table = [
        {
            "id": "recDH1",
            "fields": {
                "Department": ["recDEPMUSIC"],
                "Department Heads": ["recMEL", "recMO"],
            },
        },
        {"id": "recDH2", "fields": {"Department": ["recDEPSPORTS"]}},
    ]
    with (
        patch.object(
            UserService, "fetch_airtable_records", AsyncMock(return_value=heads_table)
        ),
        patch.object(
            UserService,
            "fetch_department_names",
            AsyncMock(return_value={"recDEPMUSIC": "Music", "recDEPSPORTS": "Sports"}),
        ),
    ):
        result = {"errors": []}
        await sync_department_heads(db, result)
    assert result["errors"] == []
    assert [
        d.name for d in db.query(WorkformDepartment).order_by(WorkformDepartment.name)
    ] == [
        "Music",
        "Sports",
    ]
    assert {
        (h.department, h.staff_airtable_record_id) for h in db.query(DepartmentHead)
    } == {
        ("Music", "recMEL"),
        ("Music", "recMO"),
    }


async def test_sync_department_heads_keeps_copy_on_failure(db: Session):
    from fastapi import HTTPException

    db.add(WorkformDepartment(name="Music"))
    db.commit()
    with patch.object(
        UserService,
        "fetch_airtable_records",
        AsyncMock(side_effect=HTTPException(status_code=503, detail="down")),
    ):
        result = {"errors": []}
        await sync_department_heads(db, result)
    assert result["errors"]
    assert db.query(WorkformDepartment).count() == 1


def test_drop_inactive_drafts(db: Session):
    active = make_staff(db, "a@example.com", "A", "recA")
    gone = make_staff(db, "g@example.com", "G", "recG", statuses=("Alumni",))
    month = date(2026, 10, 1)
    for staff in (active, gone):
        workform = Workform(staff_id=staff.id, month=month)
        db.add(workform)
        db.flush()
        db.add(
            WorkformEntry(
                workform_id=workform.id, department="Music", hours=1, description="x"
            )
        )
    db.add(
        Workform(
            staff_id=gone.id, month=date(2026, 9, 1), airtable_record_id="recSUBMITTED"
        )
    )
    db.commit()

    assert drop_inactive_drafts(db) == 1
    remaining = {(w.staff_id, w.month) for w in db.query(Workform)}
    assert remaining == {(active.id, month), (gone.id, date(2026, 9, 1))}
    assert db.query(WorkformEntry).count() == 1


async def test_staff_sync_runs_the_workforms_hook(db: Session):
    from app.common.services import user_service
    from app.workforms.services.departments import after_staff_sync

    assert after_staff_sync in user_service._post_sync_hooks
    failing = AsyncMock(side_effect=RuntimeError("boom"))
    failing.__qualname__ = "failing"
    with (
        patch.object(user_service, "_post_sync_hooks", [failing]),
        patch.object(UserService, "fetch_airtable_records", AsyncMock(return_value=[])),
    ):
        result = await UserService.sync_from_airtable(db)
    failing.assert_awaited_once()
    assert any("boom" in e for e in result["errors"])


# --- emails ---


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 10, 31), date(2026, 10, 1)),
        (date(2026, 11, 3), date(2026, 10, 1)),
        (date(2026, 2, 28), date(2026, 2, 1)),
        (date(2026, 10, 30), None),
        (date(2026, 11, 4), None),
    ],
)
def test_reminder_month(today, expected):
    assert notifications.reminder_month(today) == expected


@pytest.fixture
def sent(monkeypatch):
    emails = []
    monkeypatch.setattr(notifications, "send_email", lambda **kwargs: emails.append(kwargs))
    return emails


async def test_reminders_go_to_staff_who_havent_submitted(db: Session, airtable, sent):
    draft = make_staff(db, "draft@example.com", "Draft", "recDRAFT")
    make_staff(db, "none@example.com", "None", "recNONE")
    make_staff(db, "zero@example.com", "Zero", "recZERO")
    make_staff(db, "head@example.com", "Head", "recHEAD", heads=("Music",))
    make_staff(db, "gone@example.com", "Gone", "recGONE", statuses=("Alumni",))
    quiet = make_staff(db, "quiet@example.com", "Quiet", "recQUIET")
    db.add(WorkformPreferences(staff_id=quiet.id, reminder_emails_enabled=False))
    db.add(Workform(staff_id=draft.id, month=date(2026, 10, 1)))
    db.commit()
    airtable.add({"Name": ["recZERO"], "Month": "2026-10-01"})

    assert await notifications.send_reminders(db, today=date(2026, 10, 31)) == 2
    assert sorted(e["to_email"] for e in sent) == ["draft@example.com", "none@example.com"]
    assert "October 2026" in sent[0]["subject"]
    assert "November 5" in sent[0]["body_text"]
    assert "/workforms/month/2026-10" in sent[0]["body_text"]
    assert db.query(JobLog).filter(JobLog.job_id == "workform_reminders").count() == 1


async def test_no_reminders_on_other_days(db: Session, airtable, sent):
    make_staff(db, "none@example.com", "None", "recNONE")
    assert await notifications.send_reminders(db, today=date(2026, 10, 15)) == 0
    assert sent == []


async def test_review_emails_on_the_6th(db: Session, airtable, sent, departments):
    make_staff(db, "mel@example.com", "Mel", "recMEL", heads=("Music",))
    make_staff(db, "ola@example.com", "Ola", "recOLA", heads=("Operations",))
    make_staff(db, "pat@example.com", "Pat", "recPAT", heads=("Promotions",))
    make_staff(db, "sam@example.com", "Sam", "recSAM")
    airtable.add({
        "Name": ["recSAM"],
        "Month": "2026-10-01",
        "Music : Hours": 2,
        "Special Events : Hours": 1,
        "Promotions : Hours": 1,
        "Promotions : Approved": ["Approved"],
    })
    # Mel's own Music hours have no other Music head, so they're Ola's
    airtable.add({"Name": ["recMEL"], "Month": "2026-10-01", "Music : Hours": 3})

    assert await notifications.send_review_emails(db, today=date(2026, 11, 5)) == 0
    assert await notifications.send_review_emails(db, today=date(2026, 11, 6)) == 2
    by_email = {e["to_email"]: e for e in sent}
    assert set(by_email) == {"mel@example.com", "ola@example.com"}
    assert by_email["mel@example.com"]["subject"].startswith("1 KALX workform submission")
    # Special Events (no head) and Mel's own Music hours
    assert by_email["ola@example.com"]["subject"].startswith("2 KALX workform submissions")


async def test_scheduled_emails_are_off_unless_enabled(monkeypatch):
    from app import scheduler
    from app.config import settings

    reminders = AsyncMock()
    monkeypatch.setattr(notifications, "send_reminders", reminders)
    monkeypatch.setattr(notifications, "send_review_emails", AsyncMock())
    monkeypatch.setattr(settings, "workforms_emails_enabled", False)
    await scheduler.send_workform_emails()
    reminders.assert_not_awaited()
