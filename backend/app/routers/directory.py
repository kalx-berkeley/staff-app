"""Staff Directory API endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.auth import ACTIVE_STATUS, get_staff_member
from app.database import get_db
from app.models.staff import Staff
from app.models.staff_status import StaffStatus
from app.rate_limiter import create_rate_limit_dependency
from app.schemas.directory import DirectoryEntry, DjPersona
from app.services.staff_photo_service import photo_path

router = APIRouter(prefix="/api/directory", tags=["directory"])

# The list holds every active staff member's contact details, so it's rate
# limited to discourage scraping. A page load makes one request.
_directory_rate_limit = create_rate_limit_dependency(
    max_requests=30, window_seconds=60, scope="directory"
)


def _active_staff_query(db: Session):
    return (
        db.query(Staff)
        .join(StaffStatus, Staff.id == StaffStatus.staff_id)
        .filter(StaffStatus.status == ACTIVE_STATUS)
    )


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
    List every active staff member, sorted by name. Active staff only.

    :returns: Directory entries for all active staff.
    """
    staff_members = (
        _active_staff_query(db)
        .options(selectinload(Staff.departments), selectinload(Staff.statuses))
        .all()
    )
    staff_members.sort(key=lambda s: s.name.casefold())
    return [
        DirectoryEntry(
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
        )
        for s in staff_members
    ]


@router.get("/{staff_id}/photo")
def get_photo(
    staff_id: int,
    size: Literal["thumb", "medium"] = Query("thumb"),
    _viewer: Staff = Depends(get_staff_member),
    db: Session = Depends(get_db),
):
    """
    Return an active staff member's directory photo. Active staff only.

    The response may be cached, since the directory links to it with the
    photo's version in the query string.

    :param staff_id: Staff ID.
    :param size: "thumb" (a square crop) or "medium".
    :raises HTTPException: 404 if the staff member isn't active or has no photo.
    """
    staff_member = _active_staff_query(db).filter(Staff.id == staff_id).first()
    path = photo_path(staff_id, size)
    if not staff_member or not staff_member.photo_attachment_id or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photo")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=604800"},
    )
