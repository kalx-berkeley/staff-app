"""Tests for the pass giveaway's KALX Staff Analytics metrics and tracking."""

from datetime import datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.areas import PASS_GIVEAWAY_AREA
from app.common.services.analytics_window import today_pacific
from app.common.services.audit_service import log_event
from app.config import settings
from app.models.analytics_event import AnalyticsEvent
from app.models.audit_log import AuditLog
from app.models.on_air_caller import (
    CommonCallerName,
    DismissedCallerPair,
    OnAirCaller,
    OnAirCallerPhone,
)
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.spinitron_persona import SpinitronPersona
from app.models.promoter import Promoter
from app.models.promoter_owner import PromoterOwner
from app.models.show import Show
from app.models.show_attempt import ShowAttempt
from app.models.specialty_show import SpecialtyShow
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.models.venue_owner import VenueOwner
from app.pass_giveaway.services import tracking
from tests.personas import add_persona

DJ_GUEST = {"X-DJ-Network": "1", "X-Forwarded-For": "192.168.1.100"}
OFFICE_GUEST = {"X-Station-Office-Network": "1", "X-Forwarded-For": "192.168.2.50"}
PROMO = {"X-Forwarded-User": "promo@example.com"}
NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _staff(db: Session, email: str, department: str | None = None) -> Staff:
    staff = Staff(email=email, name=email.split("@")[0].title(), phone="")
    db.add(staff)
    db.flush()
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    return staff


@pytest.fixture
def promo(db: Session) -> Staff:
    return _staff(db, "promo@example.com", "Promotions")


@pytest.fixture
def venue(db: Session) -> Venue:
    venue = Venue(name="The Fox", address="1 Main St", win_frequency_days=30)
    db.add(venue)
    db.commit()
    return venue


def _show(
    db: Session,
    venue: Venue,
    days_from_today: int,
    *,
    pairs=2,
    given=0,
    staff=2,
    claimed=0,
    status="published",
    name="Show",
    promoter: Promoter | None = None,
    **kwargs,
) -> Show:
    show = Show(
        event_name=name,
        genre=["Rock"],
        venue_id=venue.id,
        promoter_id=promoter.id if promoter else None,
        show_date=today_pacific() + timedelta(days=days_from_today),
        show_time=kwargs.pop("show_time", time(20, 0)),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=pairs,
        status=status,
        published_at=datetime.now(timezone.utc) - timedelta(days=20),
        **kwargs,
    )
    db.add(show)
    db.flush()
    for i in range(pairs):
        db.add(
            Pass(
                show_id=show.id,
                pass_type="pair",
                status="given_away" if i < given else "available",
                given_away_at=NOW - timedelta(days=1) if i < given else None,
            )
        )
    for i in range(staff):
        db.add(
            Pass(
                show_id=show.id,
                pass_type="staff",
                status="claimed" if i < claimed else "available",
            )
        )
    db.commit()
    return show


def _tab(client: TestClient, tab: str, query: str = "", window="preset=all_time") -> dict:
    r = client.get(f"/api/analytics/tabs/{tab}?{window}{query}", headers=PROMO)
    assert r.status_code == 200, r.text
    return {m["id"]: m for m in r.json()["metrics"]}


# ---------------------------------------------------------------------------
# Utilization


def test_utilization_counts_only_complete_shows(client, db, promo, venue):
    _show(db, venue, -10, pairs=2, given=2, staff=2, claimed=1)
    _show(db, venue, -5, pairs=2, given=0, staff=2, claimed=2, status="closed")
    _show(db, venue, 10, pairs=4, given=0, staff=4, claimed=0)  # future: left out
    _show(db, venue, -3, pairs=4, given=0, status="draft")  # draft: left out

    # A window reaching into the future counts the future show, but not in utilization
    later = (today_pacific() + timedelta(days=30)).isoformat()
    window = f"from=2000-01-01&to={later}"
    m = _tab(client, "overview", window=window)
    assert m["shows"]["value"] == 3
    assert m["on_air_utilization"]["value"] == pytest.approx(0.5)
    assert m["staff_utilization"]["value"] == pytest.approx(0.75)

    venues = _tab(client, "venues", window=window)["venues"]["rows"]
    assert len(venues) == 1
    row = venues[0]
    assert row["shows"] == 2
    assert row["show_count"] == 3
    assert row["balance"] == pytest.approx(-25.0)
    assert row["_low_sample"] is True


def test_low_sample_venues_are_left_out_of_rankings(client, db, promo, venue):
    other = Venue(name="Big Venue", address="2 Main St")
    db.add(other)
    db.commit()
    _show(db, venue, -2, given=2)
    for d in (-2, -3, -4):
        _show(db, other, d, given=1)
    ranked = _tab(client, "overview")["top_venues_on_air"]["rows"]
    assert [r["venue"] for r in ranked] == ["Big Venue"]


