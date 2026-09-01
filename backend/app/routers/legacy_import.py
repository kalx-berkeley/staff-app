"""Legacy paper-form data import endpoints.

This router is only registered when settings.legacy_import_enabled is True.
It allows promotions staff to enter historical show data from paper forms
during the one-time cutover from the paper-based system.

To remove this feature: delete this file and the corresponding schema file
(backend/app/schemas/legacy_import.py), remove the conditional router
registration from main.py, remove the config flag from config.py, and
remove the frontend LegacyImport component and its route/nav link.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.legacy_import import LegacyImportResult, LegacyShowImport
from app.auth import get_promotions_staff
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.venue import Venue
from app.services.pass_service import normalize_phone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/legacy-import", tags=["legacy-import"])


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
    """Import a show with on-air winners and staff passes from a paper form.

    Creates the show in "published" status so it continues to function
    normally in the system. Pass pairs that were already given away are
    recorded with their winner info; staff passes that were claimed are
    recorded with the claimant.

    Requires promotions staff authentication.
    """
    venue = db.query(Venue).filter(Venue.id == data.venue_id).first()
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venue with id {data.venue_id} not found",
        )

    if len(data.on_air_winners) > data.num_pass_pairs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
        wheelchair_accessible=data.wheelchair_accessible,
        num_pass_pairs=data.num_pass_pairs,
        co_announce=data.co_announce,
        status="published",
        published_at=now,
    )
    db.add(show)
    db.flush()

    # Create pair passes and record on-air winners.
    on_air_winners_created = 0
    for i in range(data.num_pass_pairs):
        pair_pass = Pass(
            show_id=show.id,
            pass_type="pair",
            status="available",
            created_at=now,
            updated_at=now,
        )
        if i < len(data.on_air_winners):
            winner_data = data.on_air_winners[i]
            pair_pass.status = "given_away"
            pair_pass.given_away_by_dj = winner_data.given_away_by_dj or "Unknown"
            pair_pass.given_away_at = now
        db.add(pair_pass)
        db.flush()

        if i < len(data.on_air_winners):
            winner_data = data.on_air_winners[i]
            winner = OnAirWinner(
                pass_id=pair_pass.id,
                venue_id=data.venue_id,
                show_id=show.id,
                recipient_name=winner_data.recipient_name,
                recipient_phone=normalize_phone(winner_data.recipient_phone),
                recipient_email=winner_data.recipient_email,
                given_away_by_dj=winner_data.given_away_by_dj or "Unknown",
                created_at=now,
            )
            db.add(winner)
            on_air_winners_created += 1

    # Create staff passes, claiming them as needed and creating guest holds.
    # We pre-create all num_pass_pairs passes as a pool, then assign them.
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

    pool_idx = 0
    for i, sp_data in enumerate(data.staff_passes):
        primary = staff_pool[pool_idx]
        pool_idx += 1

        primary.status = "claimed"
        primary.staff_id = claimants[i].id
        primary.claimed_at = now
        primary.has_guest = sp_data.has_guest
        primary.guest_name = sp_data.guest_name if sp_data.has_guest else None
        primary.updated_at = now

        if sp_data.has_guest:
            guest_hold = staff_pool[pool_idx]
            pool_idx += 1
            guest_hold.status = "claimed"
            guest_hold.staff_id = claimants[i].id
            guest_hold.claimed_at = now
            guest_hold.guest_of_pass_id = primary.id
            guest_hold.updated_at = now

    db.commit()

    logger.info(
        "Legacy import: show %d created by %s (%d on-air winners, %d staff claims)",
        show.id,
        promotions.email,
        on_air_winners_created,
        len(data.staff_passes),
    )

    return LegacyImportResult(
        show_id=show.id,
        on_air_winners_created=on_air_winners_created,
        staff_passes_claimed=len(data.staff_passes),
    )


@router.get("/staff")
def list_staff(
    _: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """List all active staff members for the staff claimant picker."""
    staff_members = db.query(Staff).order_by(Staff.name).all()
    return [{"id": s.id, "name": s.name, "email": s.email} for s in staff_members]
