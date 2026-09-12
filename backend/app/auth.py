"""Authentication and authorization utilities."""

import logging

from fastapi import Header, HTTPException, Request, status, Depends
from sqlalchemy.orm import Session
import ipaddress

from app.database import get_db
from app.models.staff import Staff
from app.config import settings

logger = logging.getLogger(__name__)

PAID_STAFF_STATUS = "Paid Staff"
ACTIVE_STATUS = "Active"
PROMOTIONS_DEPARTMENT = "Promotions"
SUBLIST_DJ_STATUS = "Sublist DJ"


def is_ip_in_network(ip_address: str, network: str) -> bool:
    """
    Check if an IP address is within a CIDR network range.

    :param ip_address: IP address to check (e.g., "192.168.1.50")
    :param network: CIDR network (e.g., "192.168.1.0/24")
    :returns: True if IP is in network, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_address)
        net = ipaddress.ip_network(network, strict=False)
        return ip in net
    except (ValueError, ipaddress.AddressValueError):
        return False


def check_apache_auth_layer(
    request: Request,
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    x_forwarded_for: str | None = Header(None, alias="X-Forwarded-For"),
    x_dj_network: str | None = Header(None, alias="X-DJ-Network"),
    x_station_office_network: str | None = Header(None, alias="X-Station-Office-Network"),
) -> None:
    """
    Defense-in-depth: verify that Apache authenticated this API request.

    Apache guarantees that every proxied /api/ request carries one of:
    - X-Forwarded-User (OIDC email from mod_auth_openidc), OR
    - X-DJ-Network: 1 (set by Apache for DJ studio network requests), OR
    - X-Station-Office-Network: 1 (set by Apache for station office network requests)

    Client-supplied values are stripped early by Apache to prevent spoofing.
    X-Forwarded-For IP matching is kept as a fallback for the test environment,
    where Apache is not in the path and tests inject the header directly.

    If none of the above are present, the Apache authentication layer has been
    bypassed — this indicates a server misconfiguration.

    :param request: Incoming HTTP request (for logging the path)
    :param x_forwarded_user: OIDC email set by Apache mod_auth_openidc
    :param x_forwarded_for: Real client IP set by Apache mod_proxy (fallback)
    :param x_dj_network: Set to "1" by Apache for DJ studio network requests
    :param x_station_office_network: Set to "1" by Apache for station office network requests
    :raises HTTPException: 400 if no recognized identity or network is present
    """
    has_google_identity = bool(x_forwarded_user)
    from_dj_network = x_dj_network == "1"
    from_station_office = x_station_office_network == "1"

    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else None
    if not from_dj_network and client_ip:
        from_dj_network = is_ip_in_network(client_ip, settings.dj_studio_network)
    if not from_station_office and client_ip:
        from_station_office = is_ip_in_network(client_ip, settings.station_office_network)

    if not has_google_identity and not from_dj_network and not from_station_office:
        logger.critical(
            "SECURITY: API request received with no Google identity and no recognized "
            "network IP. Apache authentication layer may have been bypassed. "
            "Path: %s, X-Forwarded-For: %r",
            request.url.path,
            x_forwarded_for,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request did not pass through the expected authentication layer",
        )


def _staff_statuses(staff: Staff) -> set[str]:
    return {s.status for s in staff.statuses}


def _staff_departments(staff: Staff) -> set[str]:
    return {d.department for d in staff.departments}


def _is_promotions_staff(staff: Staff) -> bool:
    """
    Return True if a staff member qualifies for the promotions role.

    Promotions role is granted when:
    - Status contains both 'Paid Staff' and 'Active', OR
    - Department contains 'Promotions' and Status contains 'Active'
    """
    statuses = _staff_statuses(staff)
    is_active = ACTIVE_STATUS in statuses

    if PAID_STAFF_STATUS in statuses and is_active:
        return True

    if PROMOTIONS_DEPARTMENT in _staff_departments(staff) and is_active:
        return True

    return False


def _get_promotions_staff_by_email(db: Session, email: str) -> Staff | None:
    """Return the Staff record if the user qualifies for the promotions role, else None."""
    staff = db.query(Staff).filter(Staff.email == email).first()
    if staff and _is_promotions_staff(staff):
        return staff
    return None


def get_current_user_email(
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    db: Session = Depends(get_db),
) -> str | None:
    """
    Extract the current user's effective email from the X-Forwarded-User header,
    honoring an active staging impersonation session.

    :param x_forwarded_user: Email from Apache mod_auth_openidc Google authentication
    :param db: Database session
    :returns: The impersonated user's email if actively impersonating in staging,
        the authenticated email otherwise, or None if not authenticated.
    """
    if not x_forwarded_user:
        return None
    return resolve_effective_email(x_forwarded_user, db)


def require_authentication(
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User")
) -> str:
    """
    Require authentication and return user email.

    :param x_forwarded_user: Email from Apache mod_auth_openidc Google authentication
    :returns: User email
    :raises HTTPException: If not authenticated
    """
    if not x_forwarded_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return x_forwarded_user


def get_user_role(
    email: str = Depends(require_authentication), db: Session = Depends(get_db)
) -> str:
    """
    Determine user role from email.

    Role mapping (checked in order):
    - 'Paid Staff' + 'Active' statuses → promotions
    - 'Promotions' department + 'Active' status → promotions
    - 'Active' status → staff
    - otherwise → dj

    :param email: User email from authentication
    :param db: Database session
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