def test_weekday_and_time_breakdowns(client, db, promo, venue):
    promoter = Promoter(name="Another Planet")
    db.add(promoter)
    db.commit()
    _show(db, venue, -2, given=1, promoter=promoter)
    _show(db, venue, -3, given=0, show_time=None)
    m = _tab(client, "overview")
    times = {r["time"]: r for r in m["utilization_by_show_time"]["rows"]}
    assert set(times) == {"6–9pm", "Unknown"}
    assert "utilization_by_promoter" not in m
    assert sum(r["shows"] for r in m["utilization_by_weekday"]["rows"]) == 2


def test_staff_pass_reach_uses_todays_active_staff(client, db, promo, venue):
    a = _staff(db, "a@example.com")
    _staff(db, "b@example.com")
    show = _show(db, venue, -2, staff=0)
    db.add(
        Pass(
            show_id=show.id,
            pass_type="staff",
            status="claimed",
            staff_id=a.id,
            claimed_at=NOW,
        )
    )
    db.commit()
    m = _tab(client, "overview")
    # promo, a and b are Active
    assert m["staff_pass_reach"]["value"] == pytest.approx(1 / 3)
    [row] = m["top_staff_claimants"]["rows"]
    assert (row["name"], row["claims"]) == ("A", 1)
    assert row["_details"]["rows"] == [{
        "show_date": show.show_date.isoformat(),
        "show": "Show",
        "venue": "The Fox",
        "guest": "No",
    }]


# ---------------------------------------------------------------------------
# Winners


def _win(db, show, name, phone, email=None, days_ago=1):
    p = Pass(show_id=show.id, pass_type="pair", status="given_away")
    db.add(p)
    db.flush()
    db.add(
        OnAirWinner(
            pass_id=p.id,
            venue_id=show.venue_id,
            show_id=show.id,
            recipient_name=name,
            recipient_phone=phone,
            recipient_email=email,
            created_at=NOW - timedelta(days=days_ago),
        )
    )
    db.commit()


def test_repeat_winners_and_share(client, db, promo, venue):
    show = _show(db, venue, -1, pairs=0, staff=0)
    _win(db, show, "Jane Doe", "5105550100")
    _win(db, show, "Jane D", "5105550100")
    _win(db, show, "Someone", "5105550199")
    m = _tab(client, "winners")
    rows = m["top_repeat_winners"]["rows"]
    assert len(rows) == 1
    assert rows[0]["wins"] == 2
    assert rows[0]["name"] == "Jane D"
    assert m["repeat_winner_share"]["value"] == pytest.approx(2 / 3)


def test_same_name_different_phones(client, db, promo, venue):
    near = _show(db, venue, -1, pairs=0, staff=0)
    far = _show(db, venue, -100, pairs=0, staff=0)
    _win(db, near, "Jane Doe", "5105550100", email="jane@example.com")
    _win(db, near, "jane  doe.", "5105550111", email="JANE@example.com")
    _win(db, far, "Bob Smith", "5105550122", days_ago=100)
    _win(db, near, "Bob Smith", "5105550133")
    _win(db, near, "Solo Person", "5105550144")

    rows = _tab(client, "winners")["same_name_different_phones"]["rows"]
    by_name = {r["name"]: r for r in rows}
    assert set(by_name) == {"jane  doe.", "Bob Smith"}
    jane = by_name["jane  doe."]
    assert jane["_flag"] is True
    assert jane["same_email"] == "Yes"
    assert len(jane["_details"]["rows"]) == 2
    # 99 days apart at a venue with a 30-day limit
    assert by_name["Bob Smith"]["_flag"] is False

    venue_rows = _tab(client, "venue", f"&venue_id={venue.id}")["venue_same_name"]["rows"]
    assert len(venue_rows) == 2


def test_same_name_groups_misspelled_names(client, db, promo, venue):
    show = _show(db, venue, -1, pairs=0, staff=0)
    _win(db, show, "Jon Smith", "5105550100", days_ago=3)
    _win(db, show, "John Smtih", "5105550111", days_ago=2)
    _win(db, show, "John Smith", "5105550122")
    _win(db, show, "Jane Smith", "5105550133")
    _win(db, show, "Steven Park", "5105550144", days_ago=2)
    _win(db, show, "Stephen R. Park", "5105550155")

    rows = {
        r["name"]: r for r in _tab(client, "winners")["same_name_different_phones"]["rows"]
    }
    assert set(rows) == {"John Smith", "Stephen R. Park"}
    assert rows["Stephen R. Park"]["spellings"] == "Stephen R. Park, Steven Park"
    john = rows["John Smith"]
    assert john["name"] == "John Smith"
    assert john["phones"] == 3
    assert john["spellings"] == "John Smith, John Smtih, Jon Smith"
    assert [d["winner"] for d in john["_details"]["rows"]] == [
        "Jon Smith",
        "John Smtih",
        "John Smith",
    ]


