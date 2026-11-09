"""
The pass giveaway's analytics tracking: DJ studio and station office guest
sessions, "I'm off the mic" (giveaway page) visits and spin-match popups.

Only real DJ use is tracked: requests from the DJ studio network, plus, in
staging, Sublist DJ staff testing the DJ view while signed in. Promotions
staff previewing the DJ view aren't tracked.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.auth import _get_promotions_staff_by_email, _is_sublist_dj
from app.common.areas import PASS_GIVEAWAY_AREA
from app.common.services import tracking_service
from app.config import settings
from app.database import get_db
from app.models.analytics_event import AnalyticsEvent
from app.models.staff import Staff

GIVEAWAY_VISIT = "giveaway_visit"
GUEST_SESSION = "guest_session"
SPIN_MATCH_SUGGESTED = "spin_match_suggested"
SPIN_MATCH_GIVEAWAY = "spin_match_giveaway"

# A giveaway page visit's outcome, best last
OUTCOMES = ("neither", "tried", "given_away")

# What a DJ did with a spin-match popup
SPIN_ACTIONS = ("dismissed", "clicked")
SPIN_IGNORED = "ignored"

# A pass given away this soon after a popup for its show counts as following it
SPIN_GIVEAWAY_WINDOW = timedelta(hours=2)


@dataclass(frozen=True)
class DjTracking:
    """Who a tracked DJ view request is from."""

    network: Optional[str]
    actor_email: Optional[str]


def dj_tracking(
    x_forwarded_user: Optional[str] = Header(None, alias="X-Forwarded-User"),
    x_forwarded_for: Optional[str] = Header(None, alias="X-Forwarded-For"),
    x_dj_network: Optional[str] = Header(None, alias="X-DJ-Network"),
    x_station_office_network: Optional[str] = Header(
        None, alias="X-Station-Office-Network"
    ),
    db: Session = Depends(get_db),
) -> Optional[DjTracking]:
    """
    A dependency: how to track this DJ view request, or None not to track it.

    Tracked: the DJ studio network, and in staging, Sublist DJ staff (who can
    test the DJ view remotely). Not tracked: promotions staff previewing the
    DJ view, and anyone impersonating.
    """
    network = tracking_service.request_network(
        x_dj_network, x_station_office_network, x_forwarded_for
    )
    if network == tracking_service.DJ_STUDIO_NETWORK:
        return DjTracking(network=network, actor_email=None)
    if not x_forwarded_user or settings.environment != "staging":
        return None
    if tracking_service.is_impersonating(db, x_forwarded_user):
        return None
    if _get_promotions_staff_by_email(db, x_forwarded_user):
        return None
    staff = db.query(Staff).filter(Staff.email == x_forwarded_user).first()
    if staff and _is_sublist_dj(staff):
        return DjTracking(network=None, actor_email=x_forwarded_user)
    return None


def _visit(db: Session, visit_id: str) -> Optional[AnalyticsEvent]:
    return (
        db.query(AnalyticsEvent)
        .filter(AnalyticsEvent.event_type == GIVEAWAY_VISIT, AnalyticsEvent.ref == visit_id)
        .first()
    )


def start_visit(
    db: Session, tracking: DjTracking, visit_id: str, show_id: int, dj_name: Optional[str]
) -> None:
    """
    Record a giveaway page visit, or continue it after a reload.

    The page keeps its visit ID for 10 minutes in the tab, so a reload within
    that time sends the same ID and continues the same visit.
    """
    existing = _visit(db, visit_id)
    if existing:
        if existing.entity_id == show_id:
            set_visit_dj(db, visit_id, dj_name)
        return
    tracking_service.record_event(
        db,
        GIVEAWAY_VISIT,
        area=PASS_GIVEAWAY_AREA,
        actor_email=tracking.actor_email,
        network=tracking.network,
        ref=visit_id,
        entity_type="show",
        entity_id=show_id,
        dj_name=dj_name,
        dimension="neither",
    )


def set_visit_dj(db: Session, visit_id: str, dj_name: Optional[str]) -> None:
    """
    Update the DJ name a visit belongs to, from the name field at the top of
    the page. A name sent with a giveaway or "tried" click takes precedence.
    """
    visit = _visit(db, visit_id)
    if not visit or (visit.details or {}).get("dj_from_outcome"):
        return
    visit.dj_name = tracking_service.normalize_dj_name(dj_name)
    db.commit()


def record_visit_outcome(
    db: Session,
    tracking: Optional[DjTracking],
    visit_id: Optional[str],
    show_id: int,
    outcome: str,
    dj_name: Optional[str],
) -> None:
    """
    Record a giveaway or "tried" click in a visit. The visit keeps its best
    outcome (given away > tried > neither) and the DJ name sent with it.
    """
    if not visit_id or tracking is None:
        return
    visit = _visit(db, visit_id)
    if visit is None or visit.entity_id != show_id:
        # The visit's own request was lost; record the outcome as a visit
        tracking_service.record_event(
            db,
            GIVEAWAY_VISIT,
            area=PASS_GIVEAWAY_AREA,
            actor_email=tracking.actor_email,
            network=tracking.network,
            ref=visit_id if visit is None else None,
            entity_type="show",
            entity_id=show_id,
            dj_name=dj_name,
            dimension=outcome,
            details={"dj_from_outcome": True},
        )
        return
    if OUTCOMES.index(outcome) > OUTCOMES.index(visit.dimension or "neither"):
        visit.dimension = outcome
    if tracking_service.normalize_dj_name(dj_name):
        visit.dj_name = tracking_service.normalize_dj_name(dj_name)
        visit.details = {**(visit.details or {}), "dj_from_outcome": True}
    db.commit()


def record_guest_session(db: Session, network: str, session_id: str) -> None:
    """Record a DJ studio or station office guest session, once per session ID."""
    exists = (
        db.query(AnalyticsEvent.id)
        .filter(
            AnalyticsEvent.event_type == GUEST_SESSION, AnalyticsEvent.ref == session_id
        )
        .first()
    )
    if exists:
        return
    tracking_service.record_event(
        db, GUEST_SESSION, area=PASS_GIVEAWAY_AREA, network=network, ref=session_id
    )


def record_spin_suggestions(
    db: Session, tracking: Optional[DjTracking], matches: list[tuple[int, int]]
) -> None:
    """
    Record each (spin ID, show ID) match the first time any DJ client gets it.
    """
    if tracking is None or not matches:
        return
    refs = {str(spin_id) for spin_id, _ in matches}
    seen = {
        (e.ref, e.entity_id)
        for e in db.query(AnalyticsEvent.ref, AnalyticsEvent.entity_id).filter(
            AnalyticsEvent.event_type == SPIN_MATCH_SUGGESTED, AnalyticsEvent.ref.in_(refs)
        )
    }
    for spin_id, show_id in matches:
        if (str(spin_id), show_id) in seen:
            continue
        seen.add((str(spin_id), show_id))
        tracking_service.record_event(
            db,
            SPIN_MATCH_SUGGESTED,
            area=PASS_GIVEAWAY_AREA,
            actor_email=tracking.actor_email,
            network=tracking.network,
            ref=str(spin_id),
            entity_type="show",
            entity_id=show_id,
            dimension=SPIN_IGNORED,
        )


def record_spin_action(db: Session, spin_id: int, show_id: int, action: str) -> None:
    """Record whether the DJ dismissed a popup or clicked through to its show."""
    if action not in SPIN_ACTIONS:
        return
    event = (
        db.query(AnalyticsEvent)
        .filter(
            AnalyticsEvent.event_type == SPIN_MATCH_SUGGESTED,
            AnalyticsEvent.ref == str(spin_id),
            AnalyticsEvent.entity_id == show_id,
        )
        .first()
    )
    if event and event.dimension == SPIN_IGNORED:
        event.dimension = action
        db.commit()


def record_giveaway_after_suggestion(
    db: Session, tracking: Optional[DjTracking], show_id: int, pass_id: int
) -> None:
    """Record a giveaway that came within 2 hours of a popup for its show."""
    if tracking is None:
        return
    since = datetime.now(timezone.utc).replace(tzinfo=None) - SPIN_GIVEAWAY_WINDOW
    suggested = (
        db.query(AnalyticsEvent.id)
        .filter(
            AnalyticsEvent.event_type == SPIN_MATCH_SUGGESTED,
            AnalyticsEvent.entity_id == show_id,
            AnalyticsEvent.occurred_at >= since,
        )
        .first()
    )
    if suggested:
        tracking_service.record_event(
            db,
            SPIN_MATCH_GIVEAWAY,
            area=PASS_GIVEAWAY_AREA,
            actor_email=tracking.actor_email,
            network=tracking.network,
            ref=str(pass_id),
            entity_type="show",
            entity_id=show_id,
        )
