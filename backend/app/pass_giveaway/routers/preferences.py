"""
Pass giveaway preference endpoints under /api/users: whether a staff member
gets pass emails, and which genres they like (used to suggest DJs for passes).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_authentication, resolve_effective_email
from app.common.routers.users import determine_user_role
from app.common.services import audit_service
from app.database import get_db
from app.models.notification_preferences import NotificationPreferences
from app.models.staff import Staff
from app.models.staff_genre_preference import StaffGenrePreference
from app.pass_giveaway.schemas.preferences import (
    GenrePreferencesResponse,
    GenrePreferencesUpdate,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from app.pass_giveaway.guest_redaction import GuestRedactingRoute

router = APIRouter(prefix="/api/users", tags=["users"], route_class=GuestRedactingRoute)


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
    """
    Get current user's notification preferences.

    In staging, resolves any active impersonation session first, so a
    promotions staff member impersonating a staff account sees that staff
    member's notification preferences instead of their own.
    """
    return _get_or_create_notification_preferences(db, resolve_effective_email(email, db))


@router.put("/notification-preferences", response_model=NotificationPreferencesResponse)
def update_notification_preferences(
    updates: NotificationPreferencesUpdate,
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
):
    """
    Update current user's notification preferences.

    In staging, resolves any active impersonation session first, so a
    promotions staff member impersonating a staff account edits that staff
    member's notification preferences instead of their own.
    """
    effective_email = resolve_effective_email(email, db)
    prefs = _get_or_create_notification_preferences(db, effective_email)
    prefs.email_enabled = updates.email_enabled
    db.commit()
    db.refresh(prefs)
    audit_service.log_event(
        db,
        event_type="notification_preferences_updated",
        actor_email=effective_email,
        actor_role=determine_user_role(db, effective_email),
        entity_type="staff",
        entity_id=prefs.staff_id,
        details={"email_enabled": updates.email_enabled},
    )
    return prefs


def _get_or_create_genre_preferences(db: Session, email: str) -> StaffGenrePreference:
    """Return existing genre preferences for a staff member, creating defaults if absent."""
    staff = db.query(Staff).filter(Staff.email == email).first()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Genre preferences are only available to staff members",
        )
    prefs = (
        db.query(StaffGenrePreference)
        .filter(StaffGenrePreference.staff_id == staff.id)
        .first()
    )
    if prefs is None:
        prefs = StaffGenrePreference(staff_id=staff.id, genres=[])
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.get("/genre-preferences", response_model=GenrePreferencesResponse)
def get_genre_preferences(
    email: str = Depends(require_authentication), db: Session = Depends(get_db)
):
    """
    Get current user's genre preferences.

    In staging, resolves any active impersonation session first, so a
    promotions staff member impersonating a staff account sees that staff
    member's genre preferences instead of their own.
    """
    return _get_or_create_genre_preferences(db, resolve_effective_email(email, db))


@router.put("/genre-preferences", response_model=GenrePreferencesResponse)
def update_genre_preferences(
    updates: GenrePreferencesUpdate,
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
):
    """
    Update current user's genre preferences.

    In staging, resolves any active impersonation session first, so a
    promotions staff member impersonating a staff account edits that staff
    member's genre preferences instead of their own.
    """
    effective_email = resolve_effective_email(email, db)
    prefs = _get_or_create_genre_preferences(db, effective_email)
    prefs.genres = sorted({g.strip().lower() for g in updates.genres if g.strip()})
    db.commit()
    db.refresh(prefs)
    audit_service.log_event(
        db,
        event_type="genre_preferences_updated",
        actor_email=effective_email,
        actor_role=determine_user_role(db, effective_email),
        entity_type="staff",
        entity_id=prefs.staff_id,
        details={"genres": prefs.genres},
    )
    return prefs