def test_same_name_flags_wins_at_sister_venues(client, db, promo, venue):
    sister = Venue(name="The Fox Annex", address="2 Main St", parent_venue_id=venue.id)
    unrelated = Venue(name="Elsewhere", address="3 Main St", win_frequency_days=30)
    db.add_all([sister, unrelated])
    db.commit()
    _win(db, _show(db, venue, -1, pairs=0, staff=0), "Jane Doe", "5105550100")
    _win(db, _show(db, sister, -10, pairs=0, staff=0), "Jane Doe", "5105550111")
    _win(db, _show(db, venue, -1, pairs=0, staff=0), "Bob Smith", "5105550122")
    _win(db, _show(db, unrelated, -10, pairs=0, staff=0), "Bob Smith", "5105550133")

    rows = {
        r["name"]: r for r in _tab(client, "winners")["same_name_different_phones"]["rows"]
    }
    # 9 days apart at venues sharing a 30-day limit
    assert rows["Jane Doe"]["_flag"] is True
    # Different venues with separate limits
    assert rows["Bob Smith"]["_flag"] is False


def _link(db, *phones):
    caller = OnAirCaller()
    db.add(caller)
    db.flush()
    for phone in phones:
        db.add(OnAirCallerPhone(phone=phone, caller_id=caller.id))
    db.commit()


def test_linked_caller_counts_as_one_repeat_winner(client, db, promo, venue):
    show = _show(db, venue, -1, pairs=0, staff=0)
    _win(db, show, "Jane Doe", "5105550100", days_ago=2)
    _win(db, show, "Jane Doe", "5105550111")
    _win(db, show, "Someone", "5105550199")
    m = _tab(client, "winners")
    assert m["top_repeat_winners"]["rows"] == []
    assert m["repeat_winner_share"]["value"] == 0

    _link(db, "5105550100", "5105550111")
    m = _tab(client, "winners")
    rows = m["top_repeat_winners"]["rows"]
    assert len(rows) == 1
    assert rows[0]["wins"] == 2
    assert rows[0]["phones"] == 2
    assert rows[0]["phone"] == "5105550111"
    assert m["repeat_winner_share"]["value"] == pytest.approx(2 / 3)
    venue_rows = _tab(client, "venue", f"&venue_id={venue.id}")["venue_repeat_winners"][
        "rows"
    ]
    assert len(venue_rows) == 1


def test_same_name_status_and_highlight(client, db, promo, venue):
    show = _show(db, venue, -1, pairs=0, staff=0)
    _win(db, show, "Jane Doe", "5105550100", days_ago=2)
    _win(db, show, "Jane Doe", "5105550111")
    _win(db, show, "Bob Smith", "5105550122", days_ago=2)
    _win(db, show, "Bob Smith", "5105550133")
    _win(db, show, "Bob Smith", "5105550144")
    _win(db, show, "Ann Lee", "5105550155", days_ago=2)
    _win(db, show, "Ann Lee", "5105550166")
    _win(db, show, "Cy Young", "5105550177", days_ago=2)
    _win(db, show, "Cy Young", "5105550188")
    _link(db, "5105550100", "5105550111")
    _link(db, "5105550122", "5105550133")
    db.add(DismissedCallerPair(phone_a="5105550155", phone_b="5105550166"))
    db.add(CommonCallerName(name="cy young"))
    db.commit()

    metric = _tab(client, "winners")["same_name_different_phones"]
    rows = {r["name"]: r for r in metric["rows"]}
    assert rows["Jane Doe"]["status"] == "Linked"
    assert rows["Bob Smith"]["status"] == "Partly linked"
    assert rows["Ann Lee"]["status"] == "Dismissed"
    assert rows["Cy Young"]["status"] == "Common name"
    # Only the unresolved group stays highlighted
    assert {n for n, r in rows.items() if r["_flag"]} == {"Bob Smith"}
    name_column = metric["columns"][0]
    assert name_column["external"] is True
    assert name_column["link"].startswith("/pass-giveaway/promotions/admin?caller={name}")


# ---------------------------------------------------------------------------
# Promotions reps and creators


