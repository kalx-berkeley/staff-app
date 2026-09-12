"""Pass API endpoints."""

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pass_schema import (
    ClaimData,
    DjSuggestion,
    GiveawayData,
    PreassignmentData,
    SelfPreassignmentData,
    PassResponse,
    WinnerReleaseData,
)
from app.services.pass_service import PassService, normalize_phone, format_phone
from app.services import audit_service
from app.services.spinitron_upcoming_schedule_service import (
    SpinitronUpcomingScheduleService,
)
from app.auth import (
    require_promotions_or_staff,
    get_promotions_staff,
    get_sublist_dj_staff,
    check_dj_access,
    check_station_office_access,
    is_ip_in_network,
    ACTIVE_STATUS,
    _is_promotions_staff,
    _staff_statuses,
)
from app.config import settings
from app.rate_limiter import create_rate_limit_dependency
from app.models.staff import Staff
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.venue import Venue
from app.models.specialty_show import SpecialtyShow

router = APIRouter(prefix="/api", tags=["passes"])

# 60 requests per 60 s per IP: allows normal office use while blocking automated scanning
_phone_search_rate_limit = create_rate_limit_dependency(max_requests=60, window_seconds=60)


def _notify_venue_owners_of_winner_release(
    db,
    show,
    winner_name: str,
    winner_phone: str,
    actor_name: str,
    actor_email: str,
    reason: str,
) -> None:
    from datetime import datetime, timezone
    from app.services import notification_service
    from app.models.notification_preferences import NotificationPreferences

    released_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = "\n".join([
        (
            f'Passes for "{show.event_name}" at {show.venue.name} on {show.show_date} have'
            " been released."
        ),
        "",
        f"Released at: {released_at}",
        f"Released by: {actor_name} <{actor_email}>",
        f"Reason: {reason}",
        "",
        f"Pass winner removed: {winner_name} ({format_phone(winner_phone)})",
        "",
        "The passes are now available to be given away again.",
    ])
    subject = f"Pass winner released: {show.event_name}"

    for owner in show.venue.owners:
        if not owner.staff:
            continue
        prefs = (
            db.query(NotificationPreferences)
            .filter(NotificationPreferences.staff_id == owner.staff.id)
            .first()
        )
        email_enabled = prefs.email_enabled if prefs else True
        if email_enabled:
            notification_service.send_email(
                to_email=owner.staff.email,
                subject=subject,
                body_text=body,
                db=db,
            )


@router.get("/shows/{show_id}/passes", response_model=list[PassResponse])
def get_show_passes(
    show_id: int,
    db: Session = Depends(get_db),
):
    """
    Get all passes for a show.

    Security enforced by check_apache_auth_layer (applied to all API routes).

    Args:
        show_id: Show ID

    Returns:
        List of passes for the show
    """
    from app.models.pass_model import Pass

    passes = db.query(Pass).filter(Pass.show_id == show_id).all()
    return [PassResponse.model_validate(pass_item) for pass_item in passes]


