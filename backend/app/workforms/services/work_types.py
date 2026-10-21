"""The types of work department heads offer staff logging hours in their department."""

from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.common.areas import WORKFORMS_AREA
from app.common.services.audit_service import log_event
from app.models.staff import Staff
from app.models.workform_work_types import WorkformWorkTypes
from app.workforms.schemas.workforms import WorkTypes

MAX_WORK_TYPES = 50
MAX_WORK_TYPE_LENGTH = 100


def _row(db: Session, department: str) -> Optional[WorkformWorkTypes]:
    return (
        db.query(WorkformWorkTypes)
        .filter(WorkformWorkTypes.department == department)
        .first()
    )


def _response(row: Optional[WorkformWorkTypes]) -> WorkTypes:
    if row is None or not row.work_types:
        return WorkTypes(work_types=[], allow_free_text=True)
    return WorkTypes(work_types=list(row.work_types), allow_free_text=row.allow_free_text)


def work_types(db: Session, department: str) -> WorkTypes:
    """
    *department*'s work types. With none, staff may always describe their
    work in their own words, whatever the head last chose.
    """
    return _response(_row(db, department))


def all_work_types(db: Session) -> Dict[str, WorkTypes]:
    """The work types of every department that has any, by department."""
    return {
        row.department: _response(row)
        for row in db.query(WorkformWorkTypes)
        if row.work_types
    }


def description_problem(db: Session, department: str, description: str) -> Optional[str]:
    """Why *description* isn't allowed in *department*, or None if it is."""
    allowed = work_types(db, department)
    if allowed.allow_free_text or description in allowed.work_types:
        return None
    return f"Choose one of the {department} types of work"


def _clean(names: List[str]) -> List[str]:
    """
    *names* stripped, without blanks or repeats (ignoring case), in order.

    :raises HTTPException: 422 if there are too many or one is too long
    """
    cleaned: List[str] = []
    seen = set()
    for name in names:
        name = " ".join(name.split())
        if not name or name.casefold() in seen:
            continue
        if len(name) > MAX_WORK_TYPE_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Work types can be at most {MAX_WORK_TYPE_LENGTH} characters",
            )
        seen.add(name.casefold())
        cleaned.append(name)
    if len(cleaned) > MAX_WORK_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"A department can have at most {MAX_WORK_TYPES} work types",
        )
    return cleaned


def update(
    db: Session,
    head: Staff,
    department: str,
    names: List[str],
    allow_free_text: bool,
) -> WorkTypes:
    """
    Set *department*'s work types. Entries already saved keep their
    descriptions; the new rules apply when an entry is added or changed.

    :raises HTTPException: 422 if free text is turned off with no work types
    """
    names = _clean(names)
    if not names and not allow_free_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Add at least one work type before requiring staff to choose one",
        )
    row = _row(db, department)
    if row is None:
        row = WorkformWorkTypes(department=department)
        db.add(row)
    row.work_types = names
    row.allow_free_text = allow_free_text
    db.commit()
    log_event(
        db,
        event_type="workform_work_types_updated",
        area=WORKFORMS_AREA,
        actor_email=head.email,
        actor_role="department_head",
        entity_type="workform_department",
        details={
            "department": department,
            "work_types": names,
            "allow_free_text": allow_free_text,
        },
    )
    return _response(row)
