"""A staff member's workforms: entries, combining them, and submitting to Airtable."""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.common.areas import WORKFORMS_AREA
from app.common.services.audit_service import log_event
from app.models.staff import Staff
from app.models.workform import Workform, WorkformEntry
from app.workforms.services import airtable_client, records
from app.workforms.services.departments import departments
from app.workforms.services.months import format_month, last_day_of_month, open_months

HOURS_STEP = 0.25


def format_hours(hours: float) -> str:
    """Hours without trailing zeros: 2, 1.5, 0.25."""
    return f"{hours:.2f}".rstrip("0").rstrip(".")


def get_workform(db: Session, staff: Staff, month: date) -> Optional[Workform]:
    return (
        db.query(Workform)
        .filter(Workform.staff_id == staff.id, Workform.month == month)
        .first()
    )


def ensure_open(month: date, today: Optional[date] = None) -> None:
    """:raises HTTPException: 400 if *month* can't be added to or submitted."""
    if month not in open_months(today):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"The {format_month(month)} workform is closed. Only this month's and"
                " last month's workforms can be changed or submitted."
            ),
        )


def ensure_unlocked(db: Session, staff: Staff, month: date) -> None:
    """:raises HTTPException: 409 if a department has already decided on the workform."""
    if records.is_locked(records.record_for(db, staff.airtable_record_id, month)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A department head has already reviewed this workform, so it can't be"
                " changed."
            ),
        )


def validate_entry(
    db: Session,
    month: date,
    department: str,
    hours: float,
    description: str,
    work_date: Optional[date],
) -> str:
    """
    Check an entry's values.

    :returns: The description, stripped
    :raises HTTPException: 422 describing the first problem
    """
    problem = None
    description = (description or "").strip()
    if department not in departments(db):
        problem = f"Unknown department {department!r}"
    elif hours <= 0 or abs(hours / HOURS_STEP - round(hours / HOURS_STEP)) > 1e-9:
        problem = "Hours must be more than 0, in quarter hours (for example 1.25)"
    elif not description:
        problem = "Describe the work you did"
    elif work_date is not None and not (month <= work_date <= last_day_of_month(month)):
        problem = f"The date must be in {month:%B %Y}"
    if problem:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=problem
        )
    return description


def _sorted_entries(entries: List[WorkformEntry]) -> List[WorkformEntry]:
    """Dated entries by date, then undated ones, each in the order they were added."""
    return sorted(
        entries,
        key=lambda e: (
            e.work_date is None,
            e.work_date or date.min,
            e.created_at,
            e.id or 0,
        ),
    )


def combine(entries: List[WorkformEntry]) -> Dict[str, Dict[str, Any]]:
    """
    Combine entries into one block per department, as submitted to Airtable.

    The description has one line per entry, dated entries first by date:
    "10-03 (2h): Ran the Halloween table" or "(3h): Inventory".

    :returns: {department: {"hours", "description", "entries"}}
    """
    blocks: Dict[str, Dict[str, Any]] = {}
    for entry in _sorted_entries(entries):
        block = blocks.setdefault(
            entry.department, {"hours": 0.0, "lines": [], "entries": []}
        )
        block["hours"] += entry.hours
        prefix = f"{entry.work_date:%m-%d} " if entry.work_date else ""
        block["lines"].append(
            f"{prefix}({format_hours(entry.hours)}h): {entry.description}"
        )
        block["entries"].append({
            "hours": entry.hours,
            "description": entry.description,
            "work_date": entry.work_date.isoformat() if entry.work_date else None,
        })
    return {
        department: {
            "hours": block["hours"],
            "description": "\n".join(block["lines"]),
            "entries": block["entries"],
        }
        for department, block in sorted(blocks.items())
    }


def has_unsent_changes(workform: Optional[Workform]) -> bool:
    """Whether a submitted workform's entries differ from what was submitted."""
    if workform is None or workform.airtable_record_id is None:
        return False
    current = {
        d: {"hours": b["hours"], "description": b["description"]}
        for d, b in combine(workform.entries).items()
    }
    submitted = {
        d: {"hours": b["hours"], "description": b["description"]}
        for d, b in (workform.submitted_blocks or {}).items()
    }
    return current != submitted


