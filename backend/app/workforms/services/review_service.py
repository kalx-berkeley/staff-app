"""Department heads reviewing the hours staff submitted for their departments."""

import time
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.common.areas import WORKFORMS_AREA
from app.common.services.audit_service import log_event
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
from app.workforms.services.months import format_month, is_late, open_months

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
