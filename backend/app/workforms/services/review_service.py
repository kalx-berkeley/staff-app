"""Department heads reviewing the hours staff submitted for their departments."""

import re
import time
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth import is_current_staff
from app.common.areas import WORKFORMS_AREA
from app.common.services import staff_airtable
from app.common.services.audit_service import log_event
from app.common.services.user_service import UserService
from app.config import settings
from app.models.staff import Staff
from app.models.workform import Workform
from app.models.workform_airtable_record import WorkformAirtableRecord
from app.workforms.services import airtable_client, records
from app.workforms.services.departments import (
    can_review,
    responsible_reviewers,
    reviewable_departments,
)
from app.workforms.services.loa import entry_flag, month_overlaps
from app.workforms.services.months import (
    format_month,
    is_late,
    open_months,
    previous_month,
)

# The most months the department people list looks back
MAX_PEOPLE_MONTHS = 12

# The staff table's field linking to the departments its staff work in
STAFF_DEPARTMENT_FIELD = "Department"

_AIRTABLE_RECORD_ID_RE = re.compile(r"^rec[A-Za-z0-9]{14}$")

# A reviewer opening a month refreshes it from Airtable at most this often
REFRESH_INTERVAL_SECONDS = 60
_last_refreshed: Dict[date, float] = {}


def _reset_for_testing() -> None:
    _last_refreshed.clear()


async def refresh_month_if_stale(db: Session, month: date) -> None:
    now = time.monotonic()
    last = _last_refreshed.get(month)
    if last is not None and now - last < REFRESH_INTERVAL_SECONDS:
        return
    await records.refresh_month(db, month)
    _last_refreshed[month] = now


def _staff_by_record_id(db: Session, record_ids: set[str]) -> Dict[str, Staff]:
    if not record_ids:
        return {}
    return {
        s.airtable_record_id: s
        for s in db.query(Staff).filter(Staff.airtable_record_id.in_(record_ids))
    }


def _workform_for(db: Session, record: WorkformAirtableRecord) -> Optional[Workform]:
    return (
        db.query(Workform)
        .filter(Workform.airtable_record_id == record.airtable_record_id)
        .first()
    )


def _review_item(
    db: Session,
    record: WorkformAirtableRecord,
    department: str,
    staff: Optional[Staff],
    workform: Optional[Workform],
) -> Dict[str, Any]:
    block = record.departments[department]
    submitted = (workform.submitted_blocks or {}).get(department) if workform else None
    if workform is not None:
        loa_start, loa_end = workform.loa_start_at_submit, workform.loa_end_at_submit
    else:
        loa_start, loa_end = (staff.loa_start, staff.loa_end) if staff else (None, None)

    month = record.month
    entries = []
    for entry in (submitted or {}).get("entries", []):
        work_date = date.fromisoformat(entry["work_date"]) if entry["work_date"] else None
        entries.append({
            **entry,
            "loa_flag": entry_flag(work_date, month, loa_start, loa_end) if month else None,
        })
    return {
        "airtable_record_id": record.airtable_record_id,
        "staff_id": staff.id if staff else None,
        "staff_name": staff.name if staff else "Unknown staff member",
        "hours": block.get("hours"),
        "description": block.get("description"),
        "decision": block.get("approved"),
        "entries": entries,
        "edited_in_airtable": _edited_in_airtable(submitted, block),
        "submitted_at": record.created_time,
        "is_late": (
            bool(month and record.created_time) and is_late(month, record.created_time)
        ),
        "loa_start": loa_start,
        "loa_end": loa_end,
        "loa_overlaps_month": bool(month) and month_overlaps(month, loa_start, loa_end),
    }


def _edited_in_airtable(submitted: Optional[Dict[str, Any]], block: Dict[str, Any]) -> bool:
    """
    Whether Airtable's values for a block differ from what the app submitted.

    Airtable is the source of truth, so a hand edit there is shown as
    Airtable's values with a note, alongside the entries originally submitted.
    A record the app never submitted counts as edited by hand.
    """
    if submitted is None:
        return True
    hours = block.get("hours")
    if hours is None or abs(hours - submitted["hours"]) > 1e-6:
        return True
    return (block.get("description") or "").strip() != submitted["description"].strip()


def _records_with_hours(
    db: Session, month: date, department: str
) -> List[WorkformAirtableRecord]:
    return [
        r
        for r in db.query(WorkformAirtableRecord).filter(
            WorkformAirtableRecord.month == month
        )
        if records.has_hours((r.departments or {}).get(department))
    ]