def get_user_role_or_dj(
    email: str | None = Depends(get_current_user_email), db: Session = Depends(get_db)
) -> str:
    """
    Determine user role from email, returning "dj" for unauthenticated requests.

    Used on endpoints that must be reachable by unauthenticated DJ studio network
    users.  Any unauthenticated request that reaches this dependency has already
    passed check_apache_auth_layer, so it originates from the DJ studio network.

    Role mapping is identical to get_user_role when an email is present. `email`
    is already impersonation-resolved by `get_current_user_email`, so a
    promotions staff member impersonating another account in staging gets that
    account's role.

    :param email: User's effective email (optional)
    :param db: Database session
    :returns: User role: "promotions", "staff", or "dj"
    """
    if not email:
        return "dj"

    staff = db.query(Staff).filter(Staff.email == email).first()
    if not staff:
        return "dj"

    statuses = _staff_statuses(staff)
    if ACTIVE_STATUS not in statuses:
        return "dj"

    if _is_promotions_staff(staff):
        return "promotions"

    return "staff"


def resolve_effective_email(email: str, db: Session) -> str:
    """
    Resolve *email* to the identity actually being acted as, honoring an active
    staging impersonation session (a promotions staff member impersonating
    another account to test their view/permissions).

    :param email: The real, authenticated user's email.
    :param db: Database session.
    :returns: The impersonated user's email if *email* has an active
        impersonation session in staging, else *email* unchanged.
    """
    if settings.environment != "staging":
        return email

    from app.models.impersonation_session import ImpersonationSession

    imp = (
        db.query(ImpersonationSession)
        .filter(ImpersonationSession.real_email == email)
        .first()
    )
    return imp.impersonated_email if imp and imp.impersonated_email else email


def get_promotions_staff(
    email: str = Depends(require_authentication), db: Session = Depends(get_db)
) -> Staff:
    """
    Get promotions staff member from authenticated user.

    :param email: User email from authentication
    :param db: Database session
    :returns: Staff record for the promotions staff member
    :raises HTTPException: If user does not have the promotions role
    """
    promotions = _get_promotions_staff_by_email(db, email)
    if not promotions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only promotions staff can perform this action",
        )
    return promotions


def get_staff_member(
    email: str = Depends(require_authentication), db: Session = Depends(get_db)
) -> Staff:
    """
    Get staff member from authenticated user.

    In staging, resolves any active impersonation session so that a promotions
    staff member impersonating a staff account acts as that staff member.

    :param email: User email from authentication
    :param db: Database session
    :returns: Staff record
    :raises HTTPException: If user does not have the staff or promotions role
    """
    from app.models.impersonation_session import ImpersonationSession

    effective_email = email
    if settings.environment == "staging":
        imp = (
            db.query(ImpersonationSession)
            .filter(ImpersonationSession.real_email == email)
            .first()
        )
        if imp and imp.impersonated_email:
            effective_email = imp.impersonated_email

    staff = db.query(Staff).filter(Staff.email == effective_email).first()
    if not staff or ACTIVE_STATUS not in _staff_statuses(staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only staff members can perform this action",
        )
    return staff