@router.post("/passes/{pass_id}/giveaway", response_model=PassResponse)
def give_away_pass(
    pass_id: int,
    giveaway_data: GiveawayData,
    dj_access: bool = Depends(check_dj_access),
    db: Session = Depends(get_db),
):
    """
    Give away a pass pair.

    Requires DJ access (DJ studio IP or promotions staff authentication).

    Args:
        pass_id: Pass ID
        giveaway_data: Giveaway data with recipient and DJ info
        dj_access: DJ access validation

    Returns:
        Updated pass_item
    """
    # Check winner eligibility before the giveaway to detect overrides.
    override_details: dict | None = None
    pre_pass = db.query(Pass).filter(Pass.id == pass_id).first()
    if pre_pass:
        pre_show = db.query(Show).filter(Show.id == pre_pass.show_id).first()
        if pre_show:
            pre_venue = db.query(Venue).filter(Venue.id == pre_show.venue_id).first()
            if pre_venue and pre_venue.win_frequency_days:

                previous = (
                    db.query(OnAirWinner)
                    .join(Show, Show.id == OnAirWinner.show_id)
                    .filter(
                        OnAirWinner.venue_id == pre_venue.id,
                        OnAirWinner.recipient_phone
                        == normalize_phone(giveaway_data.recipient_phone),
                    )
                    .order_by(Show.show_date.desc())
                    .first()
                )
                if previous:
                    prev_show = db.query(Show).filter(Show.id == previous.show_id).first()
                    if prev_show:
                        current_date = pre_show.show_date
                        prev_date = prev_show.show_date
                        if hasattr(current_date, "date"):
                            current_date = current_date.date()
                        if hasattr(prev_date, "date"):
                            prev_date = prev_date.date()
                        days_between = abs((current_date - prev_date).days)
                        if days_between < pre_venue.win_frequency_days:
                            override_details = {
                                "recipient_phone": giveaway_data.recipient_phone,
                                "days_since_last_win": days_between,
                                "required_days": pre_venue.win_frequency_days,
                                "last_win_show": prev_show.event_name,
                                "venue_id": pre_venue.id,
                            }

    pass_item = PassService.give_away_pass_pair(db, pass_id, giveaway_data)

    audit_service.log_event(
        db,
        event_type="pass_given_away",
        actor_role="dj",
        entity_type="pass",
        entity_id=pass_item.id,
        details={
            "dj": giveaway_data.given_away_by_dj,
            "recipient_name": giveaway_data.recipient_name,
            "recipient_phone": giveaway_data.recipient_phone,
            "show_id": pass_item.show_id,
        },
    )

    if override_details:
        audit_service.log_event(
            db,
            event_type="venue_frequency_override",
            actor_role="dj",
            entity_type="pass",
            entity_id=pass_item.id,
            details={**override_details, "dj": giveaway_data.given_away_by_dj},
        )

    return PassResponse.model_validate(pass_item)


@router.post("/passes/{pass_id}/claim", response_model=PassResponse)
def claim_pass(
    pass_id: int,
    claim_data: ClaimData = ClaimData(),
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """
    Claim a staff pass, optionally with a +1 guest reservation.

    Requires staff member or promotions staff authentication.
    Staff members are recorded as the claimant; promotions staff may claim
    without a staff record (staff_id will be null).

    When ``has_guest=True`` in the request body, a second available staff pass
    is atomically reserved as a guest hold.  If the target pass is currently a
    guest hold, the existing reservation is displaced and the original staff
    member is notified.

    Args:
        pass_id: Pass ID
        claim_data: Optional guest-claim fields
        user_info: Tuple of (role, user) from authentication
        db: Database session

    Returns:
        Updated pass_item
    """
    role, user = user_info
    if role == "staff":
        staff_id = user.id
    else:
        # Promotions staff are also in the staff table; look up by email so
        # their name is recorded on the claimed pass.
        staff_member = db.query(Staff).filter(Staff.email == user.email).first()
        staff_id = staff_member.id if staff_member else None

    # Block direct claims while lottery is active; direct claimants must enter via lottery
    target_pass = db.query(Pass).filter(Pass.id == pass_id).first()
    if target_pass:
        show = db.query(Show).filter(Show.id == target_pass.show_id).first()
        if show:
            from app.services.lottery_service import LotteryService

            if LotteryService.is_lottery_active(show):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This show has an active lottery window. Use the lottery entry"
                        " endpoint instead of claiming a pass directly."
                    ),
                )

    pass_item = PassService.claim_staff_pass(
        db,
        pass_id,
        staff_id,
        has_guest=claim_data.has_guest,
        guest_name=claim_data.guest_name,
        only_attend_with_guest=claim_data.only_attend_with_guest,
    )

    audit_service.log_event(
        db,
        event_type="pass_claimed",
        actor_email=user.email,
        actor_role=role,
        entity_type="pass",
        entity_id=pass_item.id,
        details={
            "staff_id": staff_id,
            "show_id": pass_item.show_id,
            "has_guest": claim_data.has_guest,
            "only_attend_with_guest": claim_data.only_attend_with_guest,
        },
    )

    return PassResponse.model_validate(pass_item)