def test_reps_report_and_venue_creators(client, db, promo, venue):
    owner = _staff(db, "owner@example.com", "Promotions")
    db.add(VenueOwner(venue_id=venue.id, staff_id=owner.id))
    promoter = Promoter(name="Promoter")
    db.add(promoter)
    db.commit()
    db.add(PromoterOwner(promoter_id=promoter.id, staff_id=promo.id))
    db.commit()
    own = _show(db, venue, -2, name="Owner's show")
    other = _show(db, venue, -3, name="Someone else's")
    promoted = _show(db, venue, -4, name="Promoter show", promoter=promoter)
    _show(db, venue, -5, name="Imported")
    for show, email in ((own, owner.email), (other, promo.email), (promoted, promo.email)):
        log_event(
            db,
            "show_created",
            actor_email=email,
            entity_type="show",
            entity_id=show.id,
            area=PASS_GIVEAWAY_AREA,
        )

    rows = _tab(client, "reps")["reps_by_month"]["rows"]
    by_rep = {}
    for r in rows:
        by_rep.setdefault(r["rep"], []).append(r)
    assert sum(r["shows"] for r in by_rep["Promo"]) == 2
    assert sum(r["not_owner"] for r in by_rep["Promo"]) == 1
    assert sum(r["not_owner"] for r in by_rep["Owner"]) == 0
    assert "Unknown creator" in by_rep
    flagged = [d for r in by_rep["Promo"] for d in r["_details"]["rows"] if d["_flag"]]
    assert [d["show"] for d in flagged] == ["Someone else's"]

    creators = {
        r["creator"]: r
        for r in _tab(client, "venue", f"&venue_id={venue.id}")["venue_creators"]["rows"]
    }
    assert creators["Owner"]["venue_owner"] == 1
    assert creators["Promo"]["promoter_owner"] == 1
    assert creators["Promo"]["neither"] == 1
    assert creators["Promo"]["_flag"] is True
    assert creators["Unknown creator"]["shows"] == 1


def test_reps_posters_by_venue(client, db, promo, venue):
    alice = _staff(db, "alice@example.com", "Promotions")
    solo = Venue(name="The Chapel", address="2 Main St")
    idle = Venue(name="The Independent", address="3 Main St")
    gone = Venue(name="Gone", address="4 Main St", deleted=True)
    db.add_all([solo, idle, gone])
    db.commit()
    posts = [(venue, promo), (venue, promo), (venue, alice), (solo, alice), (solo, alice)]
    for i, (v, who) in enumerate(posts):
        show = _show(db, v, -(i + 1))
        log_event(
            db,
            "show_created",
            actor_email=who.email,
            entity_type="show",
            entity_id=show.id,
            area=PASS_GIVEAWAY_AREA,
        )
    _show(db, idle, -400)  # outside the window

    metrics = _tab(client, "reps", window="preset=last_30_days")
    rows = {r["venue"]: r for r in metrics["posters_by_venue"]["rows"]}
    assert set(rows) == {"The Fox", "The Chapel"}
    assert rows["The Fox"]["shows"] == 3
    assert rows["The Fox"]["posted_by"] == "Promo 67%, Alice 33%"
    assert [d["shows"] for d in rows["The Fox"]["_details"]["rows"]] == [2, 1]
    assert rows["The Chapel"]["posted_by"] == "Alice"
    assert "_details" not in rows["The Chapel"]

    without = metrics["venues_without_shows"]
    assert without["collapsed"] is True
    assert [r["venue"] for r in without["rows"]] == ["The Independent"]


# ---------------------------------------------------------------------------
# Giveaway page visits


def _visit(client, show_id, visit_id, headers=DJ_GUEST):
    r = client.post(
        "/api/pass-giveaway/analytics/giveaway-visits",
        json={"visit_id": visit_id, "show_id": show_id},
        headers=headers,
    )
    assert r.status_code == 204, r.text


