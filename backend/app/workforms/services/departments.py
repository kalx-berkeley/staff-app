"""Workform departments, their heads, and who may review what."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth import is_current_staff
from app.common.services.user_service import UserService
from app.config import settings
from app.models.staff import Staff
from app.models.workform import Workform
from app.models.workform_department import DepartmentHead, WorkformDepartment

logger = logging.getLogger(__name__)

DEPARTMENT_FIELD = "Department"
HEADS_FIELD = "Department Heads"


async def sync_department_heads(db: Session, result: Dict[str, Any]) -> None:
    """
    Copy the Airtable "Department Heads" table into the database.

    Its "Department" field links to the departments table and is resolved to
    names; its "Department Heads" field links to staff records and is stored
    as their record IDs. If Airtable can't be read, the existing copy is kept
    and the error is added to *result*["errors"].
    """
    try:
        records = await UserService.fetch_airtable_records(
            settings.airtable_department_heads_table_name
        )
        department_names = await UserService.fetch_department_names()
    except HTTPException as e:
        result["errors"].append(f"Department heads sync failed: {e.detail}")
        return
    if not records:
        # Also what an unconfigured Airtable returns; never wipe the copy.
        logger.warning("Department Heads table is empty; keeping the existing copy")
        return

    heads: Dict[str, set[str]] = {}
    for record in records:
        fields = record.get("fields", {})
        linked = fields.get(DEPARTMENT_FIELD) or []
        if isinstance(linked, str):
            linked = [linked]
        for department in linked:
            name = department_names.get(department, department)
            if not isinstance(name, str) or not name.strip():
                continue
            if name.startswith("rec") and name == department:
                result["errors"].append(
                    f"Department Heads: couldn't resolve department {department}"
                )
                continue
            members = heads.setdefault(name.strip(), set())
            for head in fields.get(HEADS_FIELD) or []:
                if isinstance(head, str):
                    members.add(head)

    db.query(DepartmentHead).delete()
    db.query(WorkformDepartment).delete()
    for name, members in sorted(heads.items()):
        db.add(WorkformDepartment(name=name))
        for head in sorted(members):
            db.add(DepartmentHead(department=name, staff_airtable_record_id=head))
    db.commit()
    logger.info("Synced %d workform departments and their heads", len(heads))


def drop_inactive_drafts(db: Session) -> int:
    """
    Delete the unsubmitted workforms of staff who are no longer current staff
    (neither Active nor 🆕).
    """
    dropped = 0
    drafts = db.query(Workform).filter(Workform.airtable_record_id.is_(None)).all()
    for draft in drafts:
        if not is_current_staff(draft.staff):
            db.delete(draft)
            dropped += 1
    db.commit()
    if dropped:
        logger.info(
            "Deleted %d draft workforms of staff who are no longer Active or 🆕", dropped
        )
    return dropped


async def after_staff_sync(db: Session, result: Dict[str, Any]) -> None:
    """Workforms' part of the Airtable staff sync."""
    await sync_department_heads(db, result)
    drop_inactive_drafts(db)


def departments(db: Session) -> List[str]:
    """Every department a workform can report hours in, sorted by name."""
    return [d.name for d in db.query(WorkformDepartment).order_by(WorkformDepartment.name)]


def heads_of(db: Session, department: str) -> set[str]:
    """The Airtable staff record IDs of *department*'s heads."""
    return {
        h.staff_airtable_record_id
        for h in db.query(DepartmentHead).filter(DepartmentHead.department == department)
    }


def headed_by(db: Session, staff: Staff) -> List[str]:
    """The departments *staff* heads, sorted by name."""
    if not staff.airtable_record_id:
        return []
    return sorted(
        h.department
        for h in db.query(DepartmentHead).filter(
            DepartmentHead.staff_airtable_record_id == staff.airtable_record_id
        )
    )


def is_department_head(db: Session, staff: Staff) -> bool:
    return bool(headed_by(db, staff))


def is_operations_head(db: Session, staff: Staff) -> bool:
    return settings.workforms_operations_department in headed_by(db, staff)


def responsible_reviewers(
    db: Session, department: str, subject_record_id: Optional[str]
) -> set[str]:
    """
    Who's expected to review *subject*'s hours in *department*.

    That's the department's heads other than the subject. When there are
    none (a department with no head, or a head's own hours) it's the
    Operations heads, who may then review their own Operations hours.
    """
    heads = heads_of(db, department) - {subject_record_id}
    return heads or heads_of(db, settings.workforms_operations_department)


def can_review(
    db: Session, reviewer: Staff, department: str, subject_record_id: Optional[str]
) -> bool:
    """
    Whether *reviewer* may decide on *subject*'s hours in *department*.

    A head may review their departments' hours from anyone but themselves. An
    Operations head may review any department as a fallback, including their
    own hours.
    """
    if not reviewer.airtable_record_id:
        return False
    if is_operations_head(db, reviewer):
        return True
    return (
        reviewer.airtable_record_id in heads_of(db, department)
        and reviewer.airtable_record_id != subject_record_id
    )


def reviewable_departments(db: Session, reviewer: Staff) -> tuple[List[str], List[str]]:
    """
    The departments *reviewer* can review, as (own, fallback).

    Own departments are the ones they head, plus, for an Operations head,
    departments with no head. Fallback departments are every other department
    and only Operations heads have them.
    """
    own = set(headed_by(db, reviewer))
    if not own:
        return [], []
    if settings.workforms_operations_department not in own:
        return sorted(own), []
    all_departments = departments(db)
    headed = {h.department for h in db.query(DepartmentHead)}
    own |= {d for d in all_departments if d not in headed}
    fallback = [d for d in all_departments if d not in own]
    return sorted(own), fallback
