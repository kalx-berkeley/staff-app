"""On-air DJ schedule API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import check_dj_access
from app.database import get_db
from app.models.spinitron_show import SpinitronShow
from app.schemas.on_air import OnAirResponse, SpinMatch as SpinMatchSchema, SpinMatchShow
from app.services.spin_match_service import SpinMatchService

router = APIRouter(prefix="/api/dj", tags=["dj"])


@router.get("/on-air", response_model=OnAirResponse)
def get_on_air(
    dj_access: bool = Depends(check_dj_access),
    db: Session = Depends(get_db),
):
    """Return the currently and next scheduled on-air DJ from the cached Spinitron schedule."""
    now = datetime.now(timezone.utc)

    current = (
        db.query(SpinitronShow)
        .filter(SpinitronShow.start <= now, SpinitronShow.end > now)
        .order_by(SpinitronShow.start.desc())
        .first()
    )
    next_show = (
        db.query(SpinitronShow)
        .filter(SpinitronShow.start >= (current.end if current else now))
        .order_by(SpinitronShow.start.asc())
        .first()
    )

    return OnAirResponse(
        current_dj_name=current.dj_name if current else None,
        current_show_ends_at=current.end if current else None,
        next_dj_name=next_show.dj_name if next_show else None,
    )


@router.get("/spin-matches", response_model=list[SpinMatchSchema])
async def get_spin_matches(
    dj_access: bool = Depends(check_dj_access),
    db: Session = Depends(get_db),
):
    """Return not-yet-surfaced spins that match a show with passes to give away.

    Meant to be polled roughly once a minute from the DJ view. Each match is
    returned at most once ever (see SpinMatchService/SurfacedSpinMatch) so
    the caller can pop up a notification for it without tracking its own
    dedup state.
    """
    matches = await SpinMatchService.check_for_matches(db)
    return [
        SpinMatchSchema(
            spin_id=m.spin_id,
            artist=m.artist,
            song=m.song,
            image=m.image,
            show=SpinMatchShow(
                id=m.show.id, event_name=m.show.event_name, show_date=m.show.show_date
            ),
        )
        for m in matches
    ]
