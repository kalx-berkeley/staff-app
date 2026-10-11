"""Fixtures for KALX Workforms tests: a fake Airtable workforms table and staff."""

import itertools
import re
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.workform_department import DepartmentHead, WorkformDepartment
from app.workforms.services import airtable_client, review_service

DEPARTMENTS = ("Music", "Operations", "Promotions", "Special Events")


class FakeAirtable:
    """An in-memory stand-in for the Airtable workforms table."""

    def __init__(self, departments=DEPARTMENTS):
        self.records: dict[str, dict] = {}
        self.columns = {"Name", "Month", "Created Time"} | {
            f"{d} : {kind}"
            for d in departments
            for kind in ("Hours", "Description", "Approved")
        }
        self.created_time = None
        self.calls: list[tuple] = []
        self._ids = itertools.count(1)

    def _check(self, fields):
        for name in fields:
            if name not in self.columns:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Airtable couldn't save the workform: Unknown field name:"
                        f' "{name}"'
                    ),
                )

    def add(self, fields, created_time="2026-10-02T17:00:00.000Z") -> dict:
        """Put a record in the table directly, as if made by hand."""
        record_id = f"recWF{next(self._ids):012d}"
        record = {
            "id": record_id,
            "createdTime": created_time,
            "fields": {**fields, "Created Time": created_time},
        }
        self.records[record_id] = record
        return record

    async def list_records(self, formula=None):
        self.calls.append(("list", formula))
        records = list(self.records.values())
        if formula:
            month = re.search(r"'(\d{4}-\d{2})-\d{2}'", formula).group(1)
            records = [r for r in records if r["fields"].get("Month", "")[:7] == month]
        return [dict(r, fields=dict(r["fields"])) for r in records]

    async def get_record(self, record_id):
        self.calls.append(("get", record_id))
        record = self.records.get(record_id)
        return dict(record, fields=dict(record["fields"])) if record else None

    async def create_record(self, fields):
        self.calls.append(("create", fields))
        self._check(fields)
        created = self.created_time or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        return dict(self.add({k: v for k, v in fields.items() if v is not None}, created))

    async def update_record(self, record_id, fields):
        self.calls.append(("update", record_id, fields))
        self._check(fields)
        record = self.records[record_id]
        for name, value in fields.items():
            if value is None:
                record["fields"].pop(name, None)
            else:
                record["fields"][name] = value
        return dict(record, fields=dict(record["fields"]))


@pytest.fixture
def airtable(monkeypatch):
    fake = FakeAirtable()
    for name in ("list_records", "get_record", "create_record", "update_record"):
        monkeypatch.setattr(airtable_client, name, getattr(fake, name))
    review_service._reset_for_testing()
    return fake


@pytest.fixture
def departments(db: Session):
    for name in DEPARTMENTS:
        db.add(WorkformDepartment(name=name))
    db.commit()
    return DEPARTMENTS


def make_staff(
    db: Session,
    email: str,
    name: str,
    record_id: str | None,
    statuses=("Active",),
    departments=(),
    heads=(),
    **columns,
) -> Staff:
    """A staff member, optionally heading *heads* departments."""
    staff = Staff(
        email=email,
        name=name,
        phone="510-555-0100",
        airtable_record_id=record_id,
        **columns,
    )
    db.add(staff)
    db.flush()
    for status in statuses:
        db.add(StaffStatus(staff_id=staff.id, status=status))
    for department in departments:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    for department in heads:
        db.add(DepartmentHead(department=department, staff_airtable_record_id=record_id))
    db.commit()
    return staff


def as_user(email: str) -> dict:
    return {"X-Forwarded-User": email}
