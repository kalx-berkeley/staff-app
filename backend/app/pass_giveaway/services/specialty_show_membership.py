"""Who belongs to a specialty show, and may reserve on-air passes for it.

A Specialty Music Show's members are DJ personas (`SpecialtyShowDJ`), matched
against the personas linked to a staff member, who must be a Sublist DJ to
reserve passes. A Talk &
Information show's members are staff members (`TalkShowStaff`), and any
current staff member (Active or 🆕) on the show may reserve.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth import _is_sublist_dj, is_current_staff
from app.common.services.spinitron_personas import staff_persona_ids
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_dj import SpecialtyShowDJ
from app.models.staff import Staff
from app.models.talk_show_staff import TalkShowStaff


def is_member(db: Session, show: SpecialtyShow, staff: Staff) -> bool:
    """
    Whether *staff* is a member of *show*: one of its DJs for a music show, one
    of its staff members for a talk show.
    """
    if show.is_talk:
        return (
            db.query(TalkShowStaff)
            .filter(
                TalkShowStaff.specialty_show_id == show.id,
                TalkShowStaff.staff_id == staff.id,
            )
            .first()
            is not None
        )
    persona_ids = staff_persona_ids(staff)
    if not persona_ids:
        return False
    return (
        db.query(SpecialtyShowDJ)
        .filter(
            SpecialtyShowDJ.specialty_show_id == show.id,
            SpecialtyShowDJ.persona_id.in_(persona_ids),
        )
        .first()
        is not None
    )


def member_show_ids(db: Session, staff: Staff) -> set[int]:
    """IDs of every specialty show, of either kind, that *staff* is a member of."""
    ids = {
        show_id
        for (show_id,) in db.query(TalkShowStaff.specialty_show_id).filter(
            TalkShowStaff.staff_id == staff.id
        )
    }
    ids |= dj_show_ids(db, staff)
    return ids


def dj_show_ids(db: Session, staff: Staff) -> set[int]:
    """IDs of the music shows one of *staff*'s personas is a DJ of."""
    persona_ids = staff_persona_ids(staff)
    if not persona_ids:
        return set()
    return {
        show_id
        for (show_id,) in db.query(SpecialtyShowDJ.specialty_show_id).filter(
            SpecialtyShowDJ.persona_id.in_(persona_ids)
        )
    }


def require_sublist_dj(staff: Staff) -> None:
    """Raise 403 unless *staff* is a Sublist DJ (the `get_sublist_dj_staff` rule)."""
    if not _is_sublist_dj(staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Sublist DJ staff can perform this action",
        )


def require_can_reserve_for(db: Session, show: SpecialtyShow | None, staff: Staff) -> None:
    """
    Raise unless *staff* may reserve on-air passes (or enter the DJ lottery)
    for *show*, or for themselves when *show* is None.

    Reserving for yourself or a music show needs Sublist DJ status; reserving
    for a talk show needs only current staff status. Either way, a show needs
    *staff* to be one of its members.

    :raises HTTPException: 403 if not allowed.
    """
    if show is not None and show.is_talk:
        if not is_current_staff(staff):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only current staff can reserve passes for a show",
            )
        if not is_member(db, show, staff):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a staff member of this Talk & Info Show",
            )
        return
    require_sublist_dj(staff)
    if show is not None and not is_member(db, show, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a DJ member of this Specialty Music Show",
        )
