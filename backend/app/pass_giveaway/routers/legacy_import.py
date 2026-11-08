"""Legacy paper-form data import endpoints.

This router is only registered when settings.legacy_import_enabled is True.
It allows promotions staff to enter historical show data from paper forms
during the one-time cutover from the paper-based system.

To remove this feature: delete this file and the corresponding schema file
(backend/app/pass_giveaway/schemas/legacy_import.py), remove the conditional router
registration from main.py, remove the config flag from config.py, and
remove the frontend LegacyImport component and its route/nav link.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.pass_giveaway.schemas.legacy_import import (
    LegacyImportResult,
    LegacyShowImport,
    LegacyShowMerge,
    OnAirWinnerImport,
    StaffPassImport,
)
from app.auth import get_promotions_staff, ACTIVE_STATUS
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_pass_alternate import StaffPassAlternate
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.pass_giveaway.services.alternate_service import AlternateService
from app.pass_giveaway.services.entered_winners_service import (
    assign_winners_and_claims,
)
from app.pass_giveaway.services.show_service import apply_venue_rating
from app.pass_giveaway.guest_redaction import GuestRedactingRoute

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/legacy-import", tags=["legacy-import"], route_class=GuestRedactingRoute
)


def _check_venue_rules(
    venue: Venue,
    on_air_winners: list[OnAirWinnerImport],
    staff_passes: list[StaffPassImport],
    alternates: list[StaffPassImport],
) -> None:
    """Reject winners and claims that break the venue's guest list rules.

    The same rules apply when DJs record winners and staff claim passes in
    the app: some venues need each on-air winner's email address, and some
    need the name of the +1 guest of a staff member or alternate.
    """
    if venue.requires_email_address and any(
        not (w.recipient_email or "").strip() for w in on_air_winners
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{venue.name} requires an email address for every on-air winner",
        )
    if venue.staff_guest_requires_name and any(
        p.has_guest and not (p.guest_name or "").strip()
        for p in [*staff_passes, *alternates]
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{venue.name} requires a name for every staff +1 guest",
        )


def _assign_winners_and_claims(
    db: Session,
    show: Show,
    pair_pool: list[Pass],
    staff_pool: list[Pass],
    on_air_winners: list[OnAirWinnerImport],
    staff_passes: list[StaffPassImport],
    claimants: list[Staff],
    now: datetime,
) -> tuple[int, int]:
    """Assign on-air winners and staff claims onto pools of available passes.

    Mutates the given pool passes (already persisted rows, either freshly
    created or pre-existing) in place and creates OnAirWinner rows for each
    winner. Returns (on_air_winners_created, staff_passes_claimed).
    """
    assign_winners_and_claims(
        db, show, pair_pool, staff_pool, on_air_winners, staff_passes, claimants, now
    )
    return len(on_air_winners), len(staff_passes)


def _reject_alternates(db: Session, status_code: int, detail: str) -> HTTPException:
    """Undo the import in progress and build the error to raise for it."""
    db.rollback()
    return HTTPException(status_code=status_code, detail=detail)


def _add_alternates(
    db: Session,
    show: Show,
    alternates: list[StaffPassImport],
    now: datetime,
) -> int:
    """Add alternates to the end of a show's queue, in the order given (no commit).

    Called once the claims are assigned, because the queue follows the same rule
    as in the app: it only opens when staff members hold every staff pass. Waiting
    alternates would otherwise be promoted into the open or guest-held passes the
    next time the queue fills. A rejection rolls back the whole import.

    Returns the number of alternates added.
    """
    if not alternates:
        return 0

    db.flush()
    if not AlternateService.is_queue_open(db, show):
        raise _reject_alternates(
            db,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Alternates can only be added when staff members hold every staff"
            " pass: no passes left over, none held for a +1 guest, and no"
            " lottery running",
        )

    seen: set[int] = set()
    for alternate in alternates:
        staff_member = db.query(Staff).filter(Staff.id == alternate.staff_id).first()
        if not staff_member:
            raise _reject_alternates(
                db,
                status.HTTP_404_NOT_FOUND,
                f"Staff member with id {alternate.staff_id} not found",
            )
        if alternate.staff_id in seen or AlternateService.get_waiting_entry(
            db, show.id, alternate.staff_id
        ):
            raise _reject_alternates(
                db,
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{staff_member.name} is already on the alternate list",
            )
        if AlternateService._has_claim(db, show.id, alternate.staff_id):
            raise _reject_alternates(
                db,
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{staff_member.name} already has a staff pass for this show",
            )
        seen.add(alternate.staff_id)

        # Entries with the same priority_at are queued in id order, which is
        # the order they're added here.
        guest_name = (alternate.guest_name or "").strip() or None
        db.add(
            StaffPassAlternate(
                show_id=show.id,
                staff_id=alternate.staff_id,
                has_guest=alternate.has_guest,
                guest_name=guest_name if alternate.has_guest else None,
                priority_at=now,
                source="joined",
                status="waiting",
                created_at=now,
                updated_at=now,
            )
        )
    return len(alternates)


@router.get("/enabled")
def check_enabled():
    """Return enabled status for the legacy import feature.

    Always returns 200 when this router is registered (i.e. when the feature
    flag is on). The frontend uses this to decide whether to show the UI.
    """
    return {"enabled": True}


@router.post("/shows", response_model=LegacyImportResult)
def import_legacy_show(
    data: LegacyShowImport,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Import a show with on-air winners, staff passes and alternates from a paper form.

    Creates the show in "published" status so it continues to function
    normally in the system. Pass pairs that were already given away are
    recorded with their winner info; staff passes that were claimed are
    recorded with the claimant; alternates join the queue without being emailed.

    Requires promotions staff authentication.
    """
    venue = db.query(Venue).filter(Venue.id == data.venue_id).first()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venue with id {data.venue_id} not found",
        )
    _check_venue_rules(venue, data.on_air_winners, data.staff_passes, data.alternates)

    if len(data.on_air_winners) > data.num_pass_pairs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"on_air_winners count ({len(data.on_air_winners)}) exceeds"
                f" num_pass_pairs ({data.num_pass_pairs})"
            ),
        )

    # Each staff claimant with a guest consumes two passes.
    staff_slots_needed = len(data.staff_passes) + sum(
        1 for p in data.staff_passes if p.has_guest
    )
    if staff_slots_needed > data.num_pass_pairs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Staff passes requested ({staff_slots_needed} slots) exceed"
                f" num_pass_pairs ({data.num_pass_pairs})"
            ),
        )

    claimants: list[Staff] = []
    for sp in data.staff_passes:
        staff_member = db.query(Staff).filter(Staff.id == sp.staff_id).first()
        if not staff_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Staff member with id {sp.staff_id} not found",
            )
        claimants.append(staff_member)

    now = datetime.now(timezone.utc)

    show = Show(
        event_name=data.event_name,
        genre=data.genre or [],
        venue_id=data.venue_id,
        show_date=data.show_date,
        show_time=data.show_time,
        show_start_date=data.show_start_date,
        on_air_description=data.on_air_description,
        caller_special_instructions=data.caller_special_instructions,
        age_restriction=data.age_restriction,
        movie_rating=data.movie_rating,
        wheelchair_accessible=data.wheelchair_accessible,
        num_pass_pairs=data.num_pass_pairs,
        co_announce=data.co_announce,
        status="published",
        published_at=now,
    )
    apply_venue_rating(show, venue)
    db.add(show)
    db.flush()

    # Pre-create the show's pair and staff pass pools, then assign winners
    # and claims onto them.
    pair_pool: list[Pass] = []
    for _ in range(data.num_pass_pairs):
        pair_pass = Pass(
            show_id=show.id,
            pass_type="pair",
            status="available",
            created_at=now,
            updated_at=now,
        )
        db.add(pair_pass)
        pair_pool.append(pair_pass)

    staff_pool: list[Pass] = []
    for _ in range(data.num_pass_pairs):
        sp = Pass(
            show_id=show.id,
            pass_type="staff",
            status="available",
            created_at=now,
            updated_at=now,
        )
        db.add(sp)
        staff_pool.append(sp)
    db.flush()

    on_air_winners_created, staff_passes_claimed = _assign_winners_and_claims(
        db,
        show,
        pair_pool,
        staff_pool,
        data.on_air_winners,
        data.staff_passes,
        claimants,
        now,
    )
    alternates_added = _add_alternates(db, show, data.alternates, now)

    db.commit()

    logger.info(
        "Legacy import: show %d created by %s"
        " (%d on-air winners, %d staff claims, %d alternates)",
        show.id,
        promotions.email,
        on_air_winners_created,
        len(data.staff_passes),
        alternates_added,
    )

    return LegacyImportResult(
        show_id=show.id,
        on_air_winners_created=on_air_winners_created,
        staff_passes_claimed=len(data.staff_passes),
        alternates_added=alternates_added,
    )


