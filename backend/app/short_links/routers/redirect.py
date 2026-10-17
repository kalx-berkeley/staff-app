"""
The /go/<slug> redirects. Apache proxies /go/ here (outside /api/), and lets
DJ studio and station office network requests through without a login, so
this route is the access check: only active staff can follow a short link.
"""

from html import escape

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_staff_member
from app.database import get_db
from app.models.short_link import ShortLink

router = APIRouter(prefix="/go", tags=["short-links"])

# The target can change at any time, so browsers mustn't keep the redirect
NO_STORE = {"Cache-Control": "no-store"}


def _page(status_code: int, title: str, message: str) -> HTMLResponse:
    """A minimal error page with a link to the staff home page."""
    body = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title></head>"
        '<body style="font-family: system-ui, sans-serif; margin: 2rem;">'
        f"<h1>{escape(title)}</h1><p>{escape(message)}</p>"
        '<p><a href="/">KALX Staff home</a></p></body></html>\n'
    )
    return HTMLResponse(body, status_code=status_code, headers=NO_STORE)


@router.get("/{slug:path}", response_class=HTMLResponse)
def follow_short_link(
    slug: str,
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    db: Session = Depends(get_db),
):
    """Redirect (302) to the short link's target. Slugs ignore case."""
    if not x_forwarded_user:
        return _page(
            status.HTTP_401_UNAUTHORIZED,
            "Sign in required",
            "Short links are for KALX staff. Sign in to follow this link.",
        )
    try:
        get_staff_member(x_forwarded_user, db)
    except HTTPException:
        return _page(
            status.HTTP_403_FORBIDDEN,
            "Not available",
            "Short links are only for active KALX staff.",
        )

    slug = slug.removesuffix("/").lower()
    link = db.query(ShortLink).filter(ShortLink.slug == slug).first() if slug else None
    if not link:
        message = (
            f"There's no short link named “{slug}”." if slug else "No short link was given."
        )
        return _page(status.HTTP_404_NOT_FOUND, "Short link not found", message)
    return RedirectResponse(
        link.target_url, status_code=status.HTTP_302_FOUND, headers=NO_STORE
    )
