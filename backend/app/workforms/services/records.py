"""The local copy of the Airtable workforms table, and converting to and from it."""

import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.workform_airtable_record import WorkformAirtableRecord
from app.workforms.services import airtable_client

logger = logging.getLogger(__name__)

NAME_FIELD = "Name"
MONTH_FIELD = "Month"
CREATED_TIME_FIELD = "Created Time"
APPROVED = "Approved"
DENIED = "Denied"
DECISIONS = (APPROVED, DENIED)

_DEPARTMENT_FIELD_RE = re.compile(
    r"^(?P<department>.+?) : (?P<kind>Hours|Description|Approved)$"
)


def hours_field(department: str) -> str:
    return f"{department} : Hours"


def description_field(department: str) -> str:
    return f"{department} : Description"


def approved_field(department: str) -> str:
    return f"{department} : Approved"


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse an Airtable timestamp ("2026-10-11T18:00:00.000Z") as naive UTC."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _parse_month(value: Any) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10]).replace(day=1)
    except ValueError:
        return None


def _parse_decision(value: Any) -> Optional[str]:
    """
    Read an "Approved" multi-select. "Denied" wins if someone picked both,
    so hours are never counted by mistake.
    """
    values = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    if DENIED in values:
        return DENIED
    if APPROVED in values:
        return APPROVED
    return None


def parse_departments(fields: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """The departments of an Airtable workform record that have any value."""
    departments: Dict[str, Dict[str, Any]] = {}
    for name, value in fields.items():
        match = _DEPARTMENT_FIELD_RE.match(name)
        if not match:
            continue
        block = departments.setdefault(
            match["department"], {"hours": None, "description": None, "approved": None}
        )
        kind = match["kind"]
        if kind == "Hours" and isinstance(value, (int, float)):
            block["hours"] = float(value)
        elif kind == "Description" and isinstance(value, str) and value.strip():
            block["description"] = value
        elif kind == "Approved":
            block["approved"] = _parse_decision(value)
    return {
        department: block
        for department, block in departments.items()
        if any(v is not None for v in block.values())
    }


def has_hours(block: Optional[Dict[str, Any]]) -> bool:
    """Whether a department block reports work (hours or a description)."""
    return bool(block) and (
        block.get("hours") is not None or bool(block.get("description"))
    )


def is_locked(record: Optional[WorkformAirtableRecord]) -> bool:
    """A submitted workform is locked once any department has a decision."""
    return bool(record) and any(
        block.get("approved") for block in (record.departments or {}).values()
    )


def upsert_record(db: Session, record: Dict[str, Any]) -> WorkformAirtableRecord:
    """Store an Airtable record in the local copy. The caller commits."""
    fields = record.get("fields", {})
    names = fields.get(NAME_FIELD)
    staff_record_id = names[0] if isinstance(names, list) and names else None
    created_time = _parse_datetime(fields.get(CREATED_TIME_FIELD)) or _parse_datetime(
        record.get("createdTime")
    )
    row = (
        db.query(WorkformAirtableRecord)
        .filter(WorkformAirtableRecord.airtable_record_id == record["id"])
        .first()
    )
    if row is None:
        row = WorkformAirtableRecord(airtable_record_id=record["id"])
        db.add(row)
    row.staff_airtable_record_id = staff_record_id
    row.month = _parse_month(fields.get(MONTH_FIELD))
    row.created_time = created_time
    row.departments = parse_departments(fields)
    row.refreshed_at = datetime.now(timezone.utc)
    return row


def _replace(db: Session, records: Iterable[Dict[str, Any]], stale_query) -> int:
    seen = set()
    for record in records:
        upsert_record(db, record)
        seen.add(record["id"])
    removed = 0
    for row in stale_query:
        if row.airtable_record_id not in seen:
            db.delete(row)
            removed += 1
    db.commit()
    return removed


async def refresh_all(db: Session) -> int:
    """
    Copy the whole workforms table, removing records deleted in Airtable.

    :returns: The number of records copied
    :raises HTTPException: If Airtable can't be read
    """
    records = await airtable_client.list_records()
    _replace(db, records, db.query(WorkformAirtableRecord).all())
    logger.info("Refreshed %d workform records from Airtable", len(records))
    return len(records)


async def refresh_month(db: Session, month: date) -> None:
    """
    Copy the workforms table's records for one month.

    :raises HTTPException: If Airtable can't be read
    """
    formula = f"IS_SAME({{{MONTH_FIELD}}}, '{month.isoformat()}', 'month')"
    records = await airtable_client.list_records(formula)
    # Records whose Month was changed to another month in Airtable are
    # dropped here and picked up again by that month's or the full refresh.
    _replace(
        db,
        records,
        db.query(WorkformAirtableRecord)
        .filter(WorkformAirtableRecord.month == month)
        .all(),
    )


async def refresh_one(db: Session, record_id: str) -> Optional[WorkformAirtableRecord]:
    """
    Copy one workforms record, or remove it locally if it's gone from Airtable.

    :raises HTTPException: If Airtable can't be read
    """
    record = await airtable_client.get_record(record_id)
    if record is None:
        db.query(WorkformAirtableRecord).filter(
            WorkformAirtableRecord.airtable_record_id == record_id
        ).delete()
        db.commit()
        return None
    row = upsert_record(db, record)
    db.commit()
    return row


def record_for(
    db: Session, staff_record_id: Optional[str], month: date
) -> Optional[WorkformAirtableRecord]:
    """The local copy of a staff member's Airtable workform for *month*."""
    if not staff_record_id:
        return None
    return (
        db.query(WorkformAirtableRecord)
        .filter(
            WorkformAirtableRecord.staff_airtable_record_id == staff_record_id,
            WorkformAirtableRecord.month == month,
        )
        .order_by(WorkformAirtableRecord.created_time, WorkformAirtableRecord.id)
        .first()
    )