def add_entry(
    db: Session,
    staff: Staff,
    month: date,
    department: str,
    hours: float,
    description: str,
    work_date: Optional[date],
) -> WorkformEntry:
    ensure_open(month)
    ensure_unlocked(db, staff, month)
    description = validate_entry(db, month, department, hours, description, work_date)
    workform = get_workform(db, staff, month)
    if workform is None:
        workform = Workform(staff_id=staff.id, month=month)
        db.add(workform)
        db.flush()
    entry = WorkformEntry(
        workform_id=workform.id,
        department=department,
        hours=hours,
        description=description,
        work_date=work_date,
    )
    db.add(entry)
    workform.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    return entry


def _get_entry(db: Session, staff: Staff, month: date, entry_id: int) -> WorkformEntry:
    entry = (
        db.query(WorkformEntry)
        .join(Workform)
        .filter(
            WorkformEntry.id == entry_id,
            Workform.staff_id == staff.id,
            Workform.month == month,
        )
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


def update_entry(
    db: Session,
    staff: Staff,
    month: date,
    entry_id: int,
    department: str,
    hours: float,
    description: str,
    work_date: Optional[date],
) -> WorkformEntry:
    ensure_open(month)
    ensure_unlocked(db, staff, month)
    entry = _get_entry(db, staff, month, entry_id)
    entry.description = validate_entry(db, month, department, hours, description, work_date)
    entry.department = department
    entry.hours = hours
    entry.work_date = work_date
    entry.workform.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    return entry


def delete_entry(db: Session, staff: Staff, month: date, entry_id: int) -> None:
    ensure_open(month)
    ensure_unlocked(db, staff, month)
    entry = _get_entry(db, staff, month, entry_id)
    entry.workform.updated_at = datetime.now(timezone.utc)
    db.delete(entry)
    db.commit()


async def submit(db: Session, staff: Staff, month: date) -> Workform:
    """
    Submit (or resubmit) a staff member's workform for *month* to Airtable.

    Updates the person's existing record for the month if there is one, even
    one made by hand, and creates one otherwise. A workform with no entries
    is a 0-hour workform: just Name and Month. Nothing changes locally if
    Airtable can't be written.

    :raises HTTPException: 400 if the month is closed, 409 if a department
        has already decided, 422 if the staff member has no Airtable record,
        502/503 if Airtable fails
    """
    ensure_open(month)
    if not staff.airtable_record_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Your staff record hasn't been linked to Airtable yet, so your workform"
                " can't be submitted. Please contact the webmaster."
            ),
        )

    # Check against Airtable itself, not just the local copy, so a decision
    # made moments ago (in the app or by hand) still locks the workform.
    await records.refresh_month(db, month)
    existing = records.record_for(db, staff.airtable_record_id, month)
    if existing is not None:
        existing = await records.refresh_one(db, existing.airtable_record_id)
    if records.is_locked(existing):
        ensure_unlocked(db, staff, month)

    workform = get_workform(db, staff, month)
    if workform is None:
        workform = Workform(staff_id=staff.id, month=month)
        db.add(workform)
        db.flush()
    blocks = combine(workform.entries)

    fields: Dict[str, Any] = {
        records.NAME_FIELD: [staff.airtable_record_id],
        records.MONTH_FIELD: month.isoformat(),
    }
    for department, block in blocks.items():
        fields[records.hours_field(department)] = block["hours"]
        fields[records.description_field(department)] = block["description"]
    if existing is not None:
        # Clear departments that no longer have entries. Only ones that have
        # a value, since a department may not have all its columns yet.
        for department in existing.departments or {}:
            if department not in blocks:
                fields[records.hours_field(department)] = None
                fields[records.description_field(department)] = None
        saved = await airtable_client.update_record(existing.airtable_record_id, fields)
    else:
        saved = await airtable_client.create_record(fields)

    records.upsert_record(db, saved)
    now = datetime.now(timezone.utc)
    resubmitted = workform.airtable_record_id is not None
    workform.airtable_record_id = saved["id"]
    workform.first_submitted_at = workform.first_submitted_at or now
    workform.last_submitted_at = now
    workform.submitted_blocks = blocks
    workform.loa_start_at_submit = staff.loa_start
    workform.loa_end_at_submit = staff.loa_end
    db.commit()
    db.refresh(workform)

    log_event(
        db,
        event_type="workform_resubmitted" if resubmitted else "workform_submitted",
        area=WORKFORMS_AREA,
        actor_email=staff.email,
        actor_role="staff",
        entity_type="workform",
        entity_id=workform.id,
        details={
            "month": format_month(month),
            "airtable_record_id": saved["id"],
            "hours": {d: b["hours"] for d, b in blocks.items()},
        },
    )
    return workform
