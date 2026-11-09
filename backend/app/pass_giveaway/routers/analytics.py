"""
Tracking endpoints for KALX Staff Analytics, called by the pass giveaway's
DJ view and station office pages.

These are open to DJ studio and station office guests on purpose (see
SECURITY.md, "Guest Access From Trusted Networks"), because that's who they
track. They only record events: they take a few short fields and return
nothing.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import check_dj_access
from app.common.services import tracking_service
from app.database import get_db
from app.pass_giveaway.guest_redaction import GuestRedactingRoute
from app.pass_giveaway.services import tracking
from app.rate_limiter import create_rate_limit_dependency

router = APIRouter(
    prefix="/api/pass-giveaway/analytics",
    tags=["pass-giveaway-analytics"],
    route_class=GuestRedactingRoute,
)

_tracking_rate_limit = create_rate_limit_dependency(
    max_requests=120, window_seconds=60, scope="pass_giveaway_tracking"
)

_ID_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


class GuestSessionRequest(BaseModel):
    session_id: str = Field(..., pattern=_ID_PATTERN)


class GiveawayVisitRequest(BaseModel):
    visit_id: str = Field(..., pattern=_ID_PATTERN)
    show_id: int
    dj_name: Optional[str] = Field(None, max_length=100)


class VisitDjRequest(BaseModel):
    dj_name: Optional[str] = Field(None, max_length=100)


@router.post("/session", status_code=status.HTTP_204_NO_CONTENT)
def record_guest_session(
    body: GuestSessionRequest,
    x_forwarded_user: Optional[str] = Header(None, alias="X-Forwarded-User"),
    x_forwarded_for: Optional[str] = Header(None, alias="X-Forwarded-For"),
    x_dj_network: Optional[str] = Header(None, alias="X-DJ-Network"),
    x_station_office_network: Optional[str] = Header(
        None, alias="X-Station-Office-Network"
    ),
    _rate_limit: None = Depends(_tracking_rate_limit),
    db: Session = Depends(get_db),
) -> None:
    """
    Record a DJ studio or station office guest session.

    The page starts a session per tab, and a new one after 30 minutes idle.
    Signed-in users are counted by their active days instead, so this does
    nothing for them.
    """
    if x_forwarded_user:
        return
    network = tracking_service.request_network(
        x_dj_network, x_station_office_network, x_forwarded_for
    )
    if network:
        tracking.record_guest_session(db, network, body.session_id)


@router.post("/giveaway-visits", status_code=status.HTTP_204_NO_CONTENT)
def record_giveaway_visit(
    body: GiveawayVisitRequest,
    dj_access: bool = Depends(check_dj_access),
    dj: Optional[tracking.DjTracking] = Depends(tracking.dj_tracking),
    _rate_limit: None = Depends(_tracking_rate_limit),
    db: Session = Depends(get_db),
) -> None:
    """Record a visit to a show's "I'm off the mic" page, or continue it after a reload."""
    if dj is not None:
        tracking.start_visit(db, dj, body.visit_id, body.show_id, body.dj_name)


@router.put("/giveaway-visits/{visit_id}/dj", status_code=status.HTTP_204_NO_CONTENT)
def set_giveaway_visit_dj(
    visit_id: str,
    body: VisitDjRequest,
    dj_access: bool = Depends(check_dj_access),
    dj: Optional[tracking.DjTracking] = Depends(tracking.dj_tracking),
    _rate_limit: None = Depends(_tracking_rate_limit),
    db: Session = Depends(get_db),
) -> None:
    """Update the visit's DJ from the DJ name field at the top of the page."""
    if dj is not None and len(visit_id) <= 64:
        tracking.set_visit_dj(db, visit_id, body.dj_name)
