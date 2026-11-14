"""Specialty show API endpoints.

Serves both kinds of show: Specialty Music Shows (category "music", with DJ
members) and Talk & Information shows (category "talk", with staff members).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.common.areas import PASS_GIVEAWAY_AREA
from app.database import get_db
from app.pass_giveaway.schemas.specialty_show import (
    SpecialtyShowCategory,
    SpecialtyShowCreate,
    SpecialtyShowUpdate,
    SpecialtyShowResponse,
    SpecialtyShowOwnerInfo,
    MySpecialtyShowResponse,
)
from app.common.services import audit_service
from app.pass_giveaway.services.specialty_show_spinitron import (
    resolve_urls,
    set_spinitron_shows,
)
from app.pass_giveaway.services.spinitron_show_titles_service import (
    SpinitronShowTitlesService,
)
from app.auth import (
    current_staff_filter,
    get_promotions_staff,
    get_staff_member,
    require_promotions_or_staff,
)
from app.models.staff import Staff
from app.models.specialty_show import SpecialtyShow
from app.models.talk_show_staff import TalkShowStaff
from app.pass_giveaway.services.specialty_show_membership import dj_name_parts
from app.models.specialty_show_owner import SpecialtyShowOwner
from app.models.specialty_show_dj import SpecialtyShowDJ
from app.pass_giveaway.guest_redaction import GuestRedactingRoute

router = APIRouter(
    prefix="/api/specialty-shows", tags=["specialty-shows"], route_class=GuestRedactingRoute
)


def _resolve_staff_id(db: Session, email: str) -> int | None:
    """
    Return the Staff.id for a current (Active or 🆕) staff member with the
    given email, or None.
    """
    from app.models.staff import Staff as StaffModel

    staff = (
        db.query(StaffModel)
        .filter(StaffModel.email == email, current_staff_filter())
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


def _sync_staff_members(db: Session, show: SpecialtyShow, emails: list[str]) -> None:
    """Replace a talk show's staff members. Emails of non-current staff are dropped."""
    for member in list(show.staff_members):
        db.delete(member)
    db.flush()
    added: set[int] = set()
    for email in emails:
        staff_id = _resolve_staff_id(db, email.strip())
        if staff_id and staff_id not in added:
            added.add(staff_id)
            db.add(TalkShowStaff(specialty_show_id=show.id, staff_id=staff_id))


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Show not found")


