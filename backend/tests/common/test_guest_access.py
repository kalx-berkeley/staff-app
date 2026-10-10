"""
Guard the routes an unauthenticated network guest can reach.

Apache lets two kinds of client reach /api/ without a Google login: DJ studio
network computers (the Radio Pass Giveaway DJ view) and station office network
computers (winner search). The backend is the real access boundary, so this
test calls every API route as each kind of guest and fails if the set of
routes that answer differs from the allowlists below, in either direction:

- A route missing from an allowlist answers a guest: an endpoint was opened to
  unauthenticated clients, perhaps by using a network-aware auth dependency.
- An allowlisted route no longer answers: the list is stale, or the DJ view or
  winner search lost access it needs.

"Answers" means any status other than 401/403. A 404 or 422 counts, since it
means the request got past the access checks. Rows with ID 1 are seeded so
handlers that look a record up before checking access give their real answer.
Change an allowlist only after deciding the guest should have that access.

The redaction tests check what guests get back from those routes: no staff,
promotions, venue or specialty-show owner contact details, no winner emails,
and winner phone numbers only in the DJ view and in winner search.
"""

import re
from datetime import date, time

import httpx2
import musicbrainzngs.musicbrainz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.main import app
from app.models.pass_model import Pass
from app.models.promoter import Promoter
from app.models.show import Show
from app.models.specialty_show import SpecialtyShow
from app.models.staff import Staff
from app.models.staff_status import StaffStatus
from app.models.specialty_show_owner import SpecialtyShowOwner
from app.models.staff_department import StaffDepartment
from app.models.venue import Venue
from app.models.venue_contact import VenueContact
from app.models.venue_owner import VenueOwner
from app.pass_giveaway.schemas.pass_schema import GiveawayData
from app.pass_giveaway.services.pass_service import PassService

# Apache sets the network header and the real client IP; the backend checks both.
DJ_GUEST = {"X-DJ-Network": "1", "X-Forwarded-For": "192.168.1.100"}
OFFICE_GUEST = {"X-Station-Office-Network": "1", "X-Forwarded-For": "192.168.2.50"}

# Routes both kinds of guest can reach.
SHARED_GUEST_ROUTES = {
    # Identity: tells the SPA the caller is a network guest.
    "GET /api/users/me",
    # Browsing shows, venues and specialty shows. Show passes include winner
    # and staff contact details.
    "GET /api/shows",
    "GET /api/shows/search",
    "GET /api/shows/genres",
    "GET /api/shows/suggest-genre",
    "GET /api/shows/{show_id}",
    "GET /api/shows/{show_id}/passes",
    "GET /api/shows/musicbrainz/search",
    "GET /api/shows/musicbrainz/artist/{artist_id}/wikipedia",
    "GET /api/venues",
    "GET /api/venues/{venue_id}",
    "GET /api/venues/{venue_id}/logo",
    "GET /api/specialty-shows",
    "GET /api/specialty-shows/upcoming-titles",
    "GET /api/specialty-shows/{show_id}",
    "GET /api/specialty-shows/{show_id}/dj-history",
    # Winner search.
    "GET /api/passes/search-by-phone",
    "POST /api/passes/{pass_id}/release-winner",
}

# The DJ view, used from the air studio.
DJ_GUEST_ROUTES = SHARED_GUEST_ROUTES | {
    "GET /api/autocomplete/djs",
    "GET /api/dj/on-air",
    "GET /api/dj/spin-matches",
    "POST /api/dj/spin-matches/{spin_id}/dismiss",
    "GET /api/passes/my-giveaways",
    "POST /api/passes/{pass_id}/giveaway",
    "DELETE /api/passes/{pass_id}/preassign",
    "POST /api/shows/{show_id}/attempt",
    "GET /api/venues/{venue_id}/check-winner",
}

# Winner search, used from station office computers.
OFFICE_GUEST_ROUTES = SHARED_GUEST_ROUTES

# Routes that only exist when a setting turns their router on (see main.py).
FLAGGED_GUEST_ROUTES = {
    "legacy_import_enabled": {"GET /api/legacy-import/enabled"},
}


def _with_enabled_flags(routes: set[str]) -> set[str]:
    enabled = {
        route
        for flag, flagged in FLAGGED_GUEST_ROUTES.items()
        if getattr(settings, flag)
        for route in flagged
    }
    return routes | enabled