def test_visit_outcomes_best_wins(client, db, promo, venue, on_air):
    show = _show(db, venue, 5, pairs=2)
    pair = db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "pair").first()
    marmot = dict(persona_id=77, name="DJ Marmot")
    db.add(SpinitronPersona(id=77, name="DJ Marmot"))
    db.commit()

    # Opened before DJ Marmot's slot, then moved to them after an early switch
    on_air(None)
    _visit(client, show.id, "visit-aaaa-1111")
    on_air(**marmot)
    client.put(
        "/api/pass-giveaway/analytics/giveaway-visits/visit-aaaa-1111/dj",
        json={"dj_name": "ignored"},
        headers=DJ_GUEST,
    )
    r = client.post(
        f"/api/shows/{show.id}/attempt",
        json={"visit_id": "visit-aaaa-1111"},
        headers=DJ_GUEST,
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/passes/{pair.id}/giveaway",
        json={
            "recipient_name": "Winner",
            "recipient_phone": "510-555-0100",
            "visit_id": "visit-aaaa-1111",
        },
        headers=DJ_GUEST,
    )
    assert r.status_code == 200, r.text
    # A reload continues the same visit
    _visit(client, show.id, "visit-aaaa-1111")

    _visit(client, show.id, "visit-bbbb-2222")
    on_air(None)
    _visit(client, show.id, "visit-cccc-3333")

    visits = (
        db.query(AnalyticsEvent).filter(AnalyticsEvent.event_type == "giveaway_visit").all()
    )
    assert sorted((v.ref, v.dimension, v.persona_id) for v in visits) == [
        ("visit-aaaa-1111", "given_away", 77),
        ("visit-bbbb-2222", "neither", 77),
        ("visit-cccc-3333", "neither", None),
    ]

    djs = {r["dj"]: r for r in _tab(client, "djs")["djs"]["rows"]}
    assert djs["DJ Marmot"]["visits"] == 2
    assert djs["DJ Marmot"]["given_away"] == pytest.approx(0.5)
    assert djs["DJ Marmot"]["dj_key"] == "persona-77"
    assert djs["Unattributed"]["visits"] == 1

    dj_page = _tab(client, "dj", "&dj=persona-77")
    assert dj_page["dj_funnel"]["rows"][0]["visits"] == 2
    assert dj_page["dj_given"]["value"] == 1
    unknown = _tab(client, "dj", "&dj=unknown")
    assert unknown["dj_funnel"]["rows"][0]["visits"] == 1

    venue_funnel = _tab(client, "venue", f"&venue_id={venue.id}")["venue_funnel"]["rows"][0]
    assert venue_funnel["visits"] == 3
    assert venue_funnel["neither"] == pytest.approx(2 / 3)


def test_djs_tab_has_a_row_per_persona_and_show(client, db, promo, venue):
    """Each persona and show is its own row, named as it is now (decision 29)."""
    talk = SpecialtyShow(name="Morning Report", category="talk")
    music = SpecialtyShow(name="Take Five")
    db.add_all([talk, music, SpinitronPersona(id=5, name="DJ Renamed")])
    db.flush()
    show = _show(db, venue, 5, pairs=4)
    credits = [(5, None), (5, None), (None, talk.id), (5, music.id)]
    for p, (persona_id, show_id) in zip(
        db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "pair"), credits
    ):
        p.status = "given_away"
        p.given_away_at = NOW - timedelta(days=1)
        p.given_away_persona_id = persona_id
        p.given_away_specialty_show_id = show_id
    db.add(ShowAttempt(show_id=show.id, specialty_show_id=talk.id, attempted_at=NOW))
    db.commit()

    rows = {r["dj"]: r for r in _tab(client, "djs")["djs"]["rows"]}

    assert {k: (r["given"], r["tried_count"]) for k, r in rows.items()} == {
        "DJ Renamed": (2, 0),
        "Morning Report": (1, 1),
        # A giveaway during a music show counts for the show
        "Take Five": (1, 0),
    }
    talk_page = _tab(client, "dj", f"&dj=show-{talk.id}")
    assert (talk_page["dj_given"]["value"], talk_page["dj_tried"]["value"]) == (1, 1)
    assert rows["DJ Renamed"]["total"] == 2
    assert rows["Morning Report"]["total"] == 2
    overview = _tab(client, "overview")
    assert "top_djs_given" not in overview
    top = overview["top_djs_given_tried"]["rows"]
    assert {(r["dj"], r["total"]) for r in top[:2]} == {
        ("DJ Renamed", 2),
        ("Morning Report", 2),
    }


def test_promotions_preview_is_not_tracked(client, db, promo, venue):
    show = _show(db, venue, 5)
    _visit(client, show.id, "visit-dddd-4444", headers=PROMO)
    assert db.query(AnalyticsEvent).count() == 0


def test_staging_sublist_dj_is_tracked(client, db, venue, monkeypatch):
    monkeypatch.setattr(settings, "environment", "staging")
    dj = _staff(db, "dj@example.com")
    db.add(StaffStatus(staff_id=dj.id, status="Sublist DJ"))
    db.commit()
    show = _show(db, venue, 5)
    _visit(
        client, show.id, "visit-eeee-5555", headers={"X-Forwarded-User": "dj@example.com"}
    )
    event = db.query(AnalyticsEvent).one()
    assert event.actor_email == "dj@example.com"


