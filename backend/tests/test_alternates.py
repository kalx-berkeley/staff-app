"""Tests for the staff-pass alternate queue."""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.lottery_entry import LotteryEntry
from app.models.notification_preferences import NotificationPreferences
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_pass_alternate import StaffPassAlternate
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.services.alternate_service import AlternateService
from app.services.lottery_service import LotteryService
from app.services.pass_service import PassService

SEND_EMAIL = "app.services.notification_service.send_email"

# ── Fixtures & helpers ────────────────────────────────────────────────────────


@pytest.fixture
def venue(db: Session):
    v = Venue(name="Alt Venue", address="1 Queue St")
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@pytest.fixture
def promo(db: Session):
    staff = Staff(email="promo@alt.test", name="Pat Promo", phone="555-0001")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


def _make_staff(db: Session, name: str) -> Staff:
    staff = Staff(email=f"{name.lower()}@alt.test", name=name, phone="555-0000")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def people(db: Session):
    return {n: _make_staff(db, n) for n in ["Ann", "Ben", "Cat", "Dan", "Eve"]}


def _make_show(db: Session, venue: Venue, staff_passes: int, **kwargs) -> Show:
    show = Show(
        event_name="Alt Show",
        venue_id=venue.id,
        show_date=date.today() + timedelta(days=30),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=staff_passes,
        status=kwargs.pop("status", "published"),
        published_at=datetime.now(timezone.utc) - timedelta(days=1),
        **kwargs,
    )
    db.add(show)
    db.commit()
    db.refresh(show)
    for _ in range(staff_passes):
        db.add(Pass(show_id=show.id, pass_type="staff", status="available"))
    db.commit()
    return show


def _h(staff: Staff) -> dict:
    return {"X-Forwarded-User": staff.email}


def _first_available(db: Session, show: Show) -> Pass:
    return (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id, Pass.pass_type == "staff", Pass.status == "available"
        )
        .order_by(Pass.id)
        .first()
    )


def _claim(client, db, show, staff, **body) -> Pass:
    p = _first_available(db, show)
    resp = client.post(f"/api/passes/{p.id}/claim", json=body, headers=_h(staff))
    assert resp.status_code == 200, resp.text
    return p


def _primary(db: Session, show: Show, staff: Staff) -> Pass | None:
    db.expire_all()
    return (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "staff",
            Pass.staff_id == staff.id,
            Pass.status == "claimed",
            Pass.guest_of_pass_id.is_(None),
        )
        .first()
    )


def _guest_hold(db: Session, primary: Pass) -> Pass | None:
    return db.query(Pass).filter(Pass.guest_of_pass_id == primary.id).first()


def _release(client, staff, pass_item):
    resp = client.delete(f"/api/passes/{pass_item.id}/claim", headers=_h(staff))
    assert resp.status_code == 200, resp.text


def _join(client, show, staff, **body):
    return client.post(f"/api/shows/{show.id}/alternates", json=body, headers=_h(staff))


def _queue(client, show, staff):
    resp = client.get(f"/api/shows/{show.id}/alternates", headers=_h(staff))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _queue_names(client, show, staff) -> list[str]:
    return [e["staff_name"] for e in _queue(client, show, staff)["entries"]]