@router.delete("/passes/{pass_id}/claim", response_model=PassResponse)
def release_claim(
    pass_id: int,
    user_info: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """
    Release a claimed staff pass.

    Requires staff member or promotions staff authentication.
    Show must not be closed.

    Args:
        pass_id: Pass ID
        user_info: Tuple of (role, user) from authentication
        db: Database session

    Returns:
        Updated pass
    """
    role, user = user_info
    # Snapshot the claimant before releasing
    pre_pass = db.query(Pass).filter(Pass.id == pass_id).first()
    prior_staff_id = pre_pass.staff_id if pre_pass else None

    pass_item = PassService.release_claim(db, pass_id)

    audit_service.log_event(
        db,
        event_type="pass_released",
        actor_email=user.email,
        actor_role=role,
        entity_type="pass",
        entity_id=pass_item.id,
        details={"released_staff_id": prior_staff_id, "show_id": pass_item.show_id},
    )

    return PassResponse.model_validate(pass_item)


@router.get("/passes/staff/my-giveaways", response_model=list[PassResponse])
def get_staff_my_giveaways(
    staff: Staff = Depends(get_sublist_dj_staff),
    db: Session = Depends(get_db),
):
    """
    Get Sublist DJ staff member's giveaway history using their own DJ name.

    Requires Sublist DJ status. Uses the staff member's dj_name from their profile.

    Returns:
        List of passes given away by the staff member's DJ name
    """
    if not staff.dj_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No DJ name is set on your profile. Contact promotions staff.",
        )
    dj_names = [n.strip() for n in staff.dj_name.split(",") if n.strip()]
    if not dj_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No DJ name is set on your profile. Contact promotions staff.",
        )
    passes = []
    seen_ids: set[int] = set()
    for name in dj_names:
        for pass_item in PassService.get_dj_history(db, name):
            if pass_item.id not in seen_ids:
                seen_ids.add(pass_item.id)
                passes.append(pass_item)
    return [PassResponse.model_validate(p) for p in passes]


@router.get("/passes/my-giveaways", response_model=list[PassResponse])
def get_my_giveaways(
    dj_name: str,
    dj_access: bool = Depends(check_dj_access),
    db: Session = Depends(get_db),
):
    """
    Get DJ's giveaway history.

    Requires DJ access (DJ studio IP or promotions staff authentication).

    Args:
        dj_name: DJ name to filter by
        dj_access: DJ access validation

    Returns:
        List of passes given away by the DJ
    """
    passes = PassService.get_dj_history(db, dj_name)
    return [PassResponse.model_validate(pass_item) for pass_item in passes]


@router.get("/autocomplete/djs", response_model=list[str])
def get_dj_autocomplete(
    dj_access: bool = Depends(check_dj_access), db: Session = Depends(get_db)
):
    """
    Get DJ names for autocomplete.

    Requires DJ access (DJ studio IP or promotions staff authentication).

    Args:
        dj_access: DJ access validation

    Returns:
        List of distinct DJ names
    """
    return PassService.get_dj_names_for_autocomplete(db)


@router.get("/passes/search-by-phone", response_model=list[PassResponse])
def search_passes_by_phone(
    phone: str,
    station_office_access: bool = Depends(check_station_office_access),
    _rate_limit: None = Depends(_phone_search_rate_limit),
    db: Session = Depends(get_db),
):
    """
    Search for on-air winners by phone number.

    Returns all pass pairs won by callers with that phone number.
    Requires station office network access or promotions staff authentication.

    Args:
        phone: Phone number to search for
        dj_access: DJ access validation

    Returns:
        List of passes where the given phone number won
    """
    winners = (
        db.query(OnAirWinner)
        .filter(OnAirWinner.recipient_phone == normalize_phone(phone))
        .all()
    )
    if not winners:
        return []
    pass_ids = [w.pass_id for w in winners]
    passes = db.query(Pass).filter(Pass.id.in_(pass_ids)).all()
    return [PassResponse.model_validate(p) for p in passes]


