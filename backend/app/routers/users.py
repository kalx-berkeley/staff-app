"""User API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import (
    PromotionsStaffResponse,
    StaffResponse,
    UserInfo,
    SyncResult,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from app.services.user_service import UserService
from app.services import audit_service
from app.auth import (
    require_authentication,
    is_ip_in_network,
    _get_promotions_staff_by_email,
    _is_promotions_staff,
    _staff_statuses,
    ACTIVE_STATUS,
    SUBLIST_DJ_STATUS,
)
from app.config import settings
from app.models.staff import Staff
from app.models.impersonation_session import ImpersonationSession
from app.models.notification_preferences import NotificationPreferences
from app.services.notification_service import send_email

router = APIRouter(prefix="/api/users", tags=["users"])


def determine_user_role(db: Session, email: str) -> str:
    """
    Determine user role based on database records.

    Role mapping (checked in order):
    - 'Paid Staff' + 'Active' statuses → promotions
    - 'Promotions' department + 'Active' status → promotions
    - 'Active' status → staff
    - otherwise → dj

    :param db: Database session
    :param email: User email
    :returns: User role: "promotions", "staff", or "dj"
    """
    staff = db.query(Staff).filter(Staff.email == email).first()
    if not staff:
        return "dj"

    statuses = _staff_statuses(staff)
    if ACTIVE_STATUS not in statuses:
        return "dj"

    if _is_promotions_staff(staff):
        return "promotions"

    return "staff"


@router.get("/debug/headers")
def debug_headers(request: Request):
    """Debug endpoint to inspect all incoming headers."""
    return {
        "headers": dict(request.headers),
        "client": request.client.host if request.client else None,
        "url": str(request.url),
    }


@router.get("/me", response_model=UserInfo)
def get_current_user(
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    x_forwarded_for: str | None = Header(None, alias="X-Forwarded-For"),
    x_dj_network: str | None = Header(None, alias="X-DJ-Network"),
    db: Session = Depends(get_db),
):
    """
    Get current authenticated user information.

    Returns:
        Current user info including email, role, is_dj_network,
        is_station_office_network, and profile.
        Unauthenticated requests from the DJ studio or station office network
        return role="dj".
    """
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else None
    is_dj = is_ip_in_network(client_ip, settings.dj_studio_network) if client_ip else False
    is_station_office = (
        is_ip_in_network(client_ip, settings.station_office_network) if client_ip else False
    )

    is_staging = settings.environment == "staging"

    if not x_forwarded_user:
        if is_dj or is_station_office:
            return UserInfo(
                email=None,
                role="dj",
                is_dj_network=is_dj,
                is_station_office_network=is_station_office,
                is_staging=is_staging,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Authentication required",
                "diagnostic": {
                    "x_dj_network_header": x_dj_network,
                    "x_forwarded_for_header": x_forwarded_for,
                    "client_ip": client_ip,
                    "is_dj_network": is_dj,
                    "is_station_office_network": is_station_office,
                    "dj_studio_network_config": settings.dj_studio_network,
                    "station_office_network_config": settings.station_office_network,
                },
            },
        )

    # Check for active impersonation session (staging only)
    impersonating_email = None
    is_impersonating_dj_network = False
    is_impersonating_station_office_network = False
    effective_email = x_forwarded_user
    effective_is_dj = is_dj
    effective_is_station_office = is_station_office
    imp_session = None
    if is_staging:
        imp_session = (
            db.query(ImpersonationSession)
            .filter(ImpersonationSession.real_email == x_forwarded_user)
            .first()
        )
        if imp_session:
            impersonating_email = imp_session.impersonated_email
            is_impersonating_dj_network = imp_session.impersonate_dj_network
            is_impersonating_station_office_network = (
                imp_session.impersonate_station_office_network
            )
            if impersonating_email:
                effective_email = impersonating_email
            if is_impersonating_dj_network:
                effective_is_dj = True
                effective_is_station_office = True
                if not impersonating_email:
                    # Scenario 3: DJ network only, no Google login — simulate an
                    # unauthenticated request arriving from the DJ studio network.
                    return UserInfo(
                        email=None,
                        role="dj",
                        is_dj_network=True,
                        is_station_office_network=True,
                        is_staging=is_staging,
                        real_email=x_forwarded_user,
                        is_impersonating_dj_network=True,
                    )
            if is_impersonating_station_office_network:
                effective_is_station_office = True
                if not impersonating_email and not is_impersonating_dj_network:
                    # Station office only, no login — simulate unauthenticated
                    # request arriving from the station office network.
                    return UserInfo(
                        email=None,
                        role="dj",
                        is_dj_network=False,
                        is_station_office_network=True,
                        is_staging=is_staging,
                        real_email=x_forwarded_user,
                        is_impersonating_station_office_network=True,
                    )

    role = determine_user_role(db, effective_email)

    # A Google-authenticated user who is not in the staff list and not on the DJ
    # network must not be granted DJ-level access to the site.
    if role == "dj" and x_forwarded_user is not None and not effective_is_dj:
        role = "unauthorized"

    profile = None
    if role == "promotions":
        promotions = _get_promotions_staff_by_email(db, effective_email)
        if promotions:
            profile = PromotionsStaffResponse(
                id=promotions.id,
                email=promotions.email,
                name=promotions.name or "",
                phone=promotions.phone or "",
                dj_name=promotions.dj_name,
                is_sublist_dj=SUBLIST_DJ_STATUS in _staff_statuses(promotions),
            )
    elif role == "staff":
        staff = db.query(Staff).filter(Staff.email == effective_email).first()
        if staff:
            profile = StaffResponse(
                id=staff.id,
                email=staff.email,
                name=staff.name or "",
                phone=staff.phone or "",
                dj_name=staff.dj_name,
                is_sublist_dj=SUBLIST_DJ_STATUS in _staff_statuses(staff),
            )

    return UserInfo(
        email=effective_email,
        real_email=x_forwarded_user if imp_session else None,
        role=role,
        is_dj_network=effective_is_dj,
        is_station_office_network=effective_is_station_office,
        is_staging=is_staging,
        impersonating_email=impersonating_email,
        is_impersonating_dj_network=is_impersonating_dj_network,
        is_impersonating_station_office_network=is_impersonating_station_office_network,
        profile=profile,
    )


@router.get("/profile", response_model=PromotionsStaffResponse | StaffResponse)
def get_user_profile(
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    db: Session = Depends(get_db),
):
    """Get current user's profile."""
    if not x_forwarded_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    email = x_forwarded_user
    if settings.environment == "staging":
        imp_session = (
            db.query(ImpersonationSession)
            .filter(ImpersonationSession.real_email == x_forwarded_user)
            .first()
        )
        if imp_session and imp_session.impersonated_email:
            email = imp_session.impersonated_email
    role = determine_user_role(db, email)

    if role == "promotions":
        profile = UserService.get_or_create_profile(db, email)
        return PromotionsStaffResponse(
            id=profile.id,
            email=profile.email,
            name=profile.name or "",
            phone=profile.phone or "",
            is_sublist_dj=SUBLIST_DJ_STATUS in _staff_statuses(profile),
        )
    elif role == "staff":
        profile = UserService.get_or_create_profile(db, email)
        return StaffResponse(
            id=profile.id,
            email=profile.email,
            name=profile.name or "",
            phone=profile.phone or "",
            dj_name=profile.dj_name,
            is_sublist_dj=SUBLIST_DJ_STATUS in _staff_statuses(profile),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="DJs do not have profiles"
        )


