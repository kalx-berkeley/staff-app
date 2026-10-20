"""Workform status and leave flags, and the monthly hours the directory profile shows."""

from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.common.services.profile_providers import DepartmentHours, MonthHours
from app.models.staff import Staff
from app.models.workform import Workform
from app.models.workform_airtable_record import WorkformAirtableRecord
from app.workforms.services import records
from app.workforms.services.loa import month_overlaps
from app.workforms.services.months import is_late


def workform_status(
    workform: Optional[Workform], record: Optional[WorkformAirtableRecord]
) -> str:
    """ "not_started", "draft", "submitted" or "locked" (a department has decided)."""
    if record is not None:
        return "locked" if records.is_locked(record) else "submitted"
    if workform is not None and workform.entries:
        return "draft"
    return "not_started"


def month_on_leave(
    month: date,
    staff: Staff,
    workform: Optional[Workform],
    record: Optional[WorkformAirtableRecord],
) -> bool:
    """Whether a leave overlaps *month*: the leave recorded at submit once
    submitted (as department heads see it), else the staff member's current one."""
    if record is not None and workform is not None:
        loa_start, loa_end = workform.loa_start_at_submit, workform.loa_end_at_submit
    else:
        loa_start, loa_end = staff.loa_start, staff.loa_end
    return month_overlaps(month, loa_start, loa_end)


def monthly_hours(db: Session, staff: Staff, months: List[date]) -> Dict[date, MonthHours]:
    """
    A staff member's workform for each of *months*, for the Staff Directory's
    profile page (registered as its monthly hours provider in `main.py`).

    :param db: Database session.
    :param staff: The staff member.
    :param months: First days of the months wanted.
    :returns: A MonthHours for every month in *months*.
    """
    result: Dict[date, MonthHours] = {}
    for month in months:
        workform = (
            db.query(Workform)
            .filter(Workform.staff_id == staff.id, Workform.month == month)
            .first()
        )
        record = records.record_for(db, staff.airtable_record_id, month)
        departments = []
        if record is not None:
            for department, block in sorted((record.departments or {}).items()):
                if records.has_hours(block) or block.get("approved"):
                    departments.append(
                        DepartmentHours(
                            department=department,
                            hours=block.get("hours") or 0.0,
                            decision=block.get("approved"),
                        )
                    )
            reported = sum(d.hours for d in departments)
        else:
            reported = sum(e.hours for e in workform.entries) if workform else 0.0
        result[month] = MonthHours(
            month=month,
            status=workform_status(workform, record),
            reported_hours=reported,
            departments=departments,
            is_late=bool(record and record.created_time)
            and is_late(month, record.created_time),
            loa_overlaps_month=month_on_leave(month, staff, workform, record),
        )
    return result
