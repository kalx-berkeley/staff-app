"""Staff Directory API endpoints."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.auth import (
    current_staff_filter,
    get_staff_member,
    is_paid_staff,
    is_site_admin,
    require_authentication,
)
from app.config import settings
from app.database import get_db
from app.models.staff import Staff
from app.rate_limiter import create_rate_limit_dependency
from app.directory.schemas.directory import (
    DirectoryEntry,
    DjPersona,
    PersonaOption,
    PersonaResolveRequest,
    ProfileResponse,
    ProfileUpdate,
)
from app.directory.services import profile as profile_service
from app.common.services.leave_service import (
    has_leave,
    leave_is_current_or_upcoming,
    on_leave,
    today_pt,
)
from app.common.services.staff_photo_service import photo_path

router = APIRouter(prefix="/api/directory", tags=["directory"])

# The list holds every current staff member's contact details, so it's rate
# limited to discourage scraping. A page load makes one request.
_directory_rate_limit = create_rate_limit_dependency(
    max_requests=30, window_seconds=60, scope="directory"
)


def _current_staff_query(db: Session):
    """Staff with the "Active" or "🆕" status."""
    return db.query(Staff).filter(current_staff_filter())


def _dj_personas(staff: Staff) -> list[DjPersona]:
    """
    A staff member's Spinitron personas, each with its DJ name.

    Records not yet re-synced since dj_personas was added only have the
    comma-joined dj_name, which can be split back up when there's one name per
    persona ID.

    :param staff: The staff member.
    :returns: The staff member's personas, in Airtable order.
    """
    if staff.dj_personas is not None:
        return [DjPersona(**persona) for persona in staff.dj_personas]
    ids = staff.spinitron_ids or []
    if not ids or not staff.dj_name:
        return []
    names = [staff.dj_name] if len(ids) == 1 else staff.dj_name.split(", ")
    if len(names) != len(ids):
        return []
    return [DjPersona(id=pid, name=name) for pid, name in zip(ids, names)]


# An Airtable "Status" value, separate from the LOA dates.
_ON_LEAVE_STATUS = "on leave"


def _leave_fields(staff: Staff, today: date) -> dict:
    """
    The directory's leave-of-absence fields.

    Empty unless the leave hasn't ended, or the staff member has an "On leave"
    status (matched ignoring case), in which case their leave dates are shown
    whenever they're on record, so the detail panel can say when the leave is.

    :param staff: The staff member, with statuses loaded.
    :param today: Today's date in Pacific time.
    """
    if not has_leave(staff):
        return {}
    has_leave_status = any(
        st.status.casefold() == _ON_LEAVE_STATUS for st in staff.statuses
    )
    if not has_leave_status and not leave_is_current_or_upcoming(staff, today):
        return {}
    return {
        "on_leave": on_leave(staff, today),
        "loa_start": staff.loa_start,
        "loa_end": staff.loa_end,
    }


def _entry(s: Staff, today: date) -> DirectoryEntry:
    """A staff member's directory entry, as everyone sees it."""
    return DirectoryEntry(
        id=s.id,
        name=s.name,
        pronouns=s.pronouns,
        email=s.email,
        phone=s.phone,
        dj_name=s.dj_name,
        dj_personas=_dj_personas(s),
        departments=sorted(d.department for d in s.departments),
        statuses=sorted(st.status for st in s.statuses),
        titles_and_roles=s.titles_and_roles,
        photo_version=s.photo_attachment_id,
        dj_quiz_years=s.dj_quiz_years or [],
        **_leave_fields(s, today),
    )


@router.get(
    "",
    response_model=list[DirectoryEntry],
    dependencies=[Depends(_directory_rate_limit)],
)
def list_directory(
    _viewer: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    """
    List every current (Active or 🆕) staff member, sorted by name. Current
    staff only.

    :returns: Directory entries for all current staff.
    """
    staff_members = (
        _current_staff_query(db)
        .options(selectinload(Staff.departments), selectinload(Staff.statuses))
        .all()
    )
    staff_members.sort(key=lambda s: s.name.casefold())
    today = today_pt()
    return [_entry(s, today) for s in staff_members]


@router.get("/{staff_id}/photo")
def get_photo(
    staff_id: int,
    size: Literal["thumb", "medium"] = Query("thumb"),
    _viewer: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    """
    Return a current staff member's directory photo. Current staff only.

    The response may be cached, since the directory links to it with the
    photo's version in the query string.

    :param staff_id: Staff ID.
    :param size: "thumb" (a square crop) or "medium".
    :raises HTTPException: 404 if the staff member isn't current staff or has no photo.
    """
    staff_member = _current_staff_query(db).filter(Staff.id == staff_id).first()
    path = photo_path(staff_id, size)
    if not staff_member or not staff_member.photo_attachment_id or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photo")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=604800"},
    )


