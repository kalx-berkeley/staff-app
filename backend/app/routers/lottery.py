"""Lottery API endpoints."""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_sublist_dj_staff, require_promotions_or_staff
from app.database import get_db
from app.models.lottery_entry import LotteryEntry
from app.models.show import Show
from app.models.staff import Staff
from app.schemas.lottery import (
    DJLotteryEntryCreate,
    LotteryEntryResponse,
    LotteryStatusResponse,
    StaffLotteryEntryCreate,
)
from app.services import audit_service
from app.services.lottery_service import LotteryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shows", tags=["lottery"])


@router.get("/{show_id}/lottery", response_model=LotteryStatusResponse)
def get_lottery_status(
    show_id: int,
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Get the lottery status for a show, including the current user's entry."""
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Show not found")

    is_active = LotteryService.is_lottery_active(show)
    deadline = LotteryService.get_lottery_deadline(show)

    if is_active:
        drawn = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show_id,
                LotteryEntry.status.in_(["won", "lost"]),
            )
            .first()
        ) is not None
        if drawn:
            is_active = False

    staff_count = (
        db.query(LotteryEntry)
        .filter(
            LotteryEntry.show_id == show_id,
            LotteryEntry.entry_type == "staff",
            LotteryEntry.status == "pending",
        )
        .count()
    )
    dj_count = (
        db.query(LotteryEntry)
        .filter(
            LotteryEntry.show_id == show_id,
            LotteryEntry.entry_type == "dj",
            LotteryEntry.status == "pending",
        )
        .count()
    )

    role, user = user_info
    staff_member = db.query(Staff).filter(Staff.email == user.email).first()
    my_staff_entry = None
    my_dj_entry = None

    if staff_member:
        my_staff_entry = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show_id,
                LotteryEntry.staff_id == staff_member.id,
                LotteryEntry.entry_type == "staff",
                LotteryEntry.status == "pending",
            )
            .first()
        )
        my_dj_entry = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show_id,
                LotteryEntry.staff_id == staff_member.id,
                LotteryEntry.entry_type == "dj",
                LotteryEntry.status == "pending",
            )
            .first()
        )

    # Promotions staff see all entries
    all_staff_entries = None
    all_dj_entries = None
    if role == "promotions":
        staff_entries = (
            db.query(LotteryEntry)
            .filter(LotteryEntry.show_id == show_id, LotteryEntry.entry_type == "staff")
            .order_by(LotteryEntry.entered_at)
            .all()
        )
        dj_entries = (
            db.query(LotteryEntry)
            .filter(LotteryEntry.show_id == show_id, LotteryEntry.entry_type == "dj")
            .order_by(LotteryEntry.entered_at)
            .all()
        )
        all_staff_entries = [LotteryEntryResponse.model_validate(e) for e in staff_entries]
        all_dj_entries = [LotteryEntryResponse.model_validate(e) for e in dj_entries]

    return LotteryStatusResponse(
        is_active=is_active,
        deadline=deadline,
        staff_entry_count=staff_count,
        dj_entry_count=dj_count,
        my_staff_entry=(
            LotteryEntryResponse.model_validate(my_staff_entry) if my_staff_entry else None
        ),
        my_dj_entry=(
            LotteryEntryResponse.model_validate(my_dj_entry) if my_dj_entry else None
        ),
        all_staff_entries=all_staff_entries,
        all_dj_entries=all_dj_entries,
    )


