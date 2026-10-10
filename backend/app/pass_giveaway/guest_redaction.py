"""
Remove contact details from responses to unauthenticated network guests.

DJ studio and station office computers can use parts of the pass giveaway
without a Google login (see "Guest Access From Trusted Networks" in
SECURITY.md). The responses they get are shared with signed-in users, so this
removes the contact details guests don't need:

- Every guest: staff phones and emails, winner emails, and the promotions,
  venue and specialty-show owner contacts.
- Station office guests: winner phone numbers too, except from endpoints marked
  with :func:`keeps_winner_contact` (winner search). DJ studio guests keep
  winner names and phones, which the DJ view shows.

Each pass giveaway router uses :class:`GuestRedactingRoute`, so new endpoints
are covered without extra code.
"""

import json
from typing import Any, Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute

from app.auth import is_ip_in_network
from app.config import settings

# Keys whose value is removed (set to None) in every guest response.
_HIDDEN_VALUES = {
    "email",
    "phone",
    "recipient_email",
    "releasing_email",
    "staff_email",
    "staff_phone",
}
# Keys whose list is emptied in every guest response.
_HIDDEN_LISTS = {"contacts", "owner_details", "owner_emails", "promotions_contacts"}
# Removed for station office guests outside winner search.
_WINNER_CONTACT = {"recipient_phone"}


def keeps_winner_contact(endpoint: Callable) -> Callable:
    """Mark a winner-search endpoint whose guests may see winner phone numbers."""
    endpoint.keeps_winner_contact = True
    return endpoint


def _is_dj_studio_guest(request: Request) -> bool:
    if request.headers.get("X-DJ-Network") == "1":
        return True
    forwarded_for = request.headers.get("X-Forwarded-For")
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else None
    return bool(client_ip) and is_ip_in_network(client_ip, settings.dj_studio_network)


def _redact(data: Any, hidden_values: set[str]) -> Any:
    if isinstance(data, list):
        return [_redact(item, hidden_values) for item in data]
    if not isinstance(data, dict):
        return data
    redacted = {}
    for key, value in data.items():
        if key in hidden_values:
            redacted[key] = None
        elif key in _HIDDEN_LISTS:
            redacted[key] = []
        else:
            redacted[key] = _redact(value, hidden_values)
    return redacted


class GuestRedactingRoute(APIRoute):
    """An APIRoute that removes contact details from guests' JSON responses."""

    def get_route_handler(self) -> Callable:
        handler = super().get_route_handler()
        keeps_winner = getattr(self.endpoint, "keeps_winner_contact", False)

        async def redacting_handler(request: Request) -> Response:
            response = await handler(request)
            # Signed-in users, including anyone impersonating in staging, carry
            # X-Forwarded-User; network guests never do.
            if request.headers.get("X-Forwarded-User"):
                return response
            if response.media_type != "application/json" or not response.body:
                return response
            hidden = set(_HIDDEN_VALUES)
            if not keeps_winner and not _is_dj_studio_guest(request):
                hidden |= _WINNER_CONTACT
            body = json.dumps(_redact(json.loads(response.body), hidden)).encode()
            headers = {
                k: v for k, v in response.headers.items() if k.lower() != "content-length"
            }
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type="application/json",
                background=response.background,
            )

        return redacting_handler