# --- Profile page ----------------------------------------------------------


def _real_user(db: Session, email: str) -> Staff | None:
    """The real, signed-in user, never someone they're impersonating."""
    return db.query(Staff).filter(Staff.email == email).first()


def _profile_target(
    db: Session, staff_id: int, viewer: Staff, email: str, editing: bool = False
) -> tuple[Staff, bool]:
    """
    The current staff member whose profile is wanted, and whether it's the
    viewer's own. Only they and site admins may see it, and only they and
    Paid Staff may edit it.

    The viewer is who the user is acting as (someone they're impersonating,
    on staging); the site admin and Paid Staff checks use the real, signed-in
    user.

    :raises HTTPException: 403 for anyone else, 404 if they aren't current staff.
    """
    is_self = viewer.id == staff_id
    if not is_self:
        real_user = _real_user(db, email)
        if editing and not is_paid_staff(real_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only this staff member and Paid Staff can edit this profile",
            )
        if not is_site_admin(db, real_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only this staff member and site admins can see this profile",
            )
    staff = _current_staff_query(db).filter(Staff.id == staff_id).first()
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return staff, is_self


def _profile(db: Session, staff: Staff, is_self: bool, email: str) -> ProfileResponse:
    return ProfileResponse(
        entry=_entry(staff, today_pt()),
        first_name=staff.first_name,
        surname=staff.surname,
        loa_start=staff.loa_start,
        loa_end=staff.loa_end,
        is_self=is_self,
        can_edit=settings.directory_self_edit_enabled
        and (is_self or is_paid_staff(_real_user(db, email))),
        eligibility=(
            profile_service.build_eligibility(db, staff)
            if profile_service.shows_eligibility(staff)
            else None
        ),
        workforms=profile_service.build_workforms_summary(db, staff),
    )


@router.get("/me/profile", response_model=ProfileResponse)
def get_my_profile(
    viewer: Staff = Depends(get_staff_member),
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
):
    """The user's own profile page."""
    return _profile(db, viewer, True, email)


@router.get("/{staff_id}/profile", response_model=ProfileResponse)
def get_profile(
    staff_id: int,
    viewer: Staff = Depends(get_staff_member),
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
):
    """A staff member's profile page. Only they and site admins can see it."""
    staff, is_self = _profile_target(db, staff_id, viewer, email)
    return _profile(db, staff, is_self, email)


@router.patch("/{staff_id}/profile", response_model=ProfileResponse)
async def update_profile(
    staff_id: int,
    update: ProfileUpdate,
    viewer: Staff = Depends(get_staff_member),
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
):
    """
    Save a staff member's editable details to Airtable. Only they and Paid
    Staff can, and only once editing is turned on
    (DIRECTORY_SELF_EDIT_ENABLED).
    """
    staff, is_self = _profile_target(db, staff_id, viewer, email, editing=True)
    profile_service.require_editing_enabled()
    await profile_service.update_profile(db, staff, update, email)
    db.refresh(staff)
    return _profile(db, staff, is_self, email)


@router.post("/{staff_id}/photo", response_model=ProfileResponse)
async def upload_photo(
    staff_id: int,
    photo: UploadFile = File(...),
    viewer: Staff = Depends(get_staff_member),
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
):
    """
    Replace a staff member's photo (JPEG or PNG, at most 5 MB). Same access
    as editing the profile.
    """
    staff, is_self = _profile_target(db, staff_id, viewer, email, editing=True)
    profile_service.require_editing_enabled()
    # Read one byte past the limit, so a larger file is refused without
    # reading it all
    data = await photo.read(profile_service.MAX_PHOTO_BYTES + 1)
    await profile_service.replace_photo(
        db, staff, photo.filename or "photo", photo.content_type, data, email
    )
    db.refresh(staff)
    return _profile(db, staff, is_self, email)


@router.get("/personas", response_model=list[PersonaOption])
async def search_personas(
    q: str = Query("", max_length=100),
    _viewer: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    """
    Spinitron personas whose name contains *q* (ignoring case), for the DJ
    Name editor. Placeholder personas are left out. At most 20.
    """
    needle = q.strip().casefold()
    if not needle:
        return []
    names = await profile_service.persona_names(db)
    matches = [
        PersonaOption(id=pid, name=name)
        for pid, name in names.items()
        if needle in name.casefold()
    ]
    matches.sort(
        key=lambda p: (not p.name.casefold().startswith(needle), p.name.casefold())
    )
    return matches[:20]


@router.post("/personas/resolve", response_model=PersonaOption)
async def resolve_persona(
    request: PersonaResolveRequest,
    _viewer: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    """The persona a pasted Spinitron DJ link points to."""
    persona_id, name = await profile_service.resolve_persona_url(db, request.url)
    return PersonaOption(id=persona_id, name=name)