@router.post("/sync", response_model=SyncResult)
async def sync_users_from_airtable(
    email: str = Depends(require_authentication), db: Session = Depends(get_db)
):
    """Manually trigger user synchronization from Airtable (promotions staff only)."""
    role = determine_user_role(db, email)
    if role != "promotions":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only promotions staff can trigger user sync",
        )

    result = await UserService.sync_from_airtable(db)
    return result


def _get_or_create_notification_preferences(
    db: Session, email: str
) -> NotificationPreferences:
    """Return existing notification preferences for a staff member, creating defaults if absent."""
    staff = db.query(Staff).filter(Staff.email == email).first()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Notification preferences are only available to staff members",
        )
    prefs = (
        db.query(NotificationPreferences)
        .filter(NotificationPreferences.staff_id == staff.id)
        .first()
    )
    if prefs is None:
        prefs = NotificationPreferences(staff_id=staff.id, email_enabled=True)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.get("/notification-preferences", response_model=NotificationPreferencesResponse)
def get_notification_preferences(
    email: str = Depends(require_authentication), db: Session = Depends(get_db)
):
    """Get current user's notification preferences."""
    return _get_or_create_notification_preferences(db, email)


@router.put("/notification-preferences", response_model=NotificationPreferencesResponse)
def update_notification_preferences(
    updates: NotificationPreferencesUpdate,
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
):
    """Update current user's notification preferences."""
    prefs = _get_or_create_notification_preferences(db, email)
    prefs.email_enabled = updates.email_enabled
    db.commit()
    db.refresh(prefs)
    audit_service.log_event(
        db,
        event_type="notification_preferences_updated",
        actor_email=email,
        actor_role=determine_user_role(db, email),
        entity_type="staff",
        entity_id=prefs.staff_id,
        details={"email_enabled": updates.email_enabled},
    )
    return prefs


class FeedbackRequest(BaseModel):
    """Request body for user feedback submission."""

    page_url: str
    message: str


@router.post("/feedback")
def submit_feedback(
    request: FeedbackRequest,
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
):
    """
    Submit user feedback or a bug report.

    Sends an email to the configured webmaster address containing the user's
    message, their email/role, and the page they were on. Returns 503 if
    WEBMASTER_EMAIL is not configured.
    """
    if not settings.webmaster_email:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback is not configured on this server",
        )

    role = determine_user_role(db, email)
    subject = f"[KALX Promotions Feedback] from {email}"
    body = "\n".join([
        f"From: {email} (role: {role})",
        f"Page: {request.page_url}",
        "",
        "Message:",
        request.message,
    ])
    send_email(
        to_email=settings.webmaster_email,
        subject=subject,
        body_text=body,
        body_html=f"<pre>{body}</pre>",
        db=db,
    )
    return {"success": True}
