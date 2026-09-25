"""Staff-pass alternate queue API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_promotions_staff, require_promotions_or_staff
from app.database import get_db
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_pass_alternate import StaffPassAlternate
from app.schemas.alternate import (
    AlternateEntryResponse,
    AlternateJoinRequest,
    AlternateQueueResponse,
    AlternateUpdateRequest,
    MyAlternateEntryResponse,
)
from app.services import audit_service
from app.services.alternate_service import AlternateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shows", tags=["alternates"])


def _get_show(db: Session, show_id: int) -> Show:
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show or show.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Show not found")
    return show


def _entry_response(entry: StaffPassAlternate, position: int, model=AlternateEntryResponse):
    data = {
        field: getattr(entry, field)
        for field in model.model_fields
        if field != "position" and hasattr(entry, field)
    }
    return model(position=position, **data)


def _my_waiting_entry(db: Session, show_id: int, staff: Staff) -> StaffPassAlternate:
    entry = AlternateService.get_waiting_entry(db, show_id, staff.id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not in the alternate queue for this show",
        )
    return entry


@router.get("/alternates/my-entries", response_model=list[MyAlternateEntryResponse])
def get_my_alternate_entries(
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Get the current staff member's waiting alternate entries, across all shows."""
    _, staff = user_info
    entries = (
        db.query(StaffPassAlternate)
        .filter(
            StaffPassAlternate.staff_id == staff.id,
            StaffPassAlternate.status == "waiting",
        )
        .all()
    )
    results = []
    for entry in entries:
        queue = AlternateService.waiting_entries(db, entry.show_id)
        position = next(i for i, e in enumerate(queue, start=1) if e.id == entry.id)
        results.append(_entry_response(entry, position, MyAlternateEntryResponse))
    results.sort(key=lambda r: (r.show_date is None, r.show_date))
    return results


@router.get("/{show_id}/alternates", response_model=AlternateQueueResponse)
def get_alternate_queue(
    show_id: int,
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Get a show's alternate queue in order, plus the current user's place in it."""
    _, staff = user_info
    show = _get_show(db, show_id)
    queue = AlternateService.waiting_entries(db, show.id)

    my_entry_id = next((e.id for e in queue if e.staff_id == staff.id), None)

    # If the current user holds a claim, tell them who would get it on release.
    next_candidate = None
    my_claim = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "staff",
            Pass.staff_id == staff.id,
            Pass.status == "claimed",
            Pass.guest_of_pass_id.is_(None),
        )
        .first()
    )
    if my_claim:
        has_guest_hold = (
            db.query(Pass).filter(Pass.guest_of_pass_id == my_claim.id).first() is not None
        )
        next_candidate = AlternateService.next_candidate(
            db, show, freed_passes=2 if has_guest_hold else 1
        )

    return AlternateQueueResponse(
        queue_open=AlternateService.is_queue_open(db, show),
        entries=[_entry_response(e, i) for i, e in enumerate(queue, start=1)],
        my_entry_id=my_entry_id,
        next_candidate_staff_id=next_candidate.staff_id if next_candidate else None,
        next_candidate_name=next_candidate.staff_name if next_candidate else None,
    )


@router.post(
    "/{show_id}/alternates",
    response_model=AlternateEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def join_alternate_queue(
    show_id: int,
    body: AlternateJoinRequest = AlternateJoinRequest(),
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Join the bottom of a show's staff-pass alternate queue."""
    role, staff = user_info
    show = _get_show(db, show_id)
    entry = AlternateService.join(
        db,
        show,
        staff,
        has_guest=body.has_guest,
        guest_name=body.guest_name,
        only_attend_with_guest=body.only_attend_with_guest,
    )
    audit_service.log_event(
        db,
        event_type="alternate_joined",
        actor_email=staff.email,
        actor_role=role,
        entity_type="staff_pass_alternate",
        entity_id=entry.id,
        details={
            "show_id": show.id,
            "has_guest": entry.has_guest,
            "guest_name": entry.guest_name,
            "only_attend_with_guest": entry.only_attend_with_guest,
        },
    )
    queue = AlternateService.waiting_entries(db, show.id)
    return _entry_response(entry, len(queue))


@router.patch("/{show_id}/alternates/me", response_model=AlternateEntryResponse)
def update_my_alternate_entry(
    show_id: int,
    body: AlternateUpdateRequest,
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Change the +1 details on the current user's entry, keeping their place."""
    role, staff = user_info
    show = _get_show(db, show_id)
    entry = _my_waiting_entry(db, show.id, staff)
    entry = AlternateService.update_guest(
        db,
        entry,
        has_guest=body.has_guest,
        guest_name=body.guest_name,
        only_attend_with_guest=body.only_attend_with_guest,
    )
    audit_service.log_event(
        db,
        event_type="alternate_updated",
        actor_email=staff.email,
        actor_role=role,
        entity_type="staff_pass_alternate",
        entity_id=entry.id,
        details={
            "show_id": show.id,
            "status": entry.status,
            "has_guest": entry.has_guest,
            "guest_name": entry.guest_name,
            "only_attend_with_guest": entry.only_attend_with_guest,
        },
    )
    queue = AlternateService.waiting_entries(db, show.id)
    position = next((i for i, e in enumerate(queue, start=1) if e.id == entry.id), 0)
    return _entry_response(entry, position)


@router.delete("/{show_id}/alternates/me", status_code=status.HTTP_204_NO_CONTENT)
def leave_alternate_queue(
    show_id: int,
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Leave a show's alternate queue."""
    role, staff = user_info
    show = _get_show(db, show_id)
    entry = _my_waiting_entry(db, show.id, staff)
    AlternateService.leave(db, entry)
    audit_service.log_event(
        db,
        event_type="alternate_left",
        actor_email=staff.email,
        actor_role=role,
        entity_type="staff_pass_alternate",
        entity_id=entry.id,
        details={"show_id": show.id},
    )


@router.delete("/{show_id}/alternates/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_alternate(
    show_id: int,
    entry_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Remove someone from a show's alternate queue (promotions staff only)."""
    show = _get_show(db, show_id)
    entry = (
        db.query(StaffPassAlternate)
        .filter(
            StaffPassAlternate.id == entry_id,
            StaffPassAlternate.show_id == show.id,
            StaffPassAlternate.status == "waiting",
        )
        .first()
    )
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alternate entry not found"
        )
    AlternateService.remove(db, entry, promotions)
    audit_service.log_event(
        db,
        event_type="alternate_removed",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="staff_pass_alternate",
        entity_id=entry.id,
        details={"show_id": show.id, "staff_id": entry.staff_id},
    )