def test_visit_ids_are_validated(client, db, venue):
    show = _show(db, venue, 5)
    r = client.post(
        "/api/pass-giveaway/analytics/giveaway-visits",
        json={"visit_id": "x", "show_id": show.id},
        headers=DJ_GUEST,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Guest sessions


def test_guest_sessions(client, db, promo):
    for headers, sid in (
        (DJ_GUEST, "sess-aaaa-1"),
        (DJ_GUEST, "sess-aaaa-1"),
        (OFFICE_GUEST, "sess-bbbb-2"),
    ):
        r = client.post(
            "/api/pass-giveaway/analytics/session",
            json={"session_id": sid},
            headers=headers,
        )
        assert r.status_code == 204
    # Signed-in users are counted by active days instead
    client.post(
        "/api/pass-giveaway/analytics/session",
        json={"session_id": "sess-cccc-3"},
        headers=PROMO,
    )
    rows = db.query(AnalyticsEvent).all()
    assert sorted(r.network for r in rows) == ["dj_studio", "station_office"]

    m = _tab(client, "usage")
    day = m["guest_sessions_per_day"]["rows"][-1]
    assert (day["dj_studio"], day["station_office"]) == (1, 1)
    assert sum(c["value"] for c in m["dj_studio_heatmap"]["cells"]) == 1


# ---------------------------------------------------------------------------
# Spin-match popups


def test_spin_suggestions_actions_and_giveaways(client, db, promo, venue):
    show = _show(db, venue, 5)
    other = _show(db, venue, 6)
    dj = tracking.DjTracking(network="dj_studio", actor_email=None)
    tracking.record_spin_suggestions(db, dj, [(1, show.id), (1, other.id)])
    tracking.record_spin_suggestions(db, dj, [(1, show.id), (2, show.id)])  # repeat poll
    assert db.query(AnalyticsEvent).count() == 3

    r = client.post(
        f"/api/dj/spin-matches/1/dismiss?show_id={show.id}&action=clicked", headers=DJ_GUEST
    )
    assert r.status_code == 204
    client.post(
        f"/api/dj/spin-matches/2/dismiss?show_id={show.id}&action=dismissed",
        headers=DJ_GUEST,
    )

    pair = db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "pair").first()
    client.post(
        f"/api/passes/{pair.id}/giveaway",
        json={
            "recipient_name": "W",
            "recipient_phone": "5105550100",
            "given_away_by_dj": "DJ",
        },
        headers=DJ_GUEST,
    )

    rows = {
        r["what"]: r["count"]
        for r in _tab(client, "overview")["spin_match_suggestions"]["rows"]
    }
    assert rows["Suggested"] == 3
    assert rows["Clicked through"] == 1
    assert rows["Dismissed"] == 1
    assert rows["Ignored"] == 1
    assert rows["Pass pairs given away within 2 hours"] == 1


# ---------------------------------------------------------------------------
# Venue page extras


def test_venue_page_extras(client, db, promo, venue):
    show = _show(db, venue, -2, pairs=2, given=1, staff=2, claimed=0, lottery_enabled=True)
    db.add(ShowAttempt(show_id=show.id, attempted_at=NOW))
    pair = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id, Pass.status == "available", Pass.pass_type == "pair"
        )
        .first()
    )
    pair.preassigned_persona_id = add_persona(db, "DJ Marmot")
    db.commit()
    for event_type in ("alternate_joined", "alternate_joined", "alternate_promoted"):
        log_event(db, event_type, details={"show_id": show.id}, area=PASS_GIVEAWAY_AREA)
    for _ in range(2):  # the same phone, show and day count once
        log_event(
            db,
            "winner_frequency_warning",
            entity_type="venue",
            entity_id=venue.id,
            details={"recipient_phone": "5105550100", "show_id": show.id},
            area=PASS_GIVEAWAY_AREA,
        )

    m = _tab(client, "venue", f"&venue_id={venue.id}")
    assert m["venue_announced"]["value"] == pytest.approx(1.0)
    assert m["venue_preassigned"]["value"] == pytest.approx(0.5)
    assert m["venue_unused"]["value"] == 3
    assert m["venue_lead_time"]["value"] == pytest.approx(18, abs=1)
    assert m["venue_alternates"]["value"] == pytest.approx(0.5)
    assert m["venue_win_limits"]["value"] == 1
    assert m["venue_lottery"]["value"] == 0
    r = client.get(f"/api/analytics/tabs/venue?venue_id={venue.id}", headers=PROMO)
    assert r.json()["title"] == "The Fox"


# ---------------------------------------------------------------------------
# Show date placement, announced shows and the per-column ⓘ


def _given(db, show, *, persona_id=None, days_ago=1):
    """Give away one of *show*'s available pass pairs."""
    p = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id, Pass.pass_type == "pair", Pass.status == "available"
        )
        .first()
    )
    p.status = "given_away"
    p.given_away_at = NOW - timedelta(days=days_ago)
    p.given_away_persona_id = persona_id
    db.commit()
    return p


def _window(days_back: int, days_ahead: int) -> str:
    start = today_pacific() - timedelta(days=days_back)
    end = today_pacific() + timedelta(days=days_ahead)
    return f"from={start.isoformat()}&to={end.isoformat()}"