def _add_waiting(db, show, staff, minutes_ago=0, **kwargs) -> StaffPassAlternate:
    """Insert a waiting entry directly (for states the API can't reach in one step)."""
    now = datetime.now(timezone.utc)
    entry = StaffPassAlternate(
        show_id=show.id,
        staff_id=staff.id,
        priority_at=now - timedelta(minutes=minutes_ago),
        status="waiting",
        created_at=now,
        updated_at=now,
        **kwargs,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _emails_to(mock_send, staff: Staff) -> list[dict]:
    return [
        c.kwargs
        for c in mock_send.call_args_list
        if c.kwargs.get("to_email") == staff.email
    ]


# ── Opening the queue ─────────────────────────────────────────────────────────


class TestQueueOpen:
    def test_closed_while_passes_available(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        assert _queue(client, show, people["Ann"])["queue_open"] is False
        assert _join(client, show, people["Ann"]).status_code == 409

    def test_closed_while_guest_hold_exists(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        with patch(SEND_EMAIL):
            _claim(client, db, show, people["Ann"], has_guest=True)
        assert _queue(client, show, people["Ben"])["queue_open"] is False
        assert _join(client, show, people["Ben"]).status_code == 409

    def test_open_when_all_held_by_staff(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        _claim(client, db, show, people["Ann"])
        assert _queue(client, show, people["Ben"])["queue_open"] is True

        resp = _join(client, show, people["Ben"], has_guest=True, guest_name="Ben+1")
        assert resp.status_code == 201, resp.text
        assert resp.json()["position"] == 1

    def test_rejects_duplicate_and_claimer(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        _claim(client, db, show, people["Ann"])
        assert _join(client, show, people["Ben"]).status_code == 201
        assert _join(client, show, people["Ben"]).status_code == 400
        assert _join(client, show, people["Ann"]).status_code == 400

    def test_closed_during_active_lottery(self, client, db, venue, people):
        show = _make_show(
            db,
            venue,
            1,
            lottery_enabled=True,
            lottery_window_hours=48,
        )
        db.query(Pass).filter(Pass.show_id == show.id).update(
            {"status": "claimed", "staff_id": people["Ann"].id}
        )
        db.commit()
        assert _queue(client, show, people["Ben"])["queue_open"] is False

    def test_requires_guest_name_when_venue_does(self, client, db, venue, people):
        venue.staff_guest_requires_name = True
        db.commit()
        show = _make_show(db, venue, 1)
        _claim(client, db, show, people["Ann"])
        assert _join(client, show, people["Ben"], has_guest=True).status_code == 400
        assert (
            _join(client, show, people["Ben"], has_guest=True, guest_name="Bo").status_code
            == 201
        )


# ── Promotion ─────────────────────────────────────────────────────────────────


class TestPromotion:
    def test_release_promotes_first_alternate(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        p = _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"])
        _join(client, show, people["Cat"])

        with patch(SEND_EMAIL) as mock_send:
            _release(client, people["Ann"], p)

        assert _primary(db, show, people["Ben"]) is not None
        assert _queue_names(client, show, people["Ann"]) == ["Cat"]
        emails = _emails_to(mock_send, people["Ben"])
        assert len(emails) == 1
        assert "You got a staff pass" in emails[0]["subject"]
        assert not _emails_to(mock_send, people["Cat"])

        audit = db.query(AuditLog).filter(AuditLog.event_type == "alternate_promoted").one()
        assert audit.details["trigger"] == "release"
        assert audit.details["staff_id"] == people["Ben"].id
        assert audit.actor_email == people["Ann"].email

    def test_promotions_release_on_behalf_promotes(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        p = _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"])
        with patch(SEND_EMAIL):
            _release(client, promo, p)
        assert _primary(db, show, people["Ben"]) is not None

    def test_only_with_guest_skipped_but_keeps_place(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        p = _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"], has_guest=True, only_attend_with_guest=True)
        _join(client, show, people["Cat"])

        with patch(SEND_EMAIL):
            _release(client, people["Ann"], p)

        assert _primary(db, show, people["Cat"]) is not None
        assert _primary(db, show, people["Ben"]) is None
        assert _queue_names(client, show, people["Ann"]) == ["Ben"]

    def test_only_with_guest_gets_pair_when_two_free(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        pa = _claim(client, db, show, people["Ann"])
        pd = _claim(client, db, show, people["Dan"])
        _join(
            client,
            show,
            people["Ben"],
            has_guest=True,
            guest_name="Ben+1",
            only_attend_with_guest=True,
        )

        with patch(SEND_EMAIL):
            _release(client, people["Ann"], pa)
        # One free pass can't seat a pair; it stays available for anyone.
        assert _primary(db, show, people["Ben"]) is None
        assert _first_available(db, show) is not None
        assert _queue_names(client, show, people["Dan"]) == ["Ben"]

        with patch(SEND_EMAIL):
            _release(client, people["Dan"], pd)
        ben = _primary(db, show, people["Ben"])
        assert ben is not None and ben.has_guest and ben.guest_name == "Ben+1"
        assert _guest_hold(db, ben) is not None

    def test_guest_dropped_when_others_waiting(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        pa = _claim(client, db, show, people["Ann"])
        _claim(client, db, show, people["Dan"])
        _join(client, show, people["Ben"], has_guest=True, guest_name="Ben+1")
        _join(client, show, people["Cat"])

        with patch(SEND_EMAIL) as mock_send:
            _release(client, people["Ann"], pa)

        ben = _primary(db, show, people["Ben"])
        assert ben is not None and ben.has_guest is False
        body = _emails_to(mock_send, people["Ben"])[0]["body_text"]
        assert "guest request has been dropped" in body

    def test_guest_granted_when_queue_drains(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim(client, db, show, people["Ann"])
        _claim(client, db, show, people["Dan"])
        _join(client, show, people["Ben"], has_guest=True, guest_name="Ben+1")

        with patch(SEND_EMAIL) as mock_send:
            PassService.adjust_passes_for_show(db, show, 4)

        ben = _primary(db, show, people["Ben"])
        assert ben is not None and ben.has_guest and _guest_hold(db, ben) is not None
        assert (
            "has also been reserved" in _emails_to(mock_send, people["Ben"])[0]["body_text"]
        )

    def test_seat_displaces_guest_hold_and_cascades(self, client, db, venue, people):
        show = _make_show(db, venue, 3)
        with patch(SEND_EMAIL):
            _claim(
                client,
                db,
                show,
                people["Ann"],
                has_guest=True,
                guest_name="Ann+1",
                only_attend_with_guest=True,
            )
        pd = _claim(client, db, show, people["Dan"])
        # Guest holds normally close the queue; reach this state directly.
        _add_waiting(db, show, people["Ben"], minutes_ago=2)
        _add_waiting(db, show, people["Cat"], minutes_ago=1)

        with patch(SEND_EMAIL) as mock_send:
            _release(client, people["Dan"], pd)

        assert _primary(db, show, people["Ben"]) is not None
        assert _primary(db, show, people["Cat"]) is not None
        # Ann only wanted to go with her guest, so she was released too.
        assert _primary(db, show, people["Ann"]) is None
        assert _first_available(db, show) is not None
        ann_mail = _emails_to(mock_send, people["Ann"])[0]
        assert "released" in ann_mail["subject"]
        assert f"/pass-giveaway/staff/shows/{show.id}" in ann_mail["body_text"]

    def test_direct_claim_ends_waiting_entry(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        pa = _claim(client, db, show, people["Ann"])
        _claim(client, db, show, people["Dan"])
        _join(client, show, people["Ben"], has_guest=True, only_attend_with_guest=True)
        with patch(SEND_EMAIL):
            _release(client, people["Ann"], pa)

        _claim(client, db, show, people["Ben"])
        assert _queue(client, show, people["Ben"])["entries"] == []

    def test_email_disabled_suppresses_promotion_email(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        p = _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"])
        db.add(NotificationPreferences(staff_id=people["Ben"].id, email_enabled=False))
        db.commit()
        with patch(SEND_EMAIL) as mock_send:
            _release(client, people["Ann"], p)
        assert _primary(db, show, people["Ben"]) is not None
        assert not _emails_to(mock_send, people["Ben"])

    def test_next_candidate_for_claimer(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"])
        q = _queue(client, show, people["Ann"])
        assert q["next_candidate_name"] == "Ben"
        assert _queue(client, show, people["Ben"])["next_candidate_name"] is None


# ── Capacity changes ─────────────────────────────────────────────────────────


class TestCapacity:
    def test_decrease_cuts_newest_claim_to_top_of_queue(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim(client, db, show, people["Ann"])
        _claim(client, db, show, people["Dan"])
        _join(client, show, people["Ben"])

        with patch(SEND_EMAIL) as mock_send:
            PassService.adjust_passes_for_show(db, show, 1)
        assert _primary(db, show, people["Ann"]) is not None
        assert _primary(db, show, people["Dan"]) is None
        assert _queue_names(client, show, people["Ann"]) == ["Dan", "Ben"]
        [dan_mail] = _emails_to(mock_send, people["Dan"])
        assert "has been removed" in dan_mail["subject"]
        assert "alternate #1" in dan_mail["body_text"]
        assert not _emails_to(mock_send, people["Ann"])

        with patch(SEND_EMAIL):
            PassService.adjust_passes_for_show(db, show, 2)
        assert _primary(db, show, people["Dan"]) is not None
        assert _queue_names(client, show, people["Ann"]) == ["Ben"]


# ── Lottery ───────────────────────────────────────────────────────────────────


def _lottery_show(db, venue, staff_passes) -> Show:
    show = _make_show(
        db, venue, staff_passes, lottery_enabled=True, lottery_window_hours=24
    )
    show.published_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    return show


def _enter(db, show, staff, minutes_ago, **kwargs) -> LotteryEntry:
    now = datetime.now(timezone.utc)
    entry = LotteryEntry(
        show_id=show.id,
        entry_type="staff",
        staff_id=staff.id,
        status="pending",
        entered_at=now - timedelta(minutes=minutes_ago),
        created_at=now,
        updated_at=now,
        **kwargs,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _run_ordered(db, show, order):
    def fake_shuffle(lst):
        if lst and isinstance(lst[0], LotteryEntry):
            ids = [e.id for e in order]
            lst.sort(key=lambda e: ids.index(e.id) if e.id in ids else len(ids))

    with patch("random.shuffle", side_effect=fake_shuffle):
        return LotteryService.run_lottery(db, show.id)


class TestLottery:
    def test_losers_queued_in_entry_order(self, client, db, venue, people):
        show = _lottery_show(db, venue, 1)
        ann = _enter(db, show, people["Ann"], 30)
        cat = _enter(db, show, people["Cat"], 10)
        ben = _enter(db, show, people["Ben"], 20, has_guest=True, guest_name="Ben+1")

        with patch(SEND_EMAIL) as mock_send:
            _run_ordered(db, show, [ann, cat, ben])

        assert _queue_names(client, show, people["Ann"]) == ["Ben", "Cat"]
        queued_ben = AlternateService.get_waiting_entry(db, show.id, people["Ben"].id)
        assert queued_ben.has_guest and queued_ben.guest_name == "Ben+1"
        assert queued_ben.source == "lottery"
        assert "alternate #1" in _emails_to(mock_send, people["Ben"])[0]["body_text"]
        assert "alternate #2" in _emails_to(mock_send, people["Cat"])[0]["body_text"]

        # Promotion works even while the (already drawn) lottery window is open.
        with patch(SEND_EMAIL):
            _release(client, people["Ann"], _primary(db, show, people["Ann"]))
        assert _primary(db, show, people["Ben"]) is not None

    def test_loser_promoted_in_same_run_gets_one_email(self, client, db, venue, people):
        show = _lottery_show(db, venue, 2)
        ann = _enter(
            db, show, people["Ann"], 30, has_guest=True, only_attend_with_guest=True
        )
        ben = _enter(db, show, people["Ben"], 20)
        cat = _enter(db, show, people["Cat"], 10)

        with patch(SEND_EMAIL) as mock_send:
            _run_ordered(db, show, [ann, ben, cat])

        assert _primary(db, show, people["Ben"]) is not None
        assert _primary(db, show, people["Cat"]) is not None
        cat_mail = _emails_to(mock_send, people["Cat"])
        assert len(cat_mail) == 1 and "You got a staff pass" in cat_mail[0]["subject"]
        assert _queue_names(client, show, people["Ben"]) == ["Ann"]


# ── Show lifecycle ────────────────────────────────────────────────────────────


class TestLifecycle:
    def test_close_expires_and_reopen_restores(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"])
        _join(client, show, people["Cat"])

        with patch(SEND_EMAIL) as mock_send:
            assert (
                client.post(f"/api/shows/{show.id}/close", headers=_h(promo)).status_code
                == 200
            )
        assert _queue_names(client, show, people["Ann"]) == []
        assert "No staff pass" in _emails_to(mock_send, people["Ben"])[0]["subject"]

        with patch(SEND_EMAIL) as mock_send:
            assert (
                client.post(f"/api/shows/{show.id}/reopen", headers=_h(promo)).status_code
                == 200
            )
        assert _queue_names(client, show, people["Ann"]) == ["Ben", "Cat"]
        assert "alternate #2" in _emails_to(mock_send, people["Cat"])[0]["body_text"]

    def test_close_side_effects_shared_by_auto_close(self, db, venue, people):
        from app.routers.shows import run_close_side_effects

        show = _make_show(db, venue, 1)
        _add_waiting(db, show, people["Ben"])
        show.status = "closed"
        db.commit()
        with patch(SEND_EMAIL) as mock_send:
            run_close_side_effects(db, show)
        assert _emails_to(mock_send, people["Ben"])
        assert AlternateService.waiting_entries(db, show.id) == []

    def test_unpublish_freezes_and_publish_fills(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        p = _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"])

        assert (
            client.post(f"/api/shows/{show.id}/unpublish", headers=_h(promo)).status_code
            == 200
        )
        with patch(SEND_EMAIL):
            _release(client, people["Ann"], p)
        assert _primary(db, show, people["Ben"]) is None

        with patch(SEND_EMAIL):
            assert (
                client.post(f"/api/shows/{show.id}/publish", headers=_h(promo)).status_code
                == 200
            )
        assert _primary(db, show, people["Ben"]) is not None

    def test_delete_cancels_queue_and_emails_everyone(
        self, client, db, venue, people, promo
    ):
        show = _make_show(db, venue, 1)
        _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"])

        with patch(SEND_EMAIL) as mock_send:
            assert (
                client.delete(f"/api/shows/{show.id}", headers=_h(promo)).status_code == 204
            )
        assert "cancelled" in _emails_to(mock_send, people["Ann"])[0]["subject"]
        assert "cancelled" in _emails_to(mock_send, people["Ben"])[0]["subject"]
        entry = db.query(StaffPassAlternate).filter_by(staff_id=people["Ben"].id).one()
        assert entry.status == "cancelled"


# ── Editing, leaving, removal, My Passes ─────────────────────────────────────


class TestMembership:
    def test_edit_keeps_place_and_rejoin_goes_to_bottom(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"])
        _join(client, show, people["Cat"])

        resp = client.patch(
            f"/api/shows/{show.id}/alternates/me",
            json={"has_guest": True, "guest_name": "Ben+1"},
            headers=_h(people["Ben"]),
        )
        assert resp.status_code == 200 and resp.json()["position"] == 1

        assert (
            client.delete(
                f"/api/shows/{show.id}/alternates/me", headers=_h(people["Ben"])
            ).status_code
            == 204
        )
        _join(client, show, people["Ben"])
        assert _queue_names(client, show, people["Ann"]) == ["Cat", "Ben"]

    def test_promotions_remove_emails_with_remover_name(
        self, client, db, venue, people, promo
    ):
        show = _make_show(db, venue, 1)
        _claim(client, db, show, people["Ann"])
        entry_id = _join(client, show, people["Ben"]).json()["id"]

        url = f"/api/shows/{show.id}/alternates/{entry_id}"
        assert client.delete(url, headers=_h(people["Cat"])).status_code == 403

        with patch(SEND_EMAIL) as mock_send:
            assert client.delete(url, headers=_h(promo)).status_code == 204
        assert "Pat Promo" in _emails_to(mock_send, people["Ben"])[0]["body_text"]
        assert _queue_names(client, show, people["Ann"]) == []

    def test_my_entries(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"])
        _join(client, show, people["Cat"])
        resp = client.get("/api/shows/alternates/my-entries", headers=_h(people["Cat"]))
        assert resp.status_code == 200
        [entry] = resp.json()
        assert entry["position"] == 2
        assert entry["show_event_name"] == "Alt Show"


class TestReleaseOwnership:
    def test_staff_cannot_release_someone_elses_claim(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        p = _claim(client, db, show, people["Ann"])
        resp = client.delete(f"/api/passes/{p.id}/claim", headers=_h(people["Ben"]))
        assert resp.status_code == 403
        assert _primary(db, show, people["Ann"]) is not None

    def test_promotions_can_release_on_behalf(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        p = _claim(client, db, show, people["Ann"])
        with patch(SEND_EMAIL):
            _release(client, promo, p)
        assert _primary(db, show, people["Ann"]) is None