@router.post(
    "/{show_id}/lottery/enter/staff",
    response_model=LotteryEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def enter_staff_lottery(
    show_id: int,
    entry_data: StaffLotteryEntryCreate = StaffLotteryEntryCreate(),
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Enter the staff pass lottery for a show."""
    role, user = user_info
    staff_member = db.query(Staff).filter(Staff.email == user.email).first()
    if not staff_member:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only staff members can enter the lottery",
        )

    entry = LotteryService.enter_staff_lottery(
        db,
        show_id=show_id,
        staff_id=staff_member.id,
        has_guest=entry_data.has_guest,
        guest_name=entry_data.guest_name,
        only_attend_with_guest=entry_data.only_attend_with_guest,
    )
    audit_service.log_event(
        db,
        event_type="lottery_entered",
        actor_email=user.email,
        actor_role=role,
        entity_type="lottery_entry",
        entity_id=entry.id,
        details={
            "show_id": show_id,
            "entry_type": "staff",
            "has_guest": entry_data.has_guest,
            "guest_name": entry_data.guest_name,
            "only_attend_with_guest": entry_data.only_attend_with_guest,
        },
    )
    return LotteryEntryResponse.model_validate(entry)


@router.post(
    "/{show_id}/lottery/enter/dj",
    response_model=LotteryEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def enter_dj_lottery(
    show_id: int,
    entry_data: DJLotteryEntryCreate,
    staff: Staff = Depends(get_sublist_dj_staff),
    db: Session = Depends(get_db),
):
    """Enter the DJ pass-pair lottery for a show (Sublist DJ staff only)."""
    from fastapi import HTTPException
    from app.models.specialty_show import SpecialtyShow
    from app.models.specialty_show_dj import SpecialtyShowDJ

    if not staff.dj_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No DJ name is set on your profile. Contact promotions staff.",
        )
    dj_name_parts = [n.strip() for n in staff.dj_name.split(",")]

    if entry_data.dj_name_override:
        if entry_data.dj_name_override not in dj_name_parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dj_name_override must be one of your registered DJ names",
            )
        dj_name = entry_data.dj_name_override
    else:
        dj_name = dj_name_parts[0]

    specialty_show = None
    if entry_data.specialty_show_id is not None:
        specialty_show = (
            db.query(SpecialtyShow)
            .filter(
                SpecialtyShow.id == entry_data.specialty_show_id,
                SpecialtyShow.deleted == False,  # noqa: E712
            )
            .first()
        )
        if not specialty_show:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specialty show not found",
            )
        is_member = (
            db.query(SpecialtyShowDJ)
            .filter(
                SpecialtyShowDJ.specialty_show_id == specialty_show.id,
                SpecialtyShowDJ.dj_name.in_(dj_name_parts),
            )
            .first()
        )
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a DJ member of this specialty show",
            )

    entry = LotteryService.enter_dj_lottery(
        db,
        show_id=show_id,
        staff_id=staff.id,
        dj_name=dj_name,
        assignment_date=entry_data.assignment_date,
        specialty_show_id=specialty_show.id if specialty_show else None,
    )
    audit_details: dict = {"show_id": show_id, "entry_type": "dj", "dj_name": dj_name}
    if specialty_show:
        audit_details["specialty_show_id"] = specialty_show.id
        audit_details["specialty_show_name"] = specialty_show.name
    audit_service.log_event(
        db,
        event_type="lottery_entered",
        actor_email=staff.email,
        actor_role="staff",
        entity_type="lottery_entry",
        entity_id=entry.id,
        details=audit_details,
    )
    return LotteryEntryResponse.model_validate(entry)


@router.delete("/{show_id}/lottery/staff_entry", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_staff_entry(
    show_id: int,
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """Withdraw a pending staff lottery entry."""
    role, user = user_info
    staff_member = db.query(Staff).filter(Staff.email == user.email).first()
    if not staff_member:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only staff members can withdraw from the lottery",
        )
    LotteryService.withdraw_staff_entry(db, show_id=show_id, staff_id=staff_member.id)
    audit_service.log_event(
        db,
        event_type="lottery_withdrawn",
        actor_email=user.email,
        actor_role=role,
        entity_type="show",
        entity_id=show_id,
        details={"entry_type": "staff"},
    )


@router.delete("/{show_id}/lottery/dj_entry", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_dj_entry(
    show_id: int,
    staff: Staff = Depends(get_sublist_dj_staff),
    db: Session = Depends(get_db),
):
    """Withdraw a pending DJ lottery entry (Sublist DJ staff only)."""
    LotteryService.withdraw_dj_entry(db, show_id=show_id, staff_id=staff.id)
    audit_service.log_event(
        db,
        event_type="lottery_withdrawn",
        actor_email=staff.email,
        actor_role="staff",
        entity_type="show",
        entity_id=show_id,
        details={"entry_type": "dj"},
    )
