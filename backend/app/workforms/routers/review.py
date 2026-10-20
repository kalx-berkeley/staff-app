"""KALX Workforms API for department heads reviewing submitted hours."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_staff_member
from app.database import get_db
from app.models.staff import Staff
from app.models.workform_airtable_record import WorkformAirtableRecord
from app.workforms.schemas.workforms import (
    DecisionRequest,
    DepartmentPeopleResponse,
    PendingCountsResponse,
    ReviewItem,
    ReviewOverviewResponse,
    ReviewQueueResponse,
)
from app.workforms.services import review_service
from app.workforms.services.departments import is_operations_head, reviewable_departments
from app.workforms.services.months import format_month, open_months, parse_month

router = APIRouter(prefix="/api/workforms/review", tags=["workforms"])

# The most months the department people list looks back
MAX_PEOPLE_MONTHS = 12


def get_reviewer(
    staff: Staff = Depends(get_staff_member), db: Session = Depends(get_db)
) -> Staff:
    """The current user, if they head a department."""
    own, _ = reviewable_departments(db, staff)
    if not own:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only department heads can review workforms",
        )
    return staff


def _month(month: str):
    try:
        return parse_month(month)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("", response_model=ReviewOverviewResponse)
def overview(reviewer: Staff = Depends(get_reviewer), db: Session = Depends(get_db)):
    """The departments the reviewer can review and the month to start on."""
    own, fallback = reviewable_departments(db, reviewer)
    default_month = review_service.default_month(db, reviewer)
    counts = review_service.pending_counts(db, reviewer, default_month)
    waiting = [d for d in own + fallback if counts.get(d)]
    months = {
        m for (m,) in db.query(WorkformAirtableRecord.month).distinct() if m is not None
    } | set(open_months())
    return ReviewOverviewResponse(
        is_operations_head=is_operations_head(db, reviewer),
        own_departments=own,
        fallback_departments=fallback,
        default_month=format_month(default_month),
        default_department=waiting[0] if waiting else own[0],
        months=[format_month(m) for m in sorted(months, reverse=True)],
    )


# Before "/{month}/{department}", which would otherwise match it
@router.get("/people/{department}", response_model=DepartmentPeopleResponse)
def department_people(
    department: str,
    months: int = Query(3, ge=1, le=MAX_PEOPLE_MONTHS),
    min_months: int = Query(2, ge=1, le=MAX_PEOPLE_MONTHS),
    reviewer: Staff = Depends(get_reviewer),
    db: Session = Depends(get_db),
):
    """
    Who works in *department*: everyone who reported hours in it in at least
    *min_months* of the last *months* months.
    """
    if min_months > months:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The months with hours can't be more than the months considered",
        )
    return review_service.department_people(db, reviewer, department, months, min_months)


@router.get("/{month}/pending", response_model=PendingCountsResponse)
async def pending(
    month: str, reviewer: Staff = Depends(get_reviewer), db: Session = Depends(get_db)
):
    """How many submissions in each department await a decision."""
    month_date = _month(month)
    await review_service.refresh_month_if_stale(db, month_date)
    return PendingCountsResponse(
        month=format_month(month_date),
        pending=review_service.pending_counts(db, reviewer, month_date),
    )


@router.get("/{month}/{department}", response_model=ReviewQueueResponse)
async def review_queue(
    month: str,
    department: str,
    reviewer: Staff = Depends(get_reviewer),
    db: Session = Depends(get_db),
):
    """The month's submissions with hours in *department*, and review progress."""
    month_date = _month(month)
    await review_service.refresh_month_if_stale(db, month_date)
    return review_service.queue(db, reviewer, month_date, department)


@router.put("/decisions/{airtable_record_id}/{department}", response_model=ReviewItem)
async def decide(
    airtable_record_id: str,
    department: str,
    request: DecisionRequest,
    reviewer: Staff = Depends(get_reviewer),
    db: Session = Depends(get_db),
):
    """Approve or deny a submission's hours in *department*, or clear the decision."""
    return await review_service.decide(
        db, reviewer, airtable_record_id, department, request.decision
    )
