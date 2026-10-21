"""KALX Workforms API for staff: entries, submitting, and past workforms."""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth import get_site_admin, get_staff_member
from app.database import get_db
from app.models.staff import Staff
from app.models.workform import Workform, WorkformEntry
from app.models.workform_airtable_record import WorkformAirtableRecord
from app.models.workform_preferences import WorkformPreferences
from app.workforms.schemas.workforms import (
    DepartmentResult,
    DepartmentsResponse,
    EntryRequest,
    EntryResponse,
    MyWorkformsResponse,
    PreferencesRequest,
    PreferencesResponse,
    WorkformResponse,
    WorkformSummary,
)
from app.workforms.services import records, work_types, workform_service
from app.workforms.services.departments import departments, is_department_head
from app.workforms.services.loa import entry_flag
from app.workforms.services.months import (
    deadline,
    format_month,
    is_late,
    open_months,
    parse_month,
)
from app.workforms.services.notifications import get_preferences
from app.workforms.services.summary import month_on_leave, workform_status

router = APIRouter(prefix="/api/workforms", tags=["workforms"])


def _month(month: str) -> date:
    try:
        return parse_month(month)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


def _results(record: Optional[WorkformAirtableRecord]) -> dict[str, DepartmentResult]:
    if record is None:
        return {}
    return {
        department: DepartmentResult(
            hours=block.get("hours"),
            description=block.get("description"),
            decision=block.get("approved"),
        )
        for department, block in sorted((record.departments or {}).items())
        if records.has_hours(block) or block.get("approved")
    }


def _entry_response(
    entry: WorkformEntry, month: date, loa_start: Optional[date], loa_end: Optional[date]
) -> EntryResponse:
    return EntryResponse(
        id=entry.id,
        department=entry.department,
        hours=entry.hours,
        description=entry.description,
        work_date=entry.work_date,
        loa_flag=entry_flag(entry.work_date, month, loa_start, loa_end),
    )


@router.get("/departments", response_model=DepartmentsResponse)
def list_departments(
    staff: Staff = Depends(get_staff_member), db: Session = Depends(get_db)
):
    """Every workform department, the user's own first, and their work types."""
    mine = {d.department for d in staff.departments}
    all_departments = departments(db)
    return DepartmentsResponse(
        own=[d for d in all_departments if d in mine],
        other=[d for d in all_departments if d not in mine],
        work_types=work_types.all_work_types(db),
    )


def _workforms_for(db: Session, staff: Staff) -> MyWorkformsResponse:
    """A staff member's open months and every workform they've saved or submitted."""
    months = open_months()
    workforms = {
        w.month: w for w in db.query(Workform).filter(Workform.staff_id == staff.id)
    }
    submitted = {}
    if staff.airtable_record_id:
        for record in db.query(WorkformAirtableRecord).filter(
            WorkformAirtableRecord.staff_airtable_record_id == staff.airtable_record_id,
            WorkformAirtableRecord.month.isnot(None),
        ):
            submitted.setdefault(record.month, record)
    summaries = []
    for month in sorted(set(workforms) | set(submitted) | set(months), reverse=True):
        workform, record = workforms.get(month), submitted.get(month)
        if record is not None:
            total = sum(b.get("hours") or 0 for b in (record.departments or {}).values())
        else:
            total = sum(e.hours for e in workform.entries) if workform else 0.0
        summaries.append(
            WorkformSummary(
                month=format_month(month),
                status=workform_status(workform, record),
                is_open=month in months,
                is_late=bool(record and record.created_time)
                and is_late(month, record.created_time),
                total_hours=total,
                results=_results(record),
                loa_overlaps_month=month_on_leave(month, staff, workform, record),
            )
        )
    return MyWorkformsResponse(
        open_months=[format_month(m) for m in months], workforms=summaries
    )


def _workform_for(db: Session, staff: Staff, month_date: date) -> WorkformResponse:
    """One month of a staff member's workform: its entries, status and each
    department's decision."""
    workform = workform_service.get_workform(db, staff, month_date)
    record = records.record_for(db, staff.airtable_record_id, month_date)
    months = open_months()
    return WorkformResponse(
        month=format_month(month_date),
        is_open=month_date in months,
        is_current_month=month_date == months[0],
        deadline=deadline(month_date),
        status=workform_status(workform, record),
        has_unsent_changes=record is not None
        and workform_service.has_unsent_changes(workform),
        submitted_at=record.created_time if record else None,
        is_late=bool(record and record.created_time)
        and is_late(month_date, record.created_time),
        would_be_late=is_late(month_date, datetime.now(timezone.utc)),
        entries=[
            _entry_response(e, month_date, staff.loa_start, staff.loa_end)
            for e in (workform.entries if workform else [])
        ],
        results=_results(record),
        loa_start=staff.loa_start,
        loa_end=staff.loa_end,
        loa_overlaps_month=month_on_leave(month_date, staff, workform, record),
    )