@router.post("/shows/{show_id}/merge", response_model=LegacyImportResult)
def merge_legacy_show(
    show_id: int,
    data: LegacyShowMerge,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Backfill on-air winners, staff claims and alternates onto an existing show.

    For promotions staff who already created a show in staff-app before the
    paper-to-app cutover and now want to record paper-form winners/claims
    against it, instead of creating a duplicate show. Assigns onto the
    show's existing available passes rather than creating new ones. Drafts
    are published as part of the merge so the show works normally afterward.

    Requires promotions staff authentication.
    """
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Show with id {show_id} not found",
        )

    if show.status not in ("draft", "published"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot merge into a show with status '{show.status}'",
        )
    _check_venue_rules(show.venue, data.on_air_winners, data.staff_passes, data.alternates)

    pair_pool = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id, Pass.pass_type == "pair", Pass.status == "available"
        )
        .order_by(Pass.id)
        .all()
    )
    staff_pool = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id, Pass.pass_type == "staff", Pass.status == "available"
        )
        .order_by(Pass.id)
        .all()
    )

    if len(data.on_air_winners) > len(pair_pool):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"on_air_winners count ({len(data.on_air_winners)}) exceeds"
                f" available pair passes ({len(pair_pool)})"
            ),
        )

    # Each staff claimant with a guest consumes two passes.
    staff_slots_needed = len(data.staff_passes) + sum(
        1 for p in data.staff_passes if p.has_guest
    )
    if staff_slots_needed > len(staff_pool):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Staff passes requested ({staff_slots_needed} slots) exceed"
                f" available staff passes ({len(staff_pool)})"
            ),
        )

    claimants: list[Staff] = []
    for sp in data.staff_passes:
        staff_member = db.query(Staff).filter(Staff.id == sp.staff_id).first()
        if not staff_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Staff member with id {sp.staff_id} not found",
            )
        claimants.append(staff_member)

    now = datetime.now(timezone.utc)

    was_draft = show.status == "draft"
    if was_draft:
        show.status = "published"
        show.published_at = now

    on_air_winners_created, staff_passes_claimed = _assign_winners_and_claims(
        db,
        show,
        pair_pool,
        staff_pool,
        data.on_air_winners,
        data.staff_passes,
        claimants,
        now,
    )
    alternates_added = _add_alternates(db, show, data.alternates, now)

    db.commit()

    logger.info(
        "Legacy import: show %d merged by %s"
        " (%d on-air winners, %d staff claims, %d alternates%s)",
        show.id,
        promotions.email,
        on_air_winners_created,
        staff_passes_claimed,
        alternates_added,
        ", published from draft" if was_draft else "",
    )

    return LegacyImportResult(
        show_id=show.id,
        on_air_winners_created=on_air_winners_created,
        staff_passes_claimed=staff_passes_claimed,
        alternates_added=alternates_added,
    )


@router.get("/staff")
def list_staff(
    _: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """List all active staff members for the staff claimant and alternate pickers."""
    staff_members = (
        db.query(Staff)
        .join(StaffStatus, Staff.id == StaffStatus.staff_id)
        .filter(StaffStatus.status == ACTIVE_STATUS)
        .order_by(Staff.name)
        .all()
    )
    return [{"id": s.id, "name": s.name, "email": s.email} for s in staff_members]
