"""
Short Links admin API, used by KALX Staff Admin. Only site admins can list,
create, edit or delete short links.
"""

import re
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import get_site_admin
from app.common.areas import SHORT_LINKS_AREA
from app.common.services.audit_service import log_event
from app.database import get_db
from app.models.short_link import ShortLink
from app.models.staff import Staff
from app.short_links.schemas.short_links import ShortLinkRequest, ShortLinkResponse

router = APIRouter(prefix="/api/short-links", tags=["short-links"])

# 1-64 lowercase letters, digits and hyphens, not starting or ending with a hyphen
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
MAX_TARGET_LENGTH = 2048


def normalize_slug(slug: str) -> str:
    """
    Lowercase a slug and check it's valid.

    :param slug: The slug as typed.
    :returns: The slug as stored.
    :raises HTTPException: 400 if the slug isn't valid.
    """
    slug = slug.strip().lower()
    if not SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A slug is 1 to 64 letters, numbers and hyphens, and can't start or"
                " end with a hyphen."
            ),
        )
    return slug


def validate_target(target_url: str, request: Request) -> str:
    """
    Check a short link's target is an absolute http(s) URL that isn't another
    short link on this site, which could make a redirect loop.

    :param target_url: The target as typed.
    :param request: The request, whose Host is this site.
    :returns: The target, trimmed.
    :raises HTTPException: 400 if the target isn't allowed.
    """
    target_url = target_url.strip()
    if len(target_url) > MAX_TARGET_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The target URL can be at most {MAX_TARGET_LENGTH} characters.",
        )
    parts = urlsplit(target_url)
    if (
        parts.scheme.lower() not in ("http", "https")
        or not parts.hostname
        or any(c.isspace() for c in target_url)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The target must be a full URL starting with https:// or http://.",
        )
    this_host = (request.headers.get("host") or "").split(":")[0].lower()
    path = parts.path.lower()
    if parts.hostname.lower() == this_host and (path == "/go" or path.startswith("/go/")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The target can't be another short link.",
        )
    return target_url


def _check_slug_free(db: Session, slug: str, link_id: int | None = None) -> None:
    query = db.query(ShortLink).filter(ShortLink.slug == slug)
    if link_id is not None:
        query = query.filter(ShortLink.id != link_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"There's already a short link /go/{slug}.",
        )


def _get_link(db: Session, link_id: int) -> ShortLink:
    link = db.get(ShortLink, link_id)
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found"
        )
    return link


def _note(note: str | None) -> str | None:
    return (note or "").strip() or None


@router.get("", response_model=list[ShortLinkResponse])
def list_short_links(admin: Staff = Depends(get_site_admin), db: Session = Depends(get_db)):
    """Every short link, by slug."""
    return db.query(ShortLink).order_by(ShortLink.slug).all()


@router.post("", response_model=ShortLinkResponse, status_code=status.HTTP_201_CREATED)
def create_short_link(
    body: ShortLinkRequest,
    request: Request,
    admin: Staff = Depends(get_site_admin),
    db: Session = Depends(get_db),
):
    """Create a short link."""
    slug = normalize_slug(body.slug)
    target_url = validate_target(body.target_url, request)
    _check_slug_free(db, slug)

    link = ShortLink(
        slug=slug,
        target_url=target_url,
        note=_note(body.note),
        created_by_email=admin.email,
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    log_event(
        db,
        event_type="short_link_created",
        area=SHORT_LINKS_AREA,
        actor_email=admin.email,
        actor_role="site_admin",
        entity_type="short_link",
        entity_id=link.id,
        details={"slug": link.slug, "target_url": link.target_url, "note": link.note},
    )
    return link


@router.put("/{link_id}", response_model=ShortLinkResponse)
def update_short_link(
    link_id: int,
    body: ShortLinkRequest,
    request: Request,
    admin: Staff = Depends(get_site_admin),
    db: Session = Depends(get_db),
):
    """Change a short link's slug, target or note."""
    link = _get_link(db, link_id)
    slug = normalize_slug(body.slug)
    target_url = validate_target(body.target_url, request)
    _check_slug_free(db, slug, link.id)

    old = {"slug": link.slug, "target_url": link.target_url, "note": link.note}
    link.slug = slug
    link.target_url = target_url
    link.note = _note(body.note)
    db.commit()
    db.refresh(link)

    log_event(
        db,
        event_type="short_link_updated",
        area=SHORT_LINKS_AREA,
        actor_email=admin.email,
        actor_role="site_admin",
        entity_type="short_link",
        entity_id=link.id,
        details={
            "old_slug": old["slug"],
            "slug": link.slug,
            "old_target_url": old["target_url"],
            "target_url": link.target_url,
            "old_note": old["note"],
            "note": link.note,
        },
    )
    return link


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_short_link(
    link_id: int,
    admin: Staff = Depends(get_site_admin),
    db: Session = Depends(get_db),
):
    """Delete a short link."""
    link = _get_link(db, link_id)
    details = {"slug": link.slug, "target_url": link.target_url, "note": link.note}
    db.delete(link)
    db.commit()

    log_event(
        db,
        event_type="short_link_deleted",
        area=SHORT_LINKS_AREA,
        actor_email=admin.email,
        actor_role="site_admin",
        entity_type="short_link",
        entity_id=link_id,
        details=details,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