@router.post("/passes/{pass_id}/release-winner", response_model=PassResponse)
def release_winner(
    pass_id: int,
    release_data: WinnerReleaseData,
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    station_office_access: bool = Depends(check_station_office_access),
    db: Session = Depends(get_db),
):
    """
    Release a pass winner, making the passes available for re-giveaway.

    Requires station office network access or promotions staff authentication.
    The show must not be closed. Notifies venue owners via email.

    When the caller is not authenticated via Google, releasing_name and
    releasing_email must be provided in the request body.

    Args:
        pass_id: Pass ID
        release_data: Release data with reason and optional identity fields
        x_forwarded_user: Authenticated user email (set by Apache mod_auth_openidc)
        dj_access: DJ access validation

    Returns:
        Updated pass (now available)
    """
    pass_item = db.query(Pass).filter(Pass.id == pass_id).first()
    if not pass_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pass not found")
    if pass_item.pass_type != "pair":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pair passes can have winners released",
        )
    if pass_item.status != "given_away" or not pass_item.on_air_winner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pass does not have a winner assigned",
        )

    show = db.query(Show).filter(Show.id == pass_item.show_id).first()
    if show and show.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot release winner for a closed show",
        )

    if x_forwarded_user:
        staff_record = db.query(Staff).filter(Staff.email == x_forwarded_user).first()
        actor_name = staff_record.name if staff_record else x_forwarded_user
        actor_email = x_forwarded_user
    else:
        if not release_data.releasing_name or not release_data.releasing_email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "releasing_name and releasing_email are required when not authenticated"
                    " via Google"
                ),
            )
        actor_name = release_data.releasing_name
        actor_email = release_data.releasing_email

    winner = pass_item.on_air_winner
    winner_name = winner.recipient_name
    winner_phone = winner.recipient_phone

    PassService.release_on_air_winner(
        db, pass_item, release_data.reason, actor_name, actor_email, show
    )

    _notify_venue_owners_of_winner_release(
        db, show, winner_name, winner_phone, actor_name, actor_email, release_data.reason
    )

    db.refresh(pass_item)
    return PassResponse.model_validate(pass_item)


