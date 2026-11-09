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
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.promoter import Promoter
from app.models.promoter_owner import PromoterOwner
from app.models.show import Show
from app.models.show_attempt import ShowAttempt
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.models.venue_owner import VenueOwner
from app.pass_giveaway.services import tracking

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
                given_away_by_dj="DJ Marmot" if i < given else None,
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


def test_weekday_time_and_promoter_breakdowns(client, db, promo, venue):
    promoter = Promoter(name="Another Planet")
    db.add(promoter)
    db.commit()
    _show(db, venue, -2, given=1, promoter=promoter)
    _show(db, venue, -3, given=0, show_time=None)
    m = _tab(client, "overview")
    times = {r["time"]: r for r in m["utilization_by_show_time"]["rows"]}
    assert set(times) == {"6–9pm", "Unknown"}
    assert [r["promoter"] for r in m["utilization_by_promoter"]["rows"]] == [
        "Another Planet"
    ]
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
    assert m["top_staff_claimants"]["rows"] == [{"name": "A", "claims": 1}]


# ---------------------------------------------------------------------------
# Winners


def _win(db, show, name, phone, email=None, days_ago=1):
    p = Pass(
        show_id=show.id, pass_type="pair", status="given_away", given_away_by_dj="DJ X"
    )
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
            given_away_by_dj="DJ X",
            created_at=NOW - timedelta(days=days_ago),
        )
    )
    db.commit()


def test_repeat_winners_and_share(client, db, promo, venue):
    show = _show(db, venue, -1, pairs=0, staff=0)
    _win(db, show, "Jane Doe", "5105550100")
    _win(db, show, "Jane D", "5105550100")
    _win(db, show, "Someone", "5105550199")
    m = _tab(client, "overview")
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

    rows = _tab(client, "overview")["same_name_different_phones"]["rows"]
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


# ---------------------------------------------------------------------------
# Giveaway page visits


def _visit(client, show_id, visit_id, dj_name="DJ Marmot", headers=DJ_GUEST):
    r = client.post(
        "/api/pass-giveaway/analytics/giveaway-visits",
        json={"visit_id": visit_id, "show_id": show_id, "dj_name": dj_name},
        headers=headers,
    )
    assert r.status_code == 204, r.text


def test_visit_outcomes_best_wins(client, db, promo, venue):
    show = _show(db, venue, 5, pairs=2)
    pair = db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "pair").first()

    _visit(client, show.id, "visit-aaaa-1111", dj_name="")
    client.put(
        "/api/pass-giveaway/analytics/giveaway-visits/visit-aaaa-1111/dj",
        json={"dj_name": "dj  marmot"},
        headers=DJ_GUEST,
    )
    r = client.post(
        f"/api/shows/{show.id}/attempt",
        json={"dj_name": "DJ Marmot", "visit_id": "visit-aaaa-1111"},
        headers=DJ_GUEST,
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/passes/{pair.id}/giveaway",
        json={
            "recipient_name": "Winner",
            "recipient_phone": "510-555-0100",
            "given_away_by_dj": "DJ Marmot",
            "visit_id": "visit-aaaa-1111",
        },
        headers=DJ_GUEST,
    )
    assert r.status_code == 200, r.text
    # A reload continues the same visit
    _visit(client, show.id, "visit-aaaa-1111")

    _visit(client, show.id, "visit-bbbb-2222", dj_name="DJ Marmot")
    _visit(client, show.id, "visit-cccc-3333", dj_name="")

    visits = (
        db.query(AnalyticsEvent).filter(AnalyticsEvent.event_type == "giveaway_visit").all()
    )
    assert sorted((v.ref, v.dimension, v.dj_name) for v in visits) == [
        ("visit-aaaa-1111", "given_away", "dj marmot"),
        ("visit-bbbb-2222", "neither", "dj marmot"),
        ("visit-cccc-3333", "neither", None),
    ]

    djs = {r["dj"]: r for r in _tab(client, "djs")["djs"]["rows"]}
    assert djs["DJ Marmot"]["visits"] == 2
    assert djs["DJ Marmot"]["given_away"] == pytest.approx(0.5)
    assert djs["Unknown DJ"]["visits"] == 1

    dj_page = _tab(client, "dj", "&dj=dj%20marmot")
    assert dj_page["dj_funnel"]["rows"][0]["visits"] == 2
    assert dj_page["dj_given"]["value"] == 1
    unknown = _tab(client, "dj", "&dj=unknown")
    assert unknown["dj_funnel"]["rows"][0]["visits"] == 1

    venue_funnel = _tab(client, "venue", f"&venue_id={venue.id}")["venue_funnel"]["rows"][0]
    assert venue_funnel["visits"] == 3
    assert venue_funnel["neither"] == pytest.approx(2 / 3)


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
    db.add(ShowAttempt(show_id=show.id, dj_name="DJ Marmot", attempted_at=NOW))
    pair = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id, Pass.status == "available", Pass.pass_type == "pair"
        )
        .first()
    )
    pair.preassigned_dj = "DJ Marmot"
    db.commit()
    for event_type in ("alternate_joined", "alternate_joined", "alternate_promoted"):
        log_event(db, event_type, details={"show_id": show.id}, area=PASS_GIVEAWAY_AREA)
    log_event(
        db,
        "winner_frequency_warning",
        entity_type="venue",
        entity_id=venue.id,
        area=PASS_GIVEAWAY_AREA,
    )

    m = _tab(client, "venue", f"&venue_id={venue.id}")
    assert m["venue_attempts"]["value"] == pytest.approx(1.0)
    assert m["venue_preassigned"]["value"] == pytest.approx(0.5)
    assert m["venue_unused"]["value"] == 3
    assert m["venue_lead_time"]["value"] == pytest.approx(18, abs=1)
    assert m["venue_alternates"]["value"] == pytest.approx(0.5)
    assert m["venue_win_limits"]["value"] == 1
    assert m["venue_lottery"]["value"] == 0
    r = client.get(f"/api/analytics/tabs/venue?venue_id={venue.id}", headers=PROMO)
    assert r.json()["title"] == "The Fox"
