"""On-air DJ schedule API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import check_dj_access
from app.database import get_db
from app.models.spinitron_show import SpinitronShow
from app.schemas.on_air import OnAirResponse

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