def check_dj_access(
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    x_forwarded_for: str | None = Header(None, alias="X-Forwarded-For"),
    db: Session = Depends(get_db),
) -> bool:
    """
    Check if user has DJ access.

    DJ access is granted if:
    1. Request is from DJ studio network (no authentication required), OR
    2. User is authenticated and has the promotions role (for testing/support)

    :param x_forwarded_user: Email from Apache mod_auth_openidc Google authentication (optional)
    :param x_forwarded_for: IP address from proxy
    :param db: Database session
    :returns: True if access is allowed
    :raises HTTPException: If access is denied
    """
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()
        if is_ip_in_network(client_ip, settings.dj_studio_network):
            return True

    if x_forwarded_user:
        if _get_promotions_staff_by_email(db, x_forwarded_user):
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "DJ view requires DJ studio network access or promotions staff authentication"
        ),
    )


def check_station_office_access(
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    x_forwarded_for: str | None = Header(None, alias="X-Forwarded-For"),
    x_station_office_network: str | None = Header(None, alias="X-Station-Office-Network"),
    db: Session = Depends(get_db),
) -> bool:
    """
    Check if user has station office access (required for winner search).

    Access is granted if:
    1. Request is from station office network (no authentication required), OR
    2. User is authenticated and has the promotions role (for testing/support)

    :param x_forwarded_user: Email from Apache mod_auth_openidc Google authentication (optional)
    :param x_forwarded_for: IP address from proxy
    :param x_station_office_network: Set to "1" by Apache for station office network requests
    :param db: Database session
    :returns: True if access is allowed
    :raises HTTPException: If access is denied
    """
    if x_station_office_network == "1":
        return True

    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()
        if is_ip_in_network(client_ip, settings.station_office_network):
            return True

    if x_forwarded_user:
        if _get_promotions_staff_by_email(db, x_forwarded_user):
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "Winner search requires station office network access or promotions staff"
            " authentication"
        ),
    )


def _is_sublist_dj(staff: Staff) -> bool:
    """
    Return True if a staff member has Sublist DJ status (and is Active).

    :param staff: Staff record
    :returns: True if staff is an active Sublist DJ
    """
    statuses = _staff_statuses(staff)
    return SUBLIST_DJ_STATUS in statuses and ACTIVE_STATUS in statuses


def get_sublist_dj_staff(
    email: str = Depends(require_authentication), db: Session = Depends(get_db)
) -> Staff:
    """
    Get staff member with Sublist DJ status from authenticated user.

    In staging, resolves any active impersonation session so that a promotions
    staff member impersonating a Sublist DJ account can test the feature.

    :param email: User email from authentication
    :param db: Database session
    :returns: Staff record for the Sublist DJ
    :raises HTTPException: If user does not have Sublist DJ status
    """
    from app.config import settings
    from app.models.impersonation_session import ImpersonationSession

    effective_email = email
    if settings.environment == "staging":
        imp = (
            db.query(ImpersonationSession)
            .filter(ImpersonationSession.real_email == email)
            .first()
        )
        if imp and imp.impersonated_email:
            effective_email = imp.impersonated_email

    staff = db.query(Staff).filter(Staff.email == effective_email).first()
    if not staff or not _is_sublist_dj(staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Sublist DJ staff can perform this action",
        )
    return staff


def require_promotions_or_staff(
    email: str = Depends(require_authentication), db: Session = Depends(get_db)
) -> tuple[str, Staff]:
    """
    Require that user is either promotions staff or staff member.

    In staging, resolves any active impersonation session so that a promotions
    staff member impersonating a staff account acts as that staff member.

    :param email: User email from authentication
    :param db: Database session
    :returns: Tuple of (role, user_record) where role is "promotions" or "staff"
    :raises HTTPException: If user is neither promotions staff nor active staff member
    """
    from app.models.impersonation_session import ImpersonationSession

    effective_email = email
    if settings.environment == "staging":
        imp = (
            db.query(ImpersonationSession)
            .filter(ImpersonationSession.real_email == email)
            .first()
        )
        if imp and imp.impersonated_email:
            effective_email = imp.impersonated_email

    staff = db.query(Staff).filter(Staff.email == effective_email).first()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires promotions staff or staff member authentication",
        )

    if _is_promotions_staff(staff):
        return ("promotions", staff)

    if ACTIVE_STATUS in _staff_statuses(staff):
        return ("staff", staff)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This action requires promotions staff or staff member authentication",
    )