@router.get("/passes/preassign/schedule", response_model=list[str])
async def get_preassign_schedule(
    name: str = Query(..., min_length=1, max_length=100),
    role_and_staff: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """
    List upcoming dates (next ~8 weeks) that *name* is scheduled on-air.

    *name* is matched the same way the "Reserve for"/"Pre-assign to DJ"
    autocomplete conflates DJs and specialty shows: either a DJ's persona name
    or an exact specialty-show title. Used to restrict the date picker when
    pre-assigning a pass pair, so a promotions or Sublist-DJ staff member
    only sees dates the schedule actually backs up.
    """
    return await SpinitronUpcomingScheduleService.get_dates_for_name(db, name)


@router.get("/passes/preassign/suggest-by-date", response_model=list[DjSuggestion])
async def suggest_preassign_by_date(
    date: date_type = Query(...),
    role_and_staff: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """
    Suggest DJs/specialty shows scheduled on-air on *date*, for the "Suggest DJs by
    date" pre-assignment flow.

    Backed by the same cached Spinitron schedule as `/passes/preassign/schedule`,
    read in the opposite direction (date -> names instead of name -> dates).
    """
    names = await SpinitronUpcomingScheduleService.get_names_for_date(db, date.isoformat())
    specialty_names = {
        row[0].lower()
        for row in (
            db.query(SpecialtyShow.name)
            .filter(SpecialtyShow.deleted == False)  # noqa: E712
            .all()
        )
    }
    return [
        DjSuggestion(name=name, is_specialty=name.lower() in specialty_names)
        for name in names
    ]


@router.get("/passes/preassign/suggest-by-genre", response_model=list[DjSuggestion])
def suggest_preassign_by_genre(
    show_id: int = Query(...),
    role_and_staff: tuple = Depends(require_promotions_or_staff),
    db: Session = Depends(get_db),
):
    """
    Suggest active Sublist DJs (and their specialty shows) whose genre preferences
    overlap *show_id*'s genres, for the "Suggest DJs by genre" pre-assignment flow.
    """
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Show not found")
    return PassService.suggest_djs_by_genre(db, show)


@router.post("/passes/{pass_id}/preassign", response_model=PassResponse)
def set_preassignment(
    pass_id: int,
    preassignment_data: PreassignmentData,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """
    Set pre-assignment for a pass pair.

    Requires promotions staff authentication.

    Args:
        pass_id: Pass ID
        preassignment_data: Pre-assignment data with DJ name and date
        promotions: Authenticated promotions staff member

    Returns:
        Updated pass_item
    """
    pass_item = PassService.set_preassignment(
        db,
        pass_id,
        preassignment_data.dj_name,
        preassignment_data.assignment_date,
        preassigned_by_staff_id=promotions.id,
    )

    audit_service.log_event(
        db,
        event_type="pass_preassigned",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="pass",
        entity_id=pass_item.id,
        details={
            "dj": preassignment_data.dj_name,
            "assignment_date": str(preassignment_data.assignment_date),
            "show_id": pass_item.show_id,
            "preassigned_by_staff_id": promotions.id,
        },
    )

    return PassResponse.model_validate(pass_item)


@router.post("/passes/{pass_id}/preassign/self", response_model=PassResponse)
def set_self_preassignment(
    pass_id: int,
    data: SelfPreassignmentData,
    staff: Staff = Depends(get_sublist_dj_staff),
    db: Session = Depends(get_db),
):
    """
    Set pre-assignment for a pass pair to the authenticated Sublist DJ's own DJ name
    or to a specialty show they are a member of.

    Requires Sublist DJ staff authentication. The DJ name is taken from the
    staff member's own dj_name field — it cannot be set by the caller.

    Args:
        pass_id: Pass ID
        data: Pre-assignment data with assignment date and optional specialty_show_id
        staff: Authenticated Sublist DJ staff member

    Returns:
        Updated pass_item
    """
    from app.models.specialty_show import SpecialtyShow
    from app.models.specialty_show_dj import SpecialtyShowDJ

    if not staff.dj_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You do not have a DJ name set on your staff profile",
        )

    # Validate specialty show membership if reserving for a specialty show
    specialty_show = None
    if data.specialty_show_id is not None:
        specialty_show = (
            db.query(SpecialtyShow)
            .filter(
                SpecialtyShow.id == data.specialty_show_id,
                SpecialtyShow.deleted == False,  # noqa: E712
            )
            .first()
        )
        if not specialty_show:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specialty show not found",
            )
        dj_name_parts = [n.strip() for n in staff.dj_name.split(",")]
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

    # Block direct reservations while lottery is active; check prohibition window
    target_pass = db.query(Pass).filter(Pass.id == pass_id).first()
    if target_pass:
        show = db.query(Show).filter(Show.id == target_pass.show_id).first()
        if show:
            from app.services.lottery_service import LotteryService
            from datetime import date as date_type

            if LotteryService.is_lottery_active(show):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This show has an active lottery window. Use the lottery entry"
                        " endpoint instead of reserving a pass directly."
                    ),
                )

            if (
                show.dj_preassign_prohibition_days is not None
                and show.planned_close_date is not None
            ):
                assignment = data.assignment_date
                if isinstance(assignment, str):
                    assignment = date_type.fromisoformat(assignment)
                close = show.planned_close_date
                if hasattr(close, "date"):
                    close = close.date()
                days_before_close = (close - assignment).days
                if days_before_close < show.dj_preassign_prohibition_days:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Reservations are not allowed within"
                            f" {show.dj_preassign_prohibition_days} day(s) of the planned"
                            f" close date ({show.planned_close_date}). Your selected date"
                            f" ({assignment}) is only {max(days_before_close, 0)} day(s)"
                            " before the close date."
                        ),
                    )

    # Resolve the DJ name to use
    dj_name_parts = [n.strip() for n in staff.dj_name.split(",")]
    if specialty_show:
        preassign_name = specialty_show.name
    elif data.dj_name_override:
        if data.dj_name_override not in dj_name_parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dj_name_override must be one of your registered DJ names",
            )
        preassign_name = data.dj_name_override
    else:
        preassign_name = dj_name_parts[0]
    specialty_show_id = specialty_show.id if specialty_show else None

    pass_item = PassService.set_preassignment(
        db,
        pass_id,
        preassign_name,
        data.assignment_date,
        preassigned_by_staff_id=staff.id,
        preassigned_specialty_show_id=specialty_show_id,
    )

    audit_details: dict = {
        "dj": staff.dj_name,
        "assignment_date": str(data.assignment_date),
        "show_id": pass_item.show_id,
        "preassigned_by_staff_id": staff.id,
    }
    if specialty_show:
        audit_details["specialty_show_id"] = specialty_show.id
        audit_details["specialty_show_name"] = specialty_show.name

    audit_service.log_event(
        db,
        event_type="pass_preassigned",
        actor_email=staff.email,
        actor_role="staff",
        entity_type="pass",
        entity_id=pass_item.id,
        details=audit_details,
    )

    return PassResponse.model_validate(pass_item)


