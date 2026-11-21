"""
Linked callers in Promotions → Admin: confirm that on-air winners' phone
numbers belong to one person, so venue win frequency limits check all of
them. Design: docs/pass-giveaway/specs/linked-callers/plan.md.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_site_or_promotions_admin
from app.common.schemas.types import UtcDatetime
from app.database import get_db
from app.models.staff import Staff
from app.pass_giveaway.guest_redaction import GuestRedactingRoute
from app.pass_giveaway.services import linked_callers

router = APIRouter(
    prefix="/api/pass-giveaway/admin/callers",
    tags=["pass-giveaway-admin"],
    route_class=GuestRedactingRoute,
)


class CallerPhone(BaseModel):
    phone: str
    # Each spelling it won under, latest first
    names: list[str]
    wins: int
    last_won_at: Optional[UtcDatetime] = None
    caller_id: Optional[int] = None


class SuggestionWin(BaseModel):
    pass_id: int
    won_at: UtcDatetime
    name: str
    phone: str
    email: Optional[str] = None
    show_id: int
    show: str
    show_date: Optional[date] = None
    venue: str


class Suggestion(BaseModel):
    key: str
    name: str
    spellings: list[str]
    status: str
    status_label: str
    # Two of its numbers won within a venue's win limit
    flagged: bool
    # Its spellings marked too common
    common_names: list[str]
    phones: list[CallerPhone]
    # Latest first
    wins: list[SuggestionWin]


class LinkedCaller(BaseModel):
    id: int
    note: Optional[str] = None
    created_at: UtcDatetime
    updated_at: UtcDatetime
    phones: list[CallerPhone]


class PhonesData(BaseModel):
    phones: list[str] = Field(min_length=1)


class LinkData(PhonesData):
    note: Optional[str] = None


class LinkPreview(BaseModel):
    phones: list[str]
    caller_ids: list[int]
    already_linked: bool


class NoteData(BaseModel):
    note: Optional[str] = None


class NameData(BaseModel):
    name: str


class CommonName(BaseModel):
    name: str
    marked_by: Optional[str] = None
    marked_at: UtcDatetime


class PairsResult(BaseModel):
    pairs: list[list[str]]


def _bad_request(e: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def _not_found(e: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/suggestions", response_model=list[Suggestion])
def list_suggestions(
    resolved: bool = False,
    name: Optional[str] = None,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """
    Similar-name groups of on-air winners with two or more phone numbers.
    With *resolved*, also linked, dismissed and common-name groups. With
    *name*, only the group that name belongs to, whatever its status.
    """
    return linked_callers.suggestions(db, include_resolved=resolved, name=name)


@router.get("/search", response_model=list[CallerPhone])
def search_winners(
    q: str = Query(..., min_length=2),
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Winners' phone numbers matching a name or 3 or more digits."""
    return linked_callers.search(db, q)


@router.get("/common-names", response_model=list[CommonName])
def list_common_names(
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Names marked too common to suggest linking."""
    return linked_callers.common_names(db)


@router.post("/common-names", response_model=CommonName)
def mark_common_name(
    data: NameData,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Mark a name too common to suggest linking its phone numbers."""
    try:
        return linked_callers.mark_common(db, data.name, admin.email)
    except ValueError as e:
        raise _bad_request(e)


@router.delete("/common-names/{name}", status_code=status.HTTP_204_NO_CONTENT)
def unmark_common_name(
    name: str,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Suggest linking this name's phone numbers again."""
    try:
        linked_callers.unmark_common(db, name, admin.email)
    except LookupError as e:
        raise _not_found(e)


@router.post("/dismissals", response_model=PairsResult)
def dismiss_suggestion(
    data: PhonesData,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Not the same person: stop suggesting these numbers be linked."""
    try:
        return {"pairs": linked_callers.dismiss(db, data.phones, admin.email)}
    except ValueError as e:
        raise _bad_request(e)


@router.post("/dismissals/undo", response_model=PairsResult)
def undo_dismissal(
    data: PhonesData,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Suggest these numbers again."""
    try:
        return {"pairs": linked_callers.undismiss(db, data.phones, admin.email)}
    except ValueError as e:
        raise _bad_request(e)


@router.get("", response_model=list[LinkedCaller])
def list_callers(
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Every linked caller with their phone numbers."""
    return linked_callers.callers(db)


@router.post("/preview", response_model=LinkPreview)
def preview_link(
    data: PhonesData,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Every number that linking these would put together, and the callers merged."""
    try:
        return linked_callers.preview_link(db, data.phones)
    except ValueError as e:
        raise _bad_request(e)


@router.post("", response_model=LinkedCaller)
def link_phones(
    data: LinkData,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Link phone numbers into one caller, merging any callers they're in."""
    try:
        caller = linked_callers.link(db, data.phones, data.note, admin.email)
    except ValueError as e:
        raise _bad_request(e)
    return linked_callers.caller_dict(caller, db=db)


@router.patch("/{caller_id}", response_model=LinkedCaller)
def update_note(
    caller_id: int,
    data: NoteData,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Change a linked caller's note."""
    try:
        caller = linked_callers.update_note(db, caller_id, data.note, admin.email)
    except LookupError as e:
        raise _not_found(e)
    return linked_callers.caller_dict(caller, db=db)


@router.delete("/{caller_id}/phones/{phone}", response_model=Optional[LinkedCaller])
def unlink_phone(
    caller_id: int,
    phone: str,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Take one number out of a caller. Returns null when that deleted the caller."""
    try:
        caller = linked_callers.unlink_phone(db, caller_id, phone, admin.email)
    except LookupError as e:
        raise _not_found(e)
    return linked_callers.caller_dict(caller, db=db) if caller else None


@router.delete("/{caller_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_caller(
    caller_id: int,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
):
    """Unlink all of a caller's numbers."""
    try:
        linked_callers.unlink_caller(db, caller_id, admin.email)
    except LookupError as e:
        raise _not_found(e)