@router.get("", response_model=list[SpecialtyShowResponse])
def list_specialty_shows(
    include_retired: bool = Query(False),
    category: SpecialtyShowCategory | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    List the current (not deleted or retired) shows, and also the retired ones
    if *include_retired* is set. Both kinds, unless *category* picks one.
    """
    query = db.query(SpecialtyShow)
    if include_retired:
        query = query.filter(SpecialtyShow.deleted == False)  # noqa: E712
    else:
        query = query.filter(SpecialtyShow.current_filter())
    if category is not None:
        query = query.filter(SpecialtyShow.category == category)
    return query.order_by(SpecialtyShow.name).all()


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
            SpecialtyShow.current_filter(),
            SpecialtyShowOwner.staff_id == staff.id,
        )
        .order_by(SpecialtyShow.name)
        .all()
    )


@router.get("/mine", response_model=list[MySpecialtyShowResponse])
def list_mine_specialty_shows(
    staff: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    """List shows where the current user is an owner and/or a member.

    Unlike `/my` (owner only), this also matches the user's `dj_name` against
    each music show's DJ roster, and the user against each talk show's staff
    members, since a user can hold either or both roles on a show.
    """
    owner_show_ids = {
        show_id
        for (show_id,) in db.query(SpecialtyShowOwner.specialty_show_id).filter(
            SpecialtyShowOwner.staff_id == staff.id
        )
    }

    names = dj_name_parts(staff)
    dj_show_ids = set()
    if names:
        dj_show_ids = {
            show_id
            for (show_id,) in db.query(SpecialtyShowDJ.specialty_show_id).filter(
                SpecialtyShowDJ.dj_name.in_(names)
            )
        }
    staff_member_show_ids = {
        show_id
        for (show_id,) in db.query(TalkShowStaff.specialty_show_id).filter(
            TalkShowStaff.staff_id == staff.id
        )
    }

    show_ids = owner_show_ids | dj_show_ids | staff_member_show_ids
    if not show_ids:
        return []

    shows = (
        db.query(SpecialtyShow)
        .filter(SpecialtyShow.id.in_(show_ids), SpecialtyShow.current_filter())
        .order_by(SpecialtyShow.name)
        .all()
    )
    return [
        MySpecialtyShowResponse(
            id=show.id,
            name=show.name,
            category=show.category,
            deleted=show.deleted,
            retired=show.retired,
            spinitron_shows=show.spinitron_shows,
            owner_emails=show.owner_emails,
            owner_details=show.owner_details,
            dj_names=show.dj_names,
            staff_member_emails=show.staff_member_emails,
            staff_member_details=show.staff_member_details,
            is_owner=show.id in owner_show_ids,
            is_dj=show.id in dj_show_ids and not show.is_talk,
            is_staff_member=show.id in staff_member_show_ids and show.is_talk,
        )
        for show in shows
    ]


@router.get("/upcoming-titles", response_model=list[str])
async def list_upcoming_spinitron_titles(db: Session = Depends(get_db)):
    """List distinct Spinitron show titles scheduled in the next ~2 weeks.

    Declared before `/{show_id}` so it isn't swallowed by that route.
    """
    return await SpinitronShowTitlesService.get_upcoming_titles(db)


@router.get("/staff-emails", response_model=list[SpecialtyShowOwnerInfo])
def list_staff_emails(
    staff: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    """List current (Active or 🆕) staff members' names and emails, for the
    owner-email autocomplete.

    Declared before `/{show_id}` so it isn't swallowed by that route.
    """
    return db.query(Staff).filter(current_staff_filter()).order_by(Staff.name).all()


@router.post("", response_model=SpecialtyShowResponse, status_code=status.HTTP_201_CREATED)
async def create_specialty_show(
    data: SpecialtyShowCreate,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Create a new Specialty Music Show or Talk & Info Show (promotions staff only)."""
    existing = (
        db.query(SpecialtyShow).filter(SpecialtyShow.name == data.name.strip()).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A show named '{data.name}' already exists.",
        )
    spinitron_shows = await resolve_urls(data.spinitron_urls)
    if not spinitron_shows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add the show's Spinitron link",
        )
    now = datetime.now(timezone.utc)
    show = SpecialtyShow(
        name=data.name.strip(), category=data.category, created_at=now, updated_at=now
    )
    db.add(show)
    db.flush()

    owner_emails = data.owner_emails or [promotions.email]
    _sync_owners(db, show, owner_emails)
    set_spinitron_shows(db, show, spinitron_shows)

    db.commit()
    db.refresh(show)
    audit_service.log_event(
        db,
        event_type="specialty_show_created",
        area=PASS_GIVEAWAY_AREA,
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="specialty_show",
        entity_id=show.id,
        details={
            "name": show.name,
            "category": show.category,
            "owner_emails": owner_emails,
            "spinitron_show_ids": [s.id for s in spinitron_shows],
        },
    )
    return show


@router.get("/{show_id}", response_model=SpecialtyShowResponse)
def get_specialty_show(show_id: int, db: Session = Depends(get_db)):
    """Get a Specialty Music Show or Talk & Info Show by ID."""
    show = db.query(SpecialtyShow).filter(SpecialtyShow.id == show_id).first()
    if not show:
        raise _not_found()
    return show


@router.get("/{show_id}/dj-history", response_model=list[str])
async def get_specialty_show_dj_history(show_id: int, db: Session = Depends(get_db)):
    """List DJs who hosted a Spinitron show with this exact name in the past ~2 months."""
    show = db.query(SpecialtyShow).filter(SpecialtyShow.id == show_id).first()
    if not show:
        raise _not_found()
    return await SpinitronShowTitlesService.get_dj_history_for_title(db, show.name)


