"""Staff Directory settings for site admins, shown in KALX Staff Admin."""

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth import get_site_admin
from app.common.areas import DIRECTORY_AREA
from app.common.services.audit_service import log_event
from app.database import get_db
from app.directory.schemas.directory import DjQuizDeadlineItem, DjQuizDeadlineUpdate
from app.models.dj_quiz_deadline import DjQuizDeadline
from app.models.staff import Staff

router = APIRouter(prefix="/api/directory/admin", tags=["directory-admin"])


@router.get("/dj-quiz-deadlines", response_model=list[DjQuizDeadlineItem])
def list_dj_quiz_deadlines(
    _admin: Staff = Depends(get_site_admin), db: Session = Depends(get_db)
):
    """Each year's DJ Quiz deadline, most recent year first."""
    return db.query(DjQuizDeadline).order_by(DjQuizDeadline.year.desc()).all()


@router.put("/dj-quiz-deadlines/{year}", response_model=DjQuizDeadlineItem)
def set_dj_quiz_deadline(
    request: DjQuizDeadlineUpdate,
    year: int = Path(..., ge=2000, le=2100),
    admin: Staff = Depends(get_site_admin),
    db: Session = Depends(get_db),
):
    """
    Set a year's DJ Quiz deadline: the last day (Pacific time) to complete
    that year's quiz. It must be in that year.
    """
    if request.deadline.year != year:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"The {year} deadline must be a date in {year}",
        )
    row = db.get(DjQuizDeadline, year)
    before = row.deadline.isoformat() if row else None
    if row is None:
        row = DjQuizDeadline(year=year, deadline=request.deadline)
        db.add(row)
    else:
        row.deadline = request.deadline
    db.commit()
    db.refresh(row)
    log_event(
        db,
        event_type="dj_quiz_deadline_set",
        area=DIRECTORY_AREA,
        actor_email=admin.email,
        actor_role="site_admin",
        details={"year": year, "before": before, "after": request.deadline.isoformat()},
    )
    return row


@router.delete("/dj-quiz-deadlines/{year}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dj_quiz_deadline(
    year: int,
    admin: Staff = Depends(get_site_admin),
    db: Session = Depends(get_db),
):
    """Remove a year's DJ Quiz deadline."""
    row = db.get(DjQuizDeadline, year)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    before = row.deadline.isoformat()
    db.delete(row)
    db.commit()
    log_event(
        db,
        event_type="dj_quiz_deadline_removed",
        area=DIRECTORY_AREA,
        actor_email=admin.email,
        actor_role="site_admin",
        details={"year": year, "before": before},
    )
