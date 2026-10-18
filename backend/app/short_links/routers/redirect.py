"""
The /go/<slug> redirects. Apache proxies /go/ here (outside /api/), and lets
DJ studio and station office network requests through without a login, so
this route is the access check: only active staff can follow a short link.
"""

import re
from html import escape

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_staff_member
from app.database import get_db
from app.models.short_link import ShortLink

router = APIRouter(prefix="/go", tags=["short-links"])

# The target can change at any time, so browsers mustn't keep the redirect
NO_STORE = {"Cache-Control": "no-store"}


# Same guide as the SPA's UnauthorizedPage
SIGN_IN_HELP_URL = (
    "https://docs.google.com/document/d/1RwVZaJwv-Z46pMYJhkNfvQjnZe6kSWw8vJz8MVZdW8g/edit"
)

# Inline styles matching the SPA's UnauthorizedPage
_BODY_STYLE = (
    "font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif; "
    "margin: 0; min-height: 100vh; display: flex; justify-content: center; "
    "align-items: flex-start; background: #f0f2f5; color: #222; "
    "padding: 3rem 1rem; box-sizing: border-box;"
)
_CARD_STYLE = (
    "background: #fff; border-radius: 10px; "
    "box-shadow: 0 2px 12px rgba(0,0,0,0.13); max-width: 560px; width: 100%; "
    "padding: 2.25rem 2.5rem; box-sizing: border-box;"
)
_H1_STYLE = "margin: 0 0 0.5rem; font-size: 1.5rem; color: #111;"
_LEAD_STYLE = "margin: 0 0 1.75rem; color: #555; font-size: 1rem; line-height: 1.55;"
_SECTION_STYLE = (
    "background: {color}; border: 1px solid {border}; border-radius: 7px; "
    "padding: 1.1rem 1.3rem; margin-bottom: 1.1rem; line-height: 1.55; "
    "font-size: 0.95rem; color: #333;"
)
_SECTION_HEADING_STYLE = (
    "display: block; margin-bottom: 0.6rem; font-size: 1rem; color: #111;"
)
_STEP_STYLE = "margin-bottom: 0.6rem;"
_BUTTON_STYLE = (
    "display: inline-block; background: #1a73e8; color: #fff; "
    "padding: 0.35rem 0.9rem; border-radius: 5px; text-decoration: none; "
    "font-weight: 600;"
)
_FOOTNOTE_STYLE = "margin: 1.25rem 0 0; font-size: 0.85rem; color: #666; line-height: 1.5;"


def _page(status_code: int, title: str, content_html: str) -> HTMLResponse:
    """
    An error page in a card like the SPA's UnauthorizedPage. content_html goes
    in as is, so callers must escape anything they put in it.
    """
    body = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title></head>"
        f'<body style="{_BODY_STYLE}"><div style="{_CARD_STYLE}">'
        f'<h1 style="{_H1_STYLE}">{escape(title)}</h1>{content_html}'
        "</div></body></html>\n"
    )
    return HTMLResponse(body, status_code=status_code, headers=NO_STORE)


def _message(message: str) -> str:
    """A plain message followed by a link to the staff home page."""
    return (
        f'<p style="{_LEAD_STYLE}">{escape(message)}</p>'
        '<p style="margin: 0;"><a href="/">KALX Staff home</a></p>'
    )


def _section(color: str, border: str, heading: str, content_html: str) -> str:
    style = _SECTION_STYLE.format(color=color, border=border)
    return (
        f'<div style="{style}">'
        f'<strong style="{_SECTION_HEADING_STYLE}">{escape(heading)}</strong>'
        f"{content_html}</div>"
    )


def _wrong_account(request: Request, email: str) -> str:
    """
    The 403 content: like UnauthorizedPage, suggest logging out and signing in
    with the Google account for the person's KALX email address.
    """
    # Apache preserves the Host header, so this is the staff. site's host
    auth_host = re.sub(r"^staff\.", "auth.", request.url.hostname or "")
    logout_url = f"https://{auth_host}/redirect_uri?logout=https://{auth_host}/"
    steps = (
        '<ol style="margin: 0; padding-left: 1.4rem; line-height: 1.6;">'
        f'<li style="{_STEP_STYLE}"><strong>Find your KALX email address.</strong> '
        "It's the address your <strong>KALX Announce</strong> emails are "
        "delivered to.</li>"
        f'<li style="{_STEP_STYLE}"><a href="{escape(logout_url)}" '
        f'style="{_BUTTON_STYLE}">Log out</a></li>'
        f'<li style="{_STEP_STYLE}"><strong>Sign in to Google with that '
        "address.</strong> When Google asks you to choose an account, pick it "
        "(or choose &quot;Use another account&quot; to add it), then follow "
        "the short link again.</li>"
        "</ol>"
        '<p style="margin: 1rem 0 0;">Need help signing in, or don\'t have a '
        "Google account for that address yet? "
        f'<a href="{SIGN_IN_HELP_URL}" target="_blank" rel="noreferrer">'
        "Read the sign-in guide</a>.</p>"
    )
    return (
        f'<p style="{_LEAD_STYLE}">You\'re signed in as '
        f'<strong style="word-break: break-all;">{escape(email)}</strong>.</p>'
        + _section(
            "#f5f5f5",
            "#ddd",
            "Not KALX staff?",
            '<p style="margin: 0;">Short links are only for KALX 90.7 FM '
            "staff. There's nothing more you need to do.</p>",
        )
        + _section(
            "#fff8e1",
            "#ffe082",
            "KALX staff? You're probably signed in with the wrong Google account.",
            steps,
        )
        + f'<p style="{_FOOTNOTE_STYLE}">Still blocked after signing in with '
        "your KALX Announce address? Email the Operations Manager so they can "
        "check your staff record.</p>"
    )


@router.get("/{slug:path}", response_class=HTMLResponse)
def follow_short_link(
    slug: str,
    request: Request,
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    db: Session = Depends(get_db),
):
    """Redirect (302) to the short link's target. Slugs ignore case."""
    if not x_forwarded_user:
        return _page(
            status.HTTP_401_UNAUTHORIZED,
            "Sign in required",
            _message("Short links are for KALX staff. Sign in to follow this link."),
        )
    try:
        get_staff_member(x_forwarded_user, db)
    except HTTPException:
        return _page(
            status.HTTP_403_FORBIDDEN,
            "This Google account can't follow KALX short links",
            _wrong_account(request, x_forwarded_user),
        )

    slug = slug.removesuffix("/").lower()
    link = db.query(ShortLink).filter(ShortLink.slug == slug).first() if slug else None
    if not link:
        message = (
            f"There's no short link named “{slug}”." if slug else "No short link was given."
        )
        return _page(status.HTTP_404_NOT_FOUND, "Short link not found", _message(message))
    return RedirectResponse(
        link.target_url, status_code=status.HTTP_302_FOUND, headers=NO_STORE
    )