@router.get("/venues/{venue_id}/check-winner")
def check_winner_eligibility(
    venue_id: int,
    phone: str,
    show_id: int,
    dj_access: bool = Depends(check_dj_access),
    db: Session = Depends(get_db),
):
    """
    Check if a phone number is eligible to win passes at this venue.

    Returns eligibility status and, if ineligible, details about when the person
    last won at this venue.
    """
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")

    if not venue.win_frequency_days:
        return {"eligible": True, "reason": None}

    # Get the show date for comparison
    current_show = db.query(Show).filter(Show.id == show_id).first()
    if not current_show:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Show not found")

    # Look for a previous win at this venue by this phone number
    previous = (
        db.query(OnAirWinner)
        .join(Show, Show.id == OnAirWinner.show_id)
        .filter(
            OnAirWinner.venue_id == venue_id,
            OnAirWinner.recipient_phone == normalize_phone(phone),
        )
        .order_by(Show.show_date.desc())
        .first()
    )

    if not previous:
        return {"eligible": True, "reason": None}

    prev_show = db.query(Show).filter(Show.id == previous.show_id).first()
    if not prev_show:
        return {"eligible": True, "reason": None}

    current_show_date = current_show.show_date
    prev_show_date = prev_show.show_date

    # Handle both date and datetime objects
    if hasattr(current_show_date, "date"):
        current_show_date = current_show_date.date()
    if hasattr(prev_show_date, "date"):
        prev_show_date = prev_show_date.date()

    days_between = (current_show_date - prev_show_date).days
    if days_between < 0:
        days_between = -days_between

    if days_between < venue.win_frequency_days:
        audit_service.log_event(
            db,
            event_type="winner_frequency_warning",
            actor_role="dj",
            entity_type="venue",
            entity_id=venue_id,
            details={
                "recipient_phone": phone,
                "show_id": show_id,
                "days_since_last_win": days_between,
                "required_days": venue.win_frequency_days,
                "last_win_show": prev_show.event_name,
                "last_win_date": str(prev_show_date),
            },
        )
        return {
            "eligible": False,
            "last_win_show": prev_show.event_name,
            "last_win_date": str(prev_show_date),
            "days_since": days_between,
            "required_days": venue.win_frequency_days,
        }

    return {"eligible": True, "reason": None}


