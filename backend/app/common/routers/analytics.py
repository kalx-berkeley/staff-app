"""
KALX Staff Analytics API (`/api/analytics`).

The analytics sub-site is frontend only, like KALX Staff Admin: its backend
is common, because it shows every sub-site's metrics. Each sub-site registers
its metric groups in `analytics_registry` from `main.py`.

Site admins and Promotions admins can read the metrics
(`get_site_or_promotions_admin`, checked against the real signed-in user).
Any signed-in staff member can send the active-day beacon.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.auth import get_site_or_promotions_admin, is_current_staff, require_authentication
from app.common.areas import COMMON_AREA
from app.common.schemas.analytics import (
    ActiveDayBeacon,
    AnalyticsTabResponse,
    AnalyticsWindow,
)
from app.common.services import tracking_service
from app.common.services.analytics_registry import TABS, groups_for_tab
from app.common.services.analytics_window import parse_window, today_pacific
from app.database import get_db
from app.models.analytics_event import AnalyticsEvent
from app.models.staff import Staff

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# The sub-sites the SPA can report a visit to (`frontend/src/subsites.ts`, plus
# the home page)
SUBSITES = {"home", "pass-giveaway", "directory", "workforms", "admin", "analytics"}

# Query parameters that set the window rather than being passed to the metrics
_WINDOW_PARAMS = {"preset", "from", "to"}


@router.get("/tabs/{tab}", response_model=AnalyticsTabResponse)
def get_tab(
    tab: str,
    request: Request,
    preset: Optional[str] = None,
    start: Optional[date] = Query(None, alias="from"),
    end: Optional[date] = Query(None, alias="to"),
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
) -> AnalyticsTabResponse:
    """Every metric registered for *tab*, over the requested time window."""
    if tab not in TABS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown tab")
    try:
        window = parse_window(preset, start, end)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    params = {k: v for k, v in request.query_params.items() if k not in _WINDOW_PARAMS}
    title = None
    metrics: list[dict] = []
    for group in groups_for_tab(tab):
        if title is None and group.title is not None:
            title = group.title(db, params)
        metrics.extend(group.build(db, window, params))

    return AnalyticsTabResponse(
        window=AnalyticsWindow(
            start=window.start, end=window.end, preset=window.preset, label=window.label
        ),
        title=title,
        metrics=metrics,
    )


@router.post("/beacon", status_code=status.HTTP_204_NO_CONTENT)
def record_active_day(
    body: ActiveDayBeacon,
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
) -> None:
    """
    Record that the signed-in user used *subsite* today.

    The SPA sends this on the first page load of the day in each sub-site.
    It's deduplicated here as well, so each user has at most one active day
    per sub-site per Pacific day. Nothing is recorded while impersonating, or
    for anyone who isn't current staff.
    """
    if body.subsite not in SUBSITES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown sub-site"
        )
    staff = db.query(Staff).filter(Staff.email == email).first()
    if not is_current_staff(staff):
        return
    today = today_pacific()
    already = (
        db.query(AnalyticsEvent.id)
        .filter(
            AnalyticsEvent.event_type == "active_day",
            AnalyticsEvent.actor_email == email,
            AnalyticsEvent.dimension == body.subsite,
            AnalyticsEvent.occurred_at >= tracking_service.pacific_day_start_utc(today),
            AnalyticsEvent.occurred_at
            < tracking_service.pacific_day_start_utc(today + timedelta(days=1)),
        )
        .first()
    )
    if already:
        return
    tracking_service.record_event(
        db,
        "active_day",
        area=COMMON_AREA,
        actor_email=email,
        dimension=body.subsite,
    )