def test_activity_is_placed_by_show_date(client, db, promo, venue):
    """Decision Q1: a giveaway counts in its show's window, not when it happened."""
    db.add(SpinitronPersona(id=9, name="DJ Early"))
    db.commit()
    soon = _show(db, venue, 3, pairs=2)
    long_ago = _show(db, venue, -60, pairs=2)
    # Given away 40 days ago for a show 3 days out
    _given(db, soon, persona_id=9, days_ago=40)
    # Given away yesterday (late entry) for a show 60 days ago
    _given(db, long_ago, persona_id=9, days_ago=1)
    db.add(
        ShowAttempt(show_id=soon.id, persona_id=9, attempted_at=NOW - timedelta(days=50))
    )
    db.add(
        AnalyticsEvent(
            event_type="giveaway_visit",
            area=PASS_GIVEAWAY_AREA,
            occurred_at=NOW - timedelta(days=50),
            entity_type="show",
            entity_id=soon.id,
            dimension="given_away",
            persona_id=9,
        )
    )
    db.commit()

    window = _window(10, 10)
    overview = _tab(client, "overview", window=window)
    assert overview["passes_given_away"]["value"] == 1
    assert overview["giveaway_funnel"]["rows"][0]["visits"] == 1
    [dj] = _tab(client, "djs", window=window)["djs"]["rows"]
    assert (dj["given"], dj["tried_count"], dj["total"], dj["visits"]) == (1, 1, 2, 1)


def test_announced_shows(client, db, promo, venue):
    _show(db, venue, -2, pairs=2, given=1)  # announced: given away
    tried = _show(db, venue, -3, pairs=1)
    for _ in range(3):  # tried three times
        db.add(ShowAttempt(show_id=tried.id, attempted_at=NOW))
    _show(db, venue, -4, pairs=2)  # never announced
    _show(db, venue, 4, pairs=2)  # upcoming: not complete yet
    db.commit()

    window = _window(30, 30)
    card = _tab(client, "overview", window=window)["announced_shows"]
    assert card["value"] == pytest.approx(2 / 3)
    assert card["note"] == "2 of 3 shows"
    [row] = _tab(client, "venues", window=window)["venues"]["rows"]
    assert row["announced"] == pytest.approx(2 / 3)
    assert "attempts_per_giveaway" not in row
    venue_page = _tab(client, "venue", f"&venue_id={venue.id}", window=window)
    assert venue_page["venue_announced"]["value"] == pytest.approx(2 / 3)

    shows = {
        d["show_date"]: d["announced"]
        for r in _tab(client, "reps", window=window)["reps_by_month"]["rows"]
        for d in r["_details"]["rows"]
    }
    # (1 given + 0 tried) ÷ 2 pairs; 3 tries ÷ 1 pair is over 100%
    assert shows[(today_pacific() - timedelta(days=2)).isoformat()] == pytest.approx(0.5)
    assert shows[(today_pacific() - timedelta(days=3)).isoformat()] == pytest.approx(3.0)


# Plain name columns don't need an ⓘ (decision Q10)
NAME_COLUMNS = {
    "venue",
    "dj",
    "name",
    "show",
    "month",
    "rep",
    "creator",
    "poster",
    "group",
    "what",
    "weekday",
    "time",
    "slug",
    "subsite",
    "day",
    "week",
}


def test_every_column_has_an_explanation(client, db, promo, venue):
    show = _show(db, venue, -2, pairs=2, given=1)
    _win(db, show, "Jane Doe", "5105550100")
    _win(db, show, "Jane Doe", "5105550111")
    win_id = db.query(OnAirWinner.id).first()[0]
    pages = [
        ("overview", ""),
        ("venues", ""),
        ("venue", f"&venue_id={venue.id}"),
        ("djs", ""),
        ("dj", "&dj=unknown"),
        ("winners", ""),
        ("winner", f"&win_id={win_id}"),
        ("reps", ""),
        ("short_links", ""),
        ("usage", ""),
    ]
    missing = []
    for tab, query in pages:
        for metric in _tab(client, tab, query).values():
            if metric["kind"] != "table":
                continue
            columns = list(metric["columns"])
            for row in metric["rows"]:
                columns += (row.get("_details") or {}).get("columns", [])
            for c in columns:
                if c["key"] not in NAME_COLUMNS and not c.get("help"):
                    missing.append(f"{tab}/{metric['id']}/{c['key']}")
    assert missing == []


# ---------------------------------------------------------------------------
# On-air winners tab, win-limit blocks and winner pages


def _warn(db, show, phone, days_ago=1):
    db.add(
        AuditLog(
            event_type="winner_frequency_warning",
            area=PASS_GIVEAWAY_AREA,
            occurred_at=NOW - timedelta(days=days_ago, hours=1),
            entity_type="venue",
            entity_id=show.venue_id,
            details={"recipient_phone": phone, "show_id": show.id},
        )
    )
    db.commit()