@router.get("/me", response_model=MyWorkformsResponse)
def my_workforms(staff: Staff = Depends(get_staff_member), db: Session = Depends(get_db)):
    """The user's open months and every workform they've saved or submitted."""
    return _workforms_for(db, staff)


@router.get("/me/{month}", response_model=WorkformResponse)
def my_workform(
    month: str, staff: Staff = Depends(get_staff_member), db: Session = Depends(get_db)
):
    """One month's workform: its entries, status and each department's decision."""
    return _workform_for(db, staff, _month(month))


def _other_staff(db: Session, staff_id: int) -> Staff:
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
        )
    return staff


@router.get("/staff/{staff_id}", response_model=MyWorkformsResponse)
def staff_workforms(
    staff_id: int,
    _admin: Staff = Depends(get_site_admin),
    db: Session = Depends(get_db),
):
    """
    Another staff member's workforms, as they see them on their history page.
    Site admins only, and read-only.
    """
    staff = _other_staff(db, staff_id)
    response = _workforms_for(db, staff)
    response.staff_name = staff.name
    return response


@router.get("/staff/{staff_id}/{month}", response_model=WorkformResponse)
def staff_workform(
    staff_id: int,
    month: str,
    _admin: Staff = Depends(get_site_admin),
    db: Session = Depends(get_db),
):
    """
    One month of another staff member's workform. Site admins only, and
    read-only.
    """
    staff = _other_staff(db, staff_id)
    response = _workform_for(db, staff, _month(month))
    response.staff_name = staff.name
    return response


@router.post(
    "/me/{month}/entries", response_model=EntryResponse, status_code=status.HTTP_201_CREATED
)
def add_entry(
    month: str,
    request: EntryRequest,
    staff: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    month_date = _month(month)
    entry = workform_service.add_entry(
        db,
        staff,
        month_date,
        request.department,
        request.hours,
        request.description,
        request.work_date,
    )
    return _entry_response(entry, month_date, staff.loa_start, staff.loa_end)


@router.put("/me/{month}/entries/{entry_id}", response_model=EntryResponse)
def update_entry(
    month: str,
    entry_id: int,
    request: EntryRequest,
    staff: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    month_date = _month(month)
    entry = workform_service.update_entry(
        db,
        staff,
        month_date,
        entry_id,
        request.department,
        request.hours,
        request.description,
        request.work_date,
    )
    return _entry_response(entry, month_date, staff.loa_start, staff.loa_end)


@router.delete("/me/{month}/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    month: str,
    entry_id: int,
    staff: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    workform_service.delete_entry(db, staff, _month(month), entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/{month}/submit", response_model=WorkformResponse)
async def submit(
    month: str, staff: Staff = Depends(get_staff_member), db: Session = Depends(get_db)
):
    """Submit, or resubmit, the month's workform to Airtable."""
    await workform_service.submit(db, staff, _month(month))
    return my_workform(month, staff, db)


@router.get("/preferences", response_model=PreferencesResponse)
def get_workform_preferences(
    staff: Staff = Depends(get_staff_member), db: Session = Depends(get_db)
):
    prefs = get_preferences(db, staff)
    return PreferencesResponse(
        reminder_emails_enabled=prefs.reminder_emails_enabled if prefs else True,
        review_emails_enabled=prefs.review_emails_enabled if prefs else True,
        is_department_head=is_department_head(db, staff),
    )


@router.put("/preferences", response_model=PreferencesResponse)
def update_workform_preferences(
    request: PreferencesRequest,
    staff: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    prefs = get_preferences(db, staff)
    if prefs is None:
        prefs = WorkformPreferences(staff_id=staff.id)
        db.add(prefs)
    prefs.reminder_emails_enabled = request.reminder_emails_enabled
    prefs.review_emails_enabled = request.review_emails_enabled
    db.commit()
    return get_workform_preferences(staff, db)
