"""On-air DJ schedule API endpoints."""

from datetime import datetime, timezone
from typing import Optional, Union

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import check_dj_access
from app.database import get_db
from app.models.spinitron_playlist import SpinitronPlaylist
from app.models.spinitron_show import SpinitronShow
from app.schemas.on_air import OnAirResponse, SpinMatch as SpinMatchSchema, SpinMatchShow
from app.services.spin_match_service import SpinMatchService

router = APIRouter(prefix="/api/dj", tags=["dj"])

_ScheduleRow = Union[SpinitronShow, SpinitronPlaylist]


def _earliest_preferring_playlist(
    playlist: Optional[SpinitronPlaylist], show: Optional[SpinitronShow]
) -> Optional[_ScheduleRow]:
    """Pick whichever entry starts first; prefer the playlist on an exact tie."""
    if playlist is None:
        return show
    if show is None:
        return playlist
    return playlist if playlist.start <= show.start else show


@router.get("/on-air", response_model=OnAirResponse)
def get_on_air(
    dj_access: bool = Depends(check_dj_access),
    db: Session = Depends(get_db),
):
    """Return the currently and next scheduled on-air DJ from the cached Spinitron schedule.

    Spinitron's `/shows` and `/playlists` can disagree about who's on at a
    given instant — `/shows` often lists a generic placeholder while
    `/playlists` already has a specific DJ's pre-provisioned playlist for
    the same slot. When both are scheduled for the same instant, the
    playlist is preferred as the more specific answer.
    """
    now = datetime.now(timezone.utc)

    current: Optional[_ScheduleRow] = (
        db.query(SpinitronPlaylist)
        .filter(SpinitronPlaylist.start <= now, SpinitronPlaylist.end > now)
        .order_by(SpinitronPlaylist.start.desc())
        .first()
    ) or (
        db.query(SpinitronShow)
        .filter(SpinitronShow.start <= now, SpinitronShow.end > now)
        .order_by(SpinitronShow.start.desc())
        .first()
    )

    boundary = current.end if current else now
    next_playlist = (
        db.query(SpinitronPlaylist)
        .filter(SpinitronPlaylist.start >= boundary)
        .order_by(SpinitronPlaylist.start.asc())
        .first()
    )
    next_show = (
        db.query(SpinitronShow)
        .filter(SpinitronShow.start >= boundary)
        .order_by(SpinitronShow.start.asc())
        .first()
    )
    next_entry = _earliest_preferring_playlist(next_playlist, next_show)

    return OnAirResponse(
        current_dj_name=current.dj_name if current else None,
        current_show_ends_at=current.end if current else None,
        next_dj_name=next_entry.dj_name if next_entry else None,
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
                id=m.show.id,
                event_name=m.show.event_name,
                venue_name=m.show.venue.name,
                show_date=m.show.show_date,
            ),
        )
        for m in matches
    ]