@router.delete("/passes/{pass_id}/preassign", response_model=PassResponse)
def remove_preassignment(
    pass_id: int,
    dj_name: str | None = Query(default=None),
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    x_forwarded_for: str | None = Header(None, alias="X-Forwarded-For"),
    db: Session = Depends(get_db),
):
    """
    Remove pre-assignment from a pass pair.

    Access rules:
    - Promotions staff: may remove any pre-assignment.
    - Active staff: may remove only a pre-assignment where their name (or dj_name)
      matches the preassigned_dj value.
    - DJ studio network (IP-based, no email auth): may remove only their own
      pre-assignment; must supply dj_name query param matching preassigned_dj.

    Args:
        pass_id: Pass ID
        dj_name: DJ name for self-unassign from the DJ studio network
        x_forwarded_user: Authenticated user email (set by Apache mod_auth_openidc)
        x_forwarded_for: Client IP (set by proxy)

    Returns:
        Updated pass_item
    """
    pass_pre = db.query(Pass).filter(Pass.id == pass_id).first()
    if not pass_pre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pass not found")

    prior_dj = pass_pre.preassigned_dj
    prior_date = pass_pre.preassigned_date
    actor_email: str | None = None
    actor_role: str = "dj"

    # Authenticated user path (email-based auth)
    if x_forwarded_user:
        staff_record = db.query(Staff).filter(Staff.email == x_forwarded_user).first()
        if not staff_record or ACTIVE_STATUS not in _staff_statuses(staff_record):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only promotions staff or staff members can perform this action",
            )

        if _is_promotions_staff(staff_record):
            actor_email = x_forwarded_user
            actor_role = "promotions"
        else:
            # Regular staff: verify their name (or dj_name) matches the preassigned DJ,
            # or they are a DJ member of the specialty show this pass is reserved for
            from app.models.specialty_show_dj import SpecialtyShowDJ as SpecialtyShowDJModel

            preassigned = pass_pre.preassigned_dj
            staff_names = {staff_record.name.lower()}
            if staff_record.dj_name:
                staff_names.add(staff_record.dj_name.lower())

            # Check specialty show membership if this pass is reserved for a specialty show
            allowed = preassigned and preassigned.lower() in staff_names
            if (
                not allowed
                and pass_pre.preassigned_specialty_show_id
                and staff_record.dj_name
            ):
                is_member = (
                    db.query(SpecialtyShowDJModel)
                    .filter(
                        SpecialtyShowDJModel.specialty_show_id
                        == pass_pre.preassigned_specialty_show_id,
                        SpecialtyShowDJModel.dj_name == staff_record.dj_name,
                    )
                    .first()
                )
                allowed = bool(is_member)

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only unassign your own pre-assigned passes",
                )
            actor_email = x_forwarded_user
            actor_role = "staff"

    # DJ studio network path (IP-based, no email auth)
    elif x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()
        if is_ip_in_network(client_ip, settings.dj_studio_network):
            if not dj_name:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "dj_name query parameter is required for DJ studio network access"
                    ),
                )
            preassigned = pass_pre.preassigned_dj
            if not preassigned or preassigned.lower() != dj_name.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only unassign your own pre-assigned passes",
                )
            actor_role = "dj"
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    pass_item = PassService.remove_preassignment(db, pass_pre.id)

    audit_service.log_event(
        db,
        event_type="pass_preassignment_removed",
        actor_email=actor_email,
        actor_role=actor_role,
        entity_type="pass",
        entity_id=pass_item.id,
        details={
            "prior_dj": prior_dj,
            "prior_date": str(prior_date) if prior_date else None,
            "show_id": pass_item.show_id,
            **({"dj_name": dj_name} if actor_role == "dj" else {}),
        },
    )

    return PassResponse.model_validate(pass_item)
