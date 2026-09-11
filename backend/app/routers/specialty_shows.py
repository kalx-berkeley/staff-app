"""Specialty show API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.schemas.specialty_show import (
    SpecialtyShowCreate,
    SpecialtyShowUpdate,
    SpecialtyShowResponse,
)
from app.services import audit_service
from app.services.spinitron_show_titles_service import SpinitronShowTitlesService
from app.auth import get_promotions_staff, get_staff_member, require_promotions_or_staff
from app.models.staff import Staff
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_owner import SpecialtyShowOwner
from app.models.specialty_show_dj import SpecialtyShowDJ
from app.models.staff_status import StaffStatus

router = APIRouter(prefix="/api/specialty-shows", tags=["specialty-shows"])

ACTIVE_STATUS = "Active"


def _resolve_staff_id(db: Session, email: str) -> int | None:
    """Return the Staff.id for an active staff member with the given email, or None."""
    from app.models.staff import Staff as StaffModel

    staff = (
        db.query(StaffModel)
        .join(StaffStatus, StaffModel.id == StaffStatus.staff_id)
        .filter(StaffModel.email == email, StaffStatus.status == ACTIVE_STATUS)
        .first()
    )
    return staff.id if staff else None


def _is_show_owner(show: SpecialtyShow, email: str) -> bool:
    """Return True if the given email is an owner of this specialty show."""
    return any(o.staff_email == email for o in show.owners)


def _sync_owners(db: Session, show: SpecialtyShow, owner_emails: list[str]) -> None:
    """Replace the owner list for a specialty show."""
    for owner in list(show.owners):
        db.delete(owner)
    db.flush()
    for email in owner_emails:
        staff_id = _resolve_staff_id(db, email)
        if staff_id:
            db.add(SpecialtyShowOwner(specialty_show_id=show.id, staff_id=staff_id))


def _sync_djs(db: Session, show: SpecialtyShow, dj_names: list[str]) -> None:
    """Replace the DJ list for a specialty show."""
    for dj in list(show.djs):
        db.delete(dj)
    db.flush()
    for name in dj_names:
        name = name.strip()
        if name:
            db.add(SpecialtyShowDJ(specialty_show_id=show.id, dj_name=name))


@router.get("", response_model=list[SpecialtyShowResponse])
def list_specialty_shows(db: Session = Depends(get_db)):
    """List all active (non-deleted) specialty shows."""
    return (
        db.query(SpecialtyShow)
        .filter(SpecialtyShow.deleted == False)  # noqa: E712
        .order_by(SpecialtyShow.name)
        .all()
    )


@router.get("/my", response_model=list[SpecialtyShowResponse])
def list_my_specialty_shows(
    staff: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    """List specialty shows where the current user is an owner."""
    return (
        db.query(SpecialtyShow)
        .join(SpecialtyShowOwner, SpecialtyShow.id == SpecialtyShowOwner.specialty_show_id)
        .filter(
            SpecialtyShow.deleted == False,  # noqa: E712
            SpecialtyShowOwner.staff_id == staff.id,
        )
        .order_by(SpecialtyShow.name)
        .all()
    )


@router.get("/upcoming-titles", response_model=list[str])
async def list_upcoming_spinitron_titles(db: Session = Depends(get_db)):
    """List distinct Spinitron show titles scheduled in the next ~2 weeks.

    Declared before `/{show_id}` so it isn't swallowed by that route.
    """
    return await SpinitronShowTitlesService.get_upcoming_titles(db)


@router.post("", response_model=SpecialtyShowResponse, status_code=status.HTTP_201_CREATED)
def create_specialty_show(
    data: SpecialtyShowCreate,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Create a new specialty show (promotions staff only)."""
    existing = (
        db.query(SpecialtyShow).filter(SpecialtyShow.name == data.name.strip()).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A specialty show named '{data.name}' already exists.",
        )
    now = datetime.now(timezone.utc)
    show = SpecialtyShow(name=data.name.strip(), created_at=now, updated_at=now)
    db.add(show)
    db.flush()

    owner_emails = data.owner_emails or [promotions.email]
    _sync_owners(db, show, owner_emails)

    db.commit()
    db.refresh(show)
    audit_service.log_event(
        db,
        event_type="specialty_show_created",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="specialty_show",
        entity_id=show.id,
        details={"name": show.name, "owner_emails": owner_emails},
    )
    return show


@router.get("/{show_id}", response_model=SpecialtyShowResponse)
def get_specialty_show(show_id: int, db: Session = Depends(get_db)):
    """Get a specialty show by ID."""
    show = db.query(SpecialtyShow).filter(SpecialtyShow.id == show_id).first()
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Specialty show not found"
        )
    return show


@router.get("/{show_id}/dj-history", response_model=list[str])
async def get_specialty_show_dj_history(show_id: int, db: Session = Depends(get_db)):
    """List DJs who hosted a Spinitron show with this exact name in the past ~2 months."""
    show = db.query(SpecialtyShow).filter(SpecialtyShow.id == show_id).first()
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Specialty show not found"
        )
    return await SpinitronShowTitlesService.get_dj_history_for_title(db, show.name)


@router.put("/{show_id}", response_model=SpecialtyShowResponse)
def update_specialty_show(
    show_id: int,
    data: SpecialtyShowUpdate,
    role_and_staff: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Update a specialty show (promotions staff or show owner)."""
    role, actor = role_and_staff
    show = db.query(SpecialtyShow).filter(SpecialtyShow.id == show_id).first()
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Specialty show not found"
        )

    if role != "promotions" and not _is_show_owner(show, actor.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only promotions staff or specialty show owners can update this show",
        )

    if data.name is not None:
        new_name = data.name.strip()
        conflict = (
            db.query(SpecialtyShow)
            .filter(SpecialtyShow.name == new_name, SpecialtyShow.id != show_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A specialty show named '{new_name}' already exists.",
            )
        show.name = new_name

    if data.owner_emails is not None:
        _sync_owners(db, show, data.owner_emails)

    if data.dj_names is not None:
        _sync_djs(db, show, data.dj_names)

    show.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(show)
    audit_service.log_event(
        db,
        event_type="specialty_show_updated",
        actor_email=actor.email,
        actor_role=role,
        entity_type="specialty_show",
        entity_id=show.id,
        details={"name": show.name},
    )
    return show


@router.delete("/{show_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_specialty_show(
    show_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Soft-delete a specialty show (promotions staff only)."""
    show = db.query(SpecialtyShow).filter(SpecialtyShow.id == show_id).first()
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Specialty show not found"
        )
    show.deleted = True
    show.updated_at = datetime.now(timezone.utc)
    db.commit()
    audit_service.log_event(
        db,
        event_type="specialty_show_deleted",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="specialty_show",
        entity_id=show_id,
        details={"name": show.name},
    )