def queue(db: Session, reviewer: Staff, month: date, department: str) -> Dict[str, Any]:
    """
    The submissions with hours in *department* for *month* that *reviewer*
    may review, with progress counts.

    :raises HTTPException: 403 if *reviewer* can't review *department*
    """
    own, fallback = reviewable_departments(db, reviewer)
    if department not in own and department not in fallback:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You can't review {department} workforms",
        )
    candidates = [
        r
        for r in _records_with_hours(db, month, department)
        if can_review(db, reviewer, department, r.staff_airtable_record_id)
    ]
    people = _staff_by_record_id(
        db, {r.staff_airtable_record_id for r in candidates if r.staff_airtable_record_id}
    )
    items = [
        _review_item(
            db, r, department, people.get(r.staff_airtable_record_id), _workform_for(db, r)
        )
        for r in candidates
    ]
    items.sort(key=lambda i: i["staff_name"].lower())
    reviewed = sum(1 for i in items if i["decision"])
    return {
        "month": format_month(month),
        "department": department,
        "items": items,
        "total": len(items),
        "reviewed": reviewed,
        "remaining": len(items) - reviewed,
    }


def pending_counts(db: Session, reviewer: Staff, month: date) -> Dict[str, int]:
    """For each department *reviewer* can review, how many submissions await a decision."""
    own, fallback = reviewable_departments(db, reviewer)
    counts = {}
    for department in own + fallback:
        counts[department] = sum(
            1
            for r in _records_with_hours(db, month, department)
            if not r.departments[department].get("approved")
            and can_review(db, reviewer, department, r.staff_airtable_record_id)
        )
    return counts


def responsible_pending_count(db: Session, reviewer: Staff, month: date) -> int:
    """
    How many undecided submissions in *month* *reviewer* is expected to review.

    Counts their own departments' submissions, plus, for an Operations head,
    those with no other head to review them. Used for the review email.
    """
    if not reviewer.airtable_record_id:
        return 0
    count = 0
    for record in db.query(WorkformAirtableRecord).filter(
        WorkformAirtableRecord.month == month
    ):
        for department, block in (record.departments or {}).items():
            if (
                records.has_hours(block)
                and not block.get("approved")
                and reviewer.airtable_record_id
                in responsible_reviewers(db, department, record.staff_airtable_record_id)
            ):
                count += 1
    return count


def default_month(db: Session, reviewer: Staff) -> date:
    """
    The most recent month with a submission awaiting *reviewer*'s decision,
    or last month if there's none.
    """
    months = sorted(
        {m for (m,) in db.query(WorkformAirtableRecord.month).distinct() if m is not None},
        reverse=True,
    )
    for month in months:
        if any(pending_counts(db, reviewer, month).values()):
            return month
    return open_months()[1]


async def decide(
    db: Session,
    reviewer: Staff,
    airtable_record_id: str,
    department: str,
    decision: Optional[str],
) -> Dict[str, Any]:
    """
    Approve or deny a submission's hours in *department*, or clear the decision.

    :raises HTTPException: 404 if the submission or its hours in *department*
        are gone, 403 if *reviewer* can't review them, 502/503 if Airtable fails
    """
    if decision is not None and decision not in records.DECISIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Decision must be Approved, Denied or empty",
        )
    record = await records.refresh_one(db, airtable_record_id)
    if record is None or not records.has_hours((record.departments or {}).get(department)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"That workform has no {department} hours",
        )
    if not can_review(db, reviewer, department, record.staff_airtable_record_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You can't review this {department} workform",
        )

    before = record.departments[department].get("approved")
    saved = await airtable_client.update_record(
        airtable_record_id,
        {records.approved_field(department): [decision] if decision else None},
    )
    record = records.upsert_record(db, saved)
    db.commit()

    workform = _workform_for(db, record)
    subject = _staff_by_record_id(db, {record.staff_airtable_record_id} - {None})
    subject_staff = subject.get(record.staff_airtable_record_id)
    log_event(
        db,
        event_type="workform_decision",
        area=WORKFORMS_AREA,
        actor_email=reviewer.email,
        actor_role="department_head",
        entity_type="workform",
        entity_id=workform.id if workform else None,
        details={
            "airtable_record_id": airtable_record_id,
            "month": format_month(record.month) if record.month else None,
            "department": department,
            "staff_email": subject_staff.email if subject_staff else None,
            "before": before,
            "after": decision,
            "self_review": record.staff_airtable_record_id == reviewer.airtable_record_id,
        },
    )
    return _review_item(db, record, department, subject_staff, workform)


def _check_can_see_people(db: Session, reviewer: Staff, department: str) -> None:
    own, fallback = reviewable_departments(db, reviewer)
    if department not in own and department not in fallback:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You can't see who works in {department}",
        )


def _people_window(months: int) -> List[date]:
    """The last *months* months, oldest first, ending with last month."""
    window = [open_months()[1]]
    while len(window) < months:
        window.append(previous_month(window[-1]))
    window.reverse()
    return window