def _winner_of(db, show, name, phone, days_ago=1):
    _win(db, show, name, phone, days_ago=days_ago)
    return db.query(OnAirWinner).order_by(OnAirWinner.id.desc()).first()


def test_winners_tab_and_blocks(client, db, promo, venue):
    old = _show(db, venue, -20, pairs=0, staff=0, name="Old show")
    new = _show(db, venue, -2, pairs=0, staff=0, name="New show")
    _winner_of(db, old, "Jane Doe", "5105550100", days_ago=21)
    _winner_of(db, old, "Bob Smith", "5105550122", days_ago=21)
    _winner_of(db, old, "Cy Young", "5105550177", days_ago=21)
    # Jane is warned twice the same day (counted once), then wins on another number
    _warn(db, new, "510-555-0100", days_ago=3)
    _warn(db, new, "5105550100", days_ago=3)
    _winner_of(db, new, "Jane Doe", "5105550111", days_ago=3)
    # Bob is warned and the DJ overrides it
    _warn(db, new, "5105550122", days_ago=3)
    bob = _winner_of(db, new, "Bob Smith", "5105550122", days_ago=3)
    log_event(
        db,
        "venue_frequency_override",
        entity_type="pass",
        entity_id=bob.pass_id,
        area=PASS_GIVEAWAY_AREA,
    )
    # Cy is warned and doesn't win
    _warn(db, new, "5105550177", days_ago=3)

    window = _window(10, 10)
    m = _tab(client, "winners", window=window)
    blocks = {r["name"]: r for r in m["blocked_by_win_limit"]["rows"]}
    assert {n: r["outcome"] for n, r in blocks.items()} == {
        "Jane Doe": "Won with another number",
        "Bob Smith": "Overridden",
        "Cy Young": "Blocked",
    }
    assert {n for n, r in blocks.items() if r["_flag"]} == {"Jane Doe", "Cy Young"}
    assert m["win_limit_blocks"]["value"] == 3
    assert m["blocked_by_win_limit"]["columns"][0]["link"] == "/winners/{win_id}"

    winners = {r["name"]: r for r in m["winners"]["rows"]}
    # Cy has a block in the window but no win in it
    assert set(winners) == {"Jane Doe", "Bob Smith"}
    assert (winners["Bob Smith"]["wins"], winners["Bob Smith"]["all_time"]) == (1, 2)
    assert winners["Bob Smith"]["blocks"] == 1
    assert m["winners_count"]["value"] == 2
    assert "top_repeat_winners" in m and "same_name_different_phones" in m

    # Cy's page is reachable from the block even without a win in the window
    page = _tab(client, "winner", f"&win_id={blocks['Cy Young']['win_id']}", window=window)
    assert page["winner_wins_window"]["value"] == 0
    assert page["winner_wins_all_time"]["value"] == 1
    assert page["winner_blocks"]["value"] == 1
    assert page["winner_blocks_table"]["rows"][0]["outcome"] == "Blocked"
    r = client.get(
        f"/api/analytics/tabs/winner?win_id={blocks['Cy Young']['win_id']}", headers=PROMO
    )
    assert r.json()["title"] == "Cy Young"

    venue_page = _tab(client, "venue", f"&venue_id={venue.id}", window=window)
    assert venue_page["venue_win_limits"]["value"] == 3
    assert venue_page["venue_win_limits"]["note"] == "1 overrides"


def test_winner_page_covers_a_linked_caller(client, db, promo, venue):
    show = _show(db, venue, -2, pairs=0, staff=0)
    far = _show(db, venue, -200, pairs=0, staff=0)
    first = _winner_of(db, far, "Jane Doe", "5105550100", days_ago=201)
    _winner_of(db, show, "Jane D.", "5105550111")
    _link(db, "5105550100", "5105550111")

    window = _window(10, 10)
    page = _tab(client, "winner", f"&win_id={first.id}", window=window)
    assert page["winner_wins_all_time"]["value"] == 2
    assert page["winner_wins_window"]["value"] == 1
    # Latest first, with the window's wins highlighted
    assert [(r["winner"], r["_flag"]) for r in page["winner_wins"]["rows"]] == [
        ("Jane D.", True),
        ("Jane Doe", False),
    ]
    phones = {r["phone"]: r for r in page["winner_phones"]["rows"]}
    assert set(phones) == {"5105550100", "5105550111"}
    assert all(r["linked"] == "Yes" for r in phones.values())
    assert page["winner_phones"]["columns"][1]["external"] is True

    assert _tab(client, "winner", "&win_id=999") == {}
    rows = _tab(client, "winners", window=window)["winners"]["rows"]
    assert [(r["name"], r["all_time"]) for r in rows] == [("Jane D.", 2)]
