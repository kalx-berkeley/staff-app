"""On-air DJ schedule API endpoints."""

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import check_dj_access
from app.database import get_db
from app.pass_giveaway.schemas.on_air import (
    OnAirIdentity as OnAirIdentitySchema,
    OnAirResponse,
    SpinMatch as SpinMatchSchema,
    SpinMatchShow,
)
from app.pass_giveaway.services.on_air_identity import on_air
from app.pass_giveaway.services.spin_match_service import SpinMatchService
from app.pass_giveaway.services.tracking import (
    DjTracking,
    dj_tracking,
    record_spin_action,
    record_spin_suggestions,
)
from app.pass_giveaway.guest_redaction import GuestRedactingRoute

router = APIRouter(prefix="/api/dj", tags=["dj"], route_class=GuestRedactingRoute)


def _identity(identity) -> Optional[OnAirIdentitySchema]:
    return OnAirIdentitySchema(**asdict(identity)) if identity is not None else None


@router.get("/on-air", response_model=OnAirResponse)
async def get_on_air(
    dj_access: bool = Depends(check_dj_access),
    db: Session = Depends(get_db),
):
    """
    Who is on air now and next, from the cached Spinitron schedule and recent
    spins (see `on_air_identity`).
    """
    now = datetime.now(timezone.utc)
    state = await on_air(db, now)
    current, upcoming = state.current, state.next
    return OnAirResponse(
        current=_identity(state.identity),
        current_automation=current.automation if current else False,
        current_title=current.title if current else None,
        current_ends_at=current.end if current else None,
        next=_identity(upcoming.identity if upcoming else None),
        next_starts_at=upcoming.start if upcoming else None,
        can_switch_early=state.can_switch_early(now),
    )


@router.get("/spin-matches", response_model=list[SpinMatchSchema])
async def get_spin_matches(
    dj_access: bool = Depends(check_dj_access),
    dj: Optional[DjTracking] = Depends(dj_tracking),
    db: Session = Depends(get_db),
):
    """Return current spins that match a show with passes to give away.

    Meant to be polled roughly once a minute from the DJ view. Every current
    match is returned on every call — including to every other open DJ tab —
    until the caller dismisses it (or clicks through) via
    POST /spin-matches/{spin_id}/dismiss, so the DJ view is responsible for
    not re-displaying a match it's already shown.
    """
    matches = await SpinMatchService.get_current_matches(db)
    # KALX Staff Analytics counts each match once, the first time it's offered
    record_spin_suggestions(db, dj, [(m.spin_id, m.show.id) for m in matches])
    return [
        SpinMatchSchema(
            spin_id=m.spin_id,
            artist=m.artist,
            song=m.song,
            image=m.image,
            show=SpinMatchShow(
                id=m.show.id,
                event_name=m.show.event_name,
                venue_name=m.show.venue.name,
                show_date=m.show.show_date,
            ),
        )
        for m in matches
    ]


@router.post("/spin-matches/{spin_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_spin_match(
    spin_id: int,
    show_id: int,
    action: Optional[Literal["dismissed", "clicked"]] = None,
    dj_access: bool = Depends(check_dj_access),
    db: Session = Depends(get_db),
):
    """Mark one spin/show match as dismissed so it stops being returned.

    Called when a DJ dismisses a spin-match toast or clicks through to the
    show. Takes effect for every open DJ tab, not just the caller's, as soon
    as each tab's next GET /spin-matches poll runs. A spin_id that matched
    multiple shows needs one call per show_id — dismissing one leaves the
    others showing.

    *action* says whether the DJ dismissed the popup or clicked through, for
    KALX Staff Analytics.
    """
    SpinMatchService.dismiss(db, spin_id=spin_id, show_id=show_id)
    if action:
        record_spin_action(db, spin_id, show_id, action)