def _department_hours(
    db: Session, department: str, window: List[date]
) -> Dict[str, Dict[date, float]]:
    """
    Each staff record ID's hours in *department* in each month of *window*
    they reported any.
    """
    hours: Dict[str, Dict[date, float]] = {}
    for record in db.query(WorkformAirtableRecord).filter(
        WorkformAirtableRecord.month.in_(window)
    ):
        block = (record.departments or {}).get(department)
        if record.staff_airtable_record_id and records.has_hours(block):
            by_month = hours.setdefault(record.staff_airtable_record_id, {})
            by_month[record.month] = by_month.get(record.month, 0) + (
                block.get("hours") or 0
            )
    return hours


def _in_department(staff: Optional[Staff], department: str) -> bool:
    return staff is not None and any(d.department == department for d in staff.departments)


def department_people(
    db: Session, reviewer: Staff, department: str, months: int, min_months: int
) -> Dict[str, Any]:
    """
    The people who reported hours in *department* in at least *min_months*
    of the last *months* months, with their hours in each month.

    The months end with last month, since the current month is still going.

    :raises HTTPException: 403 if *reviewer* can't review *department*
    """
    _check_can_see_people(db, reviewer, department)
    window = _people_window(months)
    hours = _department_hours(db, department, window)

    people = _staff_by_record_id(db, set(hours))
    result = []
    for record_id, by_month in hours.items():
        if len(by_month) < min_months:
            continue
        staff = people.get(record_id)
        result.append({
            "staff_id": staff.id if staff else None,
            "staff_name": staff.name if staff else "Unknown staff member",
            "is_current_staff": is_current_staff(staff),
            "months_reported": len(by_month),
            "total_hours": sum(by_month.values()),
            "hours": {format_month(m): h for m, h in by_month.items()},
            "in_department": _in_department(staff, department),
        })
    result.sort(key=lambda p: p["staff_name"].lower())
    return {
        "department": department,
        "months": [format_month(m) for m in window],
        "min_months": min_months,
        "people": result,
        "can_add_to_department": settings.airtable_staff_edit_enabled,
    }


async def add_to_department(
    db: Session, reviewer: Staff, department: str, staff_ids: List[int]
) -> List[int]:
    """
    Add *department* to these staff members' Airtable "Department" field.

    Each must be current staff who reported hours in *department* in the
    last MAX_PEOPLE_MONTHS months, as the People page lists them. Those
    already in the department are left as they are.

    :returns: The IDs of the staff added, in name order.
    :raises HTTPException: 403 if adding isn't turned on or *reviewer* can't
        review *department*, 404 if a staff member doesn't exist, 422 if one
        can't be added, 502 if Airtable fails.
    """
    if not settings.airtable_staff_edit_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adding people to departments isn't available yet",
        )
    _check_can_see_people(db, reviewer, department)

    staff = db.query(Staff).filter(Staff.id.in_(set(staff_ids))).all()
    if len(staff) != len(set(staff_ids)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
        )
    reported = _department_hours(db, department, _people_window(MAX_PEOPLE_MONTHS))
    for member in staff:
        if (
            not is_current_staff(member)
            or not member.airtable_record_id
            or member.airtable_record_id not in reported
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"{member.name} can't be added to {department}: only current "
                    f"staff who reported {department} hours recently can be"
                ),
            )
    to_add = sorted(
        (m for m in staff if not _in_department(m, department)),
        key=lambda m: m.name.lower(),
    )
    if not to_add:
        return []

    names = await UserService.fetch_department_names()
    department_id = next((rid for rid, name in names.items() if name == department), None)
    if department_id is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"Airtable's {settings.airtable_departments_table_name} table has no"
                f" {department}"
            ),
        )

    added = []
    for member in to_add:
        record = await staff_airtable.get_staff_record(member.airtable_record_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Airtable has no staff record for {member.name}",
            )
        linked = record["fields"].get(STAFF_DEPARTMENT_FIELD) or []
        if not isinstance(linked, list) or not all(
            isinstance(d, str) and _AIRTABLE_RECORD_ID_RE.match(d) for d in linked
        ):
            # Writing names back into a linked-record field would fail, or
            # drop their other departments
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"Airtable's {STAFF_DEPARTMENT_FIELD} field isn't a list of linked"
                    " departments"
                ),
            )
        if department_id not in linked:
            await staff_airtable.update_staff_record(
                member.airtable_record_id,
                {STAFF_DEPARTMENT_FIELD: linked + [department_id]},
            )
        await UserService.sync_one(db, member.airtable_record_id)
        log_event(
            db,
            event_type="staff_added_to_department",
            area=WORKFORMS_AREA,
            actor_email=reviewer.email,
            actor_role="department_head",
            entity_type="staff",
            entity_id=member.id,
            details={"email": member.email, "department": department},
        )
        added.append(member.id)
    return added