@pytest.fixture
def seeded(db: Session):
    """One of each record a route might look up by ID, all with ID 1."""
    staff = Staff(email="active@example.com", name="Active Person", phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    venue = Venue(name="Venue", address="1 Main St")
    promoter = Promoter(name="Promoter")
    db.add_all([venue, promoter, SpecialtyShow(name="Specialty Show")])
    db.flush()
    show = Show(
        event_name="Show",
        genre=["Rock"],
        venue_id=venue.id,
        promoter_id=promoter.id,
        show_date=date(2099, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=1,
        status="published",
    )
    db.add(show)
    db.flush()
    db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    db.commit()


@pytest.fixture
def no_outbound_requests(monkeypatch):
    """Fail any call to an outside service instead of making it."""

    def refuse(self, request, *args, **kwargs):
        raise httpx2.ConnectError("outbound requests are disabled in this test")

    async def refuse_async(self, request, *args, **kwargs):
        refuse(self, request)

    def refuse_musicbrainz(*args, **kwargs):
        raise musicbrainzngs.musicbrainz.NetworkError("disabled in this test")

    # Patch the network transports, not Client.send: TestClient is an
    # httpx2.Client too, but uses its own in-process transport.
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", refuse)
    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", refuse_async)
    monkeypatch.setattr(musicbrainzngs.musicbrainz, "_mb_request", refuse_musicbrainz)


def _guest_responses(client: TestClient, headers: dict[str, str]) -> dict:
    """Call every API route as a guest; map "METHOD /path" to its response."""
    # A route that crashes still got past the access checks, so count a 500 as
    # an answer rather than letting the exception fail the test.
    client = TestClient(client.app, raise_server_exceptions=False)
    responses = {}
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith("/api/"):
            continue
        concrete = re.sub(r"\{[^}]+\}", "1", path)
        for method in operations:
            route = f"{method.upper()} {path}"
            responses[route] = client.request(
                method.upper(), concrete, headers=headers, json={}
            )
    return responses


def _routes_answering(client: TestClient, headers: dict[str, str]) -> set[str]:
    return {
        route
        for route, response in _guest_responses(client, headers).items()
        if response.status_code not in (401, 403)
    }


@pytest.mark.parametrize(
    "headers, allowed",
    [(DJ_GUEST, DJ_GUEST_ROUTES), (OFFICE_GUEST, OFFICE_GUEST_ROUTES)],
    ids=["dj-network", "station-office-network"],
)
def test_guests_reach_only_allowlisted_routes(
    client: TestClient, seeded, no_outbound_requests, headers, allowed
):
    answering = _routes_answering(client, headers)
    allowed = _with_enabled_flags(allowed)

    assert sorted(answering - allowed) == [], "routes newly open to guests"
    assert sorted(allowed - answering) == [], "allowlisted routes guests can't reach"


def test_directory_is_never_open_to_guests(
    client: TestClient, seeded, no_outbound_requests
):
    for headers in (DJ_GUEST, OFFICE_GUEST):
        answering = _routes_answering(client, headers)
        assert not {r for r in answering if " /api/directory" in r}


# Contact details seeded by the contact_details fixture.
STAFF_CONTACTS = [
    "claimer@example.com",
    "5105550111",
    "owner@example.com",
    "5105550133",
    "venue.contact@example.com",
    "5105550144",
]
WINNER_EMAIL = "winner@example.com"
WINNER_PHONE = "5105550122"
WINNER_SEARCH_ROUTES = {
    "GET /api/passes/search-by-phone",
    "POST /api/passes/{pass_id}/release-winner",
}


@pytest.fixture
def contact_details(db: Session, seeded):
    """Contact details guests must not see, attached to the seeded show and venue."""
    owner = Staff(email="owner@example.com", name="Venue Owner", phone="510-555-0133")
    claimer = Staff(email="claimer@example.com", name="Claimer", phone="510-555-0111")
    db.add_all([owner, claimer])
    db.flush()
    db.add_all([
        StaffStatus(staff_id=owner.id, status="Active"),
        StaffDepartment(staff_id=owner.id, department="Promotions"),
        StaffStatus(staff_id=claimer.id, status="Active"),
        VenueOwner(venue_id=1, staff_id=owner.id),
        SpecialtyShowOwner(specialty_show_id=1, staff_id=owner.id),
        VenueContact(
            venue_id=1,
            name="Box Office",
            email="venue.contact@example.com",
            phone="510-555-0144",
        ),
        Pass(show_id=1, pass_type="staff", status="claimed", staff_id=claimer.id),
    ])
    db.commit()
    PassService.give_away_pass_pair(
        db,
        1,
        GiveawayData(
            recipient_name="Winner",
            recipient_phone="510-555-0122",
            recipient_email=WINNER_EMAIL,
            given_away_by_dj="DJ",
        ),
    )


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _shows_contact(response, contact: str) -> bool:
    return contact in response.text or (
        contact.isdigit() and contact in _digits(response.text)
    )


@pytest.mark.parametrize("headers", [DJ_GUEST, OFFICE_GUEST], ids=["dj", "office"])
def test_guests_never_see_staff_contacts_or_winner_emails(
    client: TestClient, contact_details, no_outbound_requests, headers
):
    leaks = [
        f"{route}: {contact}"
        for route, response in _guest_responses(client, headers).items()
        for contact in STAFF_CONTACTS + [WINNER_EMAIL]
        if _shows_contact(response, contact)
    ]

    assert leaks == []


def test_office_guests_see_winner_phones_only_in_winner_search(
    client: TestClient, contact_details, no_outbound_requests
):
    responses = _guest_responses(client, OFFICE_GUEST)

    leaks = [
        route
        for route, response in responses.items()
        if route not in WINNER_SEARCH_ROUTES and _shows_contact(response, WINNER_PHONE)
    ]
    found = client.get(
        "/api/passes/search-by-phone",
        params={"phone": "510-555-0122"},
        headers=OFFICE_GUEST,
    )

    assert leaks == []
    assert found.json()[0]["recipient_phone"] is not None


def test_dj_guests_see_winner_phones_for_the_dj_view(
    client: TestClient, contact_details, no_outbound_requests
):
    passes = client.get("/api/shows/1/passes", headers=DJ_GUEST).json()

    winner = next(p for p in passes if p["recipient_name"] == "Winner")
    assert _digits(winner["recipient_phone"]) == WINNER_PHONE


def test_signed_in_users_still_see_contact_details(
    client: TestClient, contact_details, no_outbound_requests
):
    response = client.get(
        "/api/shows/1/passes", headers={"X-Forwarded-User": "owner@example.com"}
    )

    assert "claimer@example.com" in response.text
    assert WINNER_EMAIL in response.text