def _get_editable_show(db: Session, show_id: int, role: str, actor: Staff) -> SpecialtyShow:
    """The show, if *actor* (promotions staff or one of its owners) may edit it."""
    show = db.query(SpecialtyShow).filter(SpecialtyShow.id == show_id).first()
    if not show:
        raise _not_found()
    if role != "promotions" and not _is_show_owner(show, actor.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only promotions staff or the show's owners can update this show",
        )
    return show


@router.put("/{show_id}", response_model=SpecialtyShowResponse)
async def update_specialty_show(
    show_id: int,
    data: SpecialtyShowUpdate,
    role_and_staff: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """
    Update a show (promotions staff or show owner). A show must have a
    Spinitron show, so saving a show that has none needs *spinitron_urls*.
    Music shows take *dj_names* and talk shows take *staff_member_emails*.
    """
    role, actor = role_and_staff
    show = _get_editable_show(db, show_id, role, actor)
    if show.is_talk and data.dj_names is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Talk & Info Show has staff members, not DJs",
        )
    if not show.is_talk and data.staff_member_emails is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Specialty Music Show has DJs, not staff members",
        )

    spinitron_shows = None
    if data.spinitron_urls is not None:
        spinitron_shows = await resolve_urls(data.spinitron_urls)
    if (spinitron_shows is None and not show.spinitron_show_rows) or (
        spinitron_shows is not None and not spinitron_shows
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add the show's Spinitron link",
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
                detail=f"A show named '{new_name}' already exists.",
            )
        show.name = new_name

    if data.owner_emails is not None:
        _sync_owners(db, show, data.owner_emails)

    if data.dj_names is not None:
        _sync_djs(db, show, data.dj_names)

    if data.staff_member_emails is not None:
        _sync_staff_members(db, show, data.staff_member_emails)

    if spinitron_shows is not None:
        set_spinitron_shows(db, show, spinitron_shows)

    show.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(show)
    audit_service.log_event(
        db,
        event_type="specialty_show_updated",
        area=PASS_GIVEAWAY_AREA,
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
    """Soft-delete a show (promotions staff only)."""
    show = db.query(SpecialtyShow).filter(SpecialtyShow.id == show_id).first()
    if not show:
        raise _not_found()
    show.deleted = True
    show.updated_at = datetime.now(timezone.utc)
    db.commit()
    audit_service.log_event(
        db,
        event_type="specialty_show_deleted",
        area=PASS_GIVEAWAY_AREA,
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="specialty_show",
        entity_id=show_id,
        details={"name": show.name},
    )


def _set_retired(
    db: Session, show_id: int, role_and_staff: tuple, retired: bool
) -> SpecialtyShow:
    role, actor = role_and_staff
    show = _get_editable_show(db, show_id, role, actor)
    if show.deleted:
        raise _not_found()
    if show.retired != retired:
        show.retired_at = datetime.now(timezone.utc) if retired else None
        show.updated_at = datetime.now(timezone.utc)
        db.commit()
        audit_service.log_event(
            db,
            event_type="specialty_show_retired" if retired else "specialty_show_unretired",
            area=PASS_GIVEAWAY_AREA,
            actor_email=actor.email,
            actor_role=role,
            entity_type="specialty_show",
            entity_id=show.id,
            details={"name": show.name},
        )
    db.refresh(show)
    return show


@router.post("/{show_id}/retire", response_model=SpecialtyShowResponse)
def retire_specialty_show(
    show_id: int,
    role_and_staff: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """
    Retire a show that has ended (promotions staff or show owner).

    It's kept, and its Spinitron shows still count as a specialty show, but
    passes can no longer be given to it and it's no longer suggested.
    """
    return _set_retired(db, show_id, role_and_staff, True)


@router.post("/{show_id}/unretire", response_model=SpecialtyShowResponse)
def unretire_specialty_show(
    show_id: int,
    role_and_staff: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Make a retired show current again (promotions staff or show owner)."""
    return _set_retired(db, show_id, role_and_staff, False)
