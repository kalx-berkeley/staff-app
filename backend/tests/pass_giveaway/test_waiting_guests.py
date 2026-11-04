"""Tests for +1 guests waiting on the staff pass alternate list."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.notification_preferences import NotificationPreferences
from app.models.pass_model import Pass
from app.models.show import Show
from app.pass_giveaway.services.alternate_service import AlternateService
from app.pass_giveaway.services.pass_service import PassService
from app.pass_giveaway.services.show_service import ShowService
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from tests.pass_giveaway.test_alternates import (
    SEND_EMAIL,
    _add_waiting,
    _emails_to,
    _enter,
    _first_available,
    _guest_hold,
    _h,
    _join,
    _lottery_show,
    _make_show,
    _make_staff,
    _primary,
    _queue,
    _release,
    _run_ordered,
)


@pytest.fixture
def venue(db: Session) -> Venue:
    v = Venue(name="Alt Venue", address="1 Queue St")
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@pytest.fixture
def promo(db: Session) -> Staff:
    staff = Staff(email="promo@alt.test", name="Pat Promo", phone="555-0001")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def people(db: Session):
    names = ["Ann", "Ben", "Cat", "Dan", "Eve", "Fay"]
    return {n: _make_staff(db, n) for n in names}


def _claim(client, db, show, staff, **body) -> Pass:
    """Claim a pass, with email patched because claiming may bump someone's guest."""
    with patch(SEND_EMAIL):
        pass_id = _claimable_pass_id(db, show)
        resp = client.post(f"/api/passes/{pass_id}/claim", json=body, headers=_h(staff))
    assert resp.status_code == 200, resp.text
    return _primary(db, show, staff)


def _claimable_pass_id(db: Session, show: Show) -> int:
    """A free pass or, failing that, a guest hold."""
    passes = db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "staff")
    available = passes.filter(Pass.status == "available").first()
    if available:
        return available.id
    return passes.filter(Pass.guest_of_pass_id.isnot(None)).first().id


def _claim_with_guest(client, db, show, staff, fallback="wait", name=None) -> Pass:
    return _claim(
        client,
        db,
        show,
        staff,
        has_guest=True,
        guest_name=name or f"{staff.name}+1",
        guest_fallback=fallback,
    )


def _waiting_names(db: Session, show: Show) -> list[str]:
    return [p.guest_name for p in AlternateService.waiting_guests(db, show.id)]


class TestBumpedToTheList:
    def test_wait_keeps_the_host_and_the_guest_waits(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim_with_guest(client, db, show, people["Ann"])

        _claim(client, db, show, people["Ben"])

        db.refresh(ann)
        assert ann.status == "claimed" and ann.staff_id == people["Ann"].id
        assert ann.guest_waiting and not ann.has_guest
        assert ann.guest_name == "Ann+1"
        assert ann.guest_position == 1
        assert _guest_hold(db, ann) is None

    def test_host_is_emailed_their_guests_position(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")

        with patch(SEND_EMAIL) as mock_send:
            resp = client.post(
                f"/api/passes/{_claimable_pass_id(db, show)}/claim",
                json={},
                headers=_h(people["Ben"]),
            )
        assert resp.status_code == 200, resp.text

        email = _emails_to(mock_send, people["Ann"])[0]
        assert "alternate list" in email["subject"]
        assert "guest #1" in email["body_text"]
        assert "your pass will be released too" in email["body_text"]

    def test_attend_alone_guest_is_still_dropped(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim_with_guest(client, db, show, people["Ann"], "attend_alone")
        _claim(client, db, show, people["Ben"])
        db.refresh(ann)
        assert not ann.guest_waiting and ann.guest_name is None
        assert ann.status == "claimed"

    def test_release_fallback_still_releases_both(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"], "release")
        _claim(client, db, show, people["Ben"])
        assert _primary(db, show, people["Ann"]) is None

    @pytest.mark.parametrize("fallback", ["attend_alone", "release", "wait"])
    def test_bumped_email_respects_email_setting(self, client, db, venue, people, fallback):
        db.add(NotificationPreferences(staff_id=people["Ann"].id, email_enabled=False))
        db.commit()
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"], fallback)

        with patch(SEND_EMAIL) as mock_send:
            resp = client.post(
                f"/api/passes/{_claimable_pass_id(db, show)}/claim",
                json={},
                headers=_h(people["Ben"]),
            )

        assert resp.status_code == 200, resp.text
        assert _emails_to(mock_send, people["Ann"]) == []

    @pytest.mark.parametrize(
        ("fallback", "subject"),
        [
            ("attend_alone", "Your guest pass is no longer available"),
            ("release", "Your staff pass has been released"),
        ],
    )
    def test_bumped_email_still_sends_by_default(
        self, client, db, venue, people, fallback, subject
    ):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"], fallback)

        with patch(SEND_EMAIL) as mock_send:
            resp = client.post(
                f"/api/passes/{_claimable_pass_id(db, show)}/claim",
                json={},
                headers=_h(people["Ben"]),
            )

        assert resp.status_code == 200, resp.text
        assert subject in _emails_to(mock_send, people["Ann"])[0]["subject"]

    def test_guest_list_leaves_out_a_waiting_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        _claim(client, db, show, people["Ben"])
        db.refresh(show)

        text = ShowService._build_guest_list_text(show)

        assert "1 pass for Ann" in text
        assert "Ann+1" not in text and "and a guest" not in text


class TestPriority:
    def test_staff_who_join_later_go_first(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        ben = _claim(client, db, show, people["Ben"])
        assert _join(client, show, people["Cat"]).status_code == 201

        with patch(SEND_EMAIL):
            _release(client, people["Ben"], ben)

        assert _primary(db, show, people["Cat"]) is not None
        assert _waiting_names(db, show) == ["Ann+1"]

    def test_earlier_claims_guest_gets_the_pass_first(self, client, db, venue, people):
        show = _make_show(db, venue, 4)
        _claim_with_guest(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])
        cat = _claim(client, db, show, people["Cat"])
        _claim(client, db, show, people["Dan"])
        assert _waiting_names(db, show) == ["Ann+1", "Ben+1"]

        with patch(SEND_EMAIL) as mock_send:
            _release(client, people["Cat"], cat)

        ann = _primary(db, show, people["Ann"])
        assert ann.has_guest and not ann.guest_waiting
        assert _waiting_names(db, show) == ["Ben+1"]
        assert "has a pass" in _emails_to(mock_send, people["Ann"])[0]["subject"]

    def test_bumped_again_keeps_their_place(self, client, db, venue, people):
        show = _make_show(db, venue, 4)
        _claim_with_guest(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])
        cat = _claim(client, db, show, people["Cat"])
        _claim(client, db, show, people["Dan"])
        with patch(SEND_EMAIL):
            _release(client, people["Cat"], cat)
        assert _waiting_names(db, show) == ["Ben+1"]

        _claim(client, db, show, people["Eve"])

        assert _waiting_names(db, show) == ["Ann+1", "Ben+1"]

    def test_single_pass_goes_to_guest_over_pair_alternate(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        ben = _claim(client, db, show, people["Ben"])
        _join(client, show, people["Cat"], has_guest=True, guest_fallback="release")

        with patch(SEND_EMAIL):
            _release(client, people["Ben"], ben)

        assert _primary(db, show, people["Ann"]).has_guest
        assert _primary(db, show, people["Cat"]) is None

    def test_two_free_passes_go_to_the_pair_first(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        _claim(client, db, show, people["Ben"])
        _join(client, show, people["Cat"], has_guest=True, guest_fallback="release")

        with patch(SEND_EMAIL):
            PassService.adjust_passes_for_show(db, show, 4)

        assert _primary(db, show, people["Cat"]).has_guest
        assert _waiting_names(db, show) == ["Ann+1"]

    def test_guest_added_later_ranks_behind_those_waiting(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])
        assert _waiting_names(db, show) == ["Ben+1"]

        resp = client.post(
            f"/api/passes/{ann.id}/guest",
            json={"guest_name": "Ann+1", "guest_fallback": "wait"},
            headers=_h(people["Ann"]),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["guest_waiting"] is True
        assert resp.json()["guest_position"] == 2
        assert _waiting_names(db, show) == ["Ben+1", "Ann+1"]


class TestClaiming:
    @pytest.mark.parametrize("fallback", ["attend_alone", "release"])
    def test_no_spare_pass_rejects_options_that_cant_wait(
        self, client, db, venue, people, fallback
    ):
        show = _make_show(db, venue, 1)
        resp = client.post(
            f"/api/passes/{_first_available(db, show).id}/claim",
            json={"has_guest": True, "guest_fallback": fallback},
            headers=_h(people["Ann"]),
        )
        assert resp.status_code == 400
        assert "no pass free for your guest" in resp.json()["detail"]
        assert _primary(db, show, people["Ann"]) is None

    @pytest.mark.parametrize("fallback", ["wait", "wait_then_release"])
    def test_no_spare_pass_lets_the_guest_start_waiting(
        self, client, db, venue, people, fallback
    ):
        show = _make_show(db, venue, 1)
        ann = _claim_with_guest(client, db, show, people["Ann"], fallback)
        assert ann.guest_waiting and not ann.has_guest
        assert ann.guest_fallback == fallback
        assert ann.guest_position == 1

    def test_failed_claim_leaves_the_existing_guest_alone(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        hold = _guest_hold(db, ann)

        with patch(SEND_EMAIL) as mock_send:
            resp = client.post(
                f"/api/passes/{hold.id}/claim",
                json={"has_guest": True, "guest_fallback": "attend_alone"},
                headers=_h(people["Ben"]),
            )

        assert resp.status_code == 400
        db.refresh(ann)
        assert ann.has_guest
        mock_send.assert_not_called()

    def test_claiming_a_hold_with_a_waiting_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        ben = _claim_with_guest(client, db, show, people["Ben"])

        assert ben.guest_waiting
        assert _waiting_names(db, show) == ["Ann+1", "Ben+1"]

    def test_spare_pass_seats_the_guest_under_a_wait_option(
        self, client, db, venue, people
    ):
        show = _make_show(db, venue, 2)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        assert ann.has_guest and not ann.guest_waiting
        assert _guest_hold(db, ann) is not None

    def test_guest_name_is_required_when_joining_the_list(self, client, db, venue, people):
        venue.staff_guest_requires_name = True
        db.commit()
        show = _make_show(db, venue, 1)
        resp = client.post(
            f"/api/passes/{_first_available(db, show).id}/claim",
            json={"has_guest": True, "guest_fallback": "wait"},
            headers=_h(people["Ann"]),
        )
        assert resp.status_code == 400
        assert "requires a name" in resp.json()["detail"]

    def test_guest_name_is_required_when_entering_the_lottery(
        self, client, db, venue, people
    ):
        venue.staff_guest_requires_name = True
        db.commit()
        show = _lottery_show(db, venue, 1)
        resp = client.post(
            f"/api/shows/{show.id}/lottery/enter/staff",
            json={"has_guest": True, "guest_fallback": "wait"},
            headers=_h(people["Ann"]),
        )
        assert resp.status_code == 400
        assert "requires a name" in resp.json()["detail"]


class TestHostActions:
    def test_release_cancels_a_waiting_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        ann = _claim_with_guest(client, db, show, people["Ann"])

        with patch(SEND_EMAIL):
            _release(client, people["Ann"], ann)

        db.refresh(ann)
        assert ann.status == "available"
        assert not ann.guest_waiting and ann.guest_name is None
        assert ann.guest_priority_at is None
        assert _waiting_names(db, show) == []

    def test_releasing_host_doesnt_seat_their_own_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])
        assert _waiting_names(db, show) == ["Ann+1", "Ben+1"]

        with patch(SEND_EMAIL):
            _release(client, people["Ann"], ann)

        ben = _primary(db, show, people["Ben"])
        assert ben.has_guest and not ben.guest_waiting

    def test_removing_a_seated_guest_frees_the_pass(self, client, db, venue, people):
        show = _make_show(db, venue, 4)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])
        _claim(client, db, show, people["Cat"])
        assert _waiting_names(db, show) == ["Ben+1"]

        with patch(SEND_EMAIL) as mock_send:
            resp = client.delete(f"/api/passes/{ann.id}/guest", headers=_h(people["Ann"]))

        assert resp.status_code == 200, resp.text
        db.refresh(ann)
        assert ann.status == "claimed" and not ann.has_guest and ann.guest_name is None
        assert _primary(db, show, people["Ben"]).has_guest
        assert _emails_to(mock_send, people["Ann"]) == []

    def test_removing_a_waiting_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        ann = _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")

        resp = client.delete(f"/api/passes/{ann.id}/guest", headers=_h(people["Ann"]))

        assert resp.status_code == 200, resp.text
        db.refresh(ann)
        assert ann.status == "claimed" and not ann.guest_waiting
        assert ann.guest_fallback == "attend_alone"
        assert _waiting_names(db, show) == []

    def test_promotions_removal_emails_the_host(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        ann = _claim_with_guest(client, db, show, people["Ann"])

        with patch(SEND_EMAIL) as mock_send:
            resp = client.delete(f"/api/passes/{ann.id}/guest", headers=_h(promo))

        assert resp.status_code == 200, resp.text
        email = _emails_to(mock_send, people["Ann"])[0]
        assert "has been removed" in email["subject"]
        assert "Ann+1" in email["body_text"]
        assert promo.name in email["body_text"]

    def test_staff_cant_change_someone_elses_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        url = f"/api/passes/{ann.id}/guest"
        headers = _h(people["Ben"])

        statuses = [
            client.delete(url, headers=headers).status_code,
            client.patch(url, json={"guest_name": "X"}, headers=headers).status_code,
            client.post(url, json={"guest_fallback": "wait"}, headers=headers).status_code,
        ]

        assert statuses == [403, 403, 403]

    def test_name_fix_keeps_their_place(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])

        resp = client.patch(
            f"/api/passes/{ann.id}/guest",
            json={"guest_name": "  Fixed Name "},
            headers=_h(people["Ann"]),
        )

        assert resp.status_code == 200, resp.text
        assert _waiting_names(db, show) == ["Fixed Name", "Ben+1"]

    def test_remove_then_add_goes_to_the_back(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])
        headers = _h(people["Ann"])

        client.delete(f"/api/passes/{ann.id}/guest", headers=headers)
        client.post(
            f"/api/passes/{ann.id}/guest",
            json={"guest_name": "Ann+1", "guest_fallback": "wait"},
            headers=headers,
        )

        assert _waiting_names(db, show) == ["Ben+1", "Ann+1"]

    def test_added_guest_gets_a_free_pass(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim(client, db, show, people["Ann"])

        resp = client.post(
            f"/api/passes/{ann.id}/guest",
            json={"guest_name": "Ann+1"},
            headers=_h(people["Ann"]),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["has_guest"] is True
        assert _guest_hold(db, ann) is not None

    def test_adding_with_no_free_pass_needs_a_wait_option(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        ann = _claim(client, db, show, people["Ann"])

        resp = client.post(
            f"/api/passes/{ann.id}/guest",
            json={"guest_fallback": "attend_alone"},
            headers=_h(people["Ann"]),
        )

        assert resp.status_code == 400
        assert "no pass free for your guest" in resp.json()["detail"]

    def test_cant_add_a_second_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        resp = client.post(
            f"/api/passes/{ann.id}/guest",
            json={"guest_fallback": "wait"},
            headers=_h(people["Ann"]),
        )
        assert resp.status_code == 400

    def test_guests_cant_change_after_close(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        show.status = "closed"
        db.commit()
        url = f"/api/passes/{ann.id}/guest"
        headers = _h(people["Ann"])

        statuses = [
            client.delete(url, headers=headers).status_code,
            client.patch(url, json={"guest_name": "X"}, headers=headers).status_code,
        ]

        assert statuses == [400, 400]
        db.refresh(ann)
        assert ann.guest_waiting

    def test_guest_changes_are_audited(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim(client, db, show, people["Ann"])
        headers = _h(people["Ann"])
        url = f"/api/passes/{ann.id}/guest"

        client.post(
            url, json={"guest_name": "A", "guest_fallback": "wait"}, headers=headers
        )
        client.patch(url, json={"guest_name": "B"}, headers=headers)
        client.delete(url, headers=headers)

        events = {e.event_type for e in db.query(AuditLog).all()}
        assert {"guest_added", "guest_name_changed", "guest_removed"} <= events

    def test_moves_and_seats_are_audited(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        ben = _claim(client, db, show, people["Ben"])
        with patch(SEND_EMAIL):
            _release(client, people["Ben"], ben)

        events = [e.event_type for e in db.query(AuditLog).all()]
        assert "guest_moved_to_alternates" in events
        assert "guest_given_pass" in events


class TestOtherWaysIn:
    def test_lottery_winners_guest_waits(self, client, db, venue, people):
        show = _lottery_show(db, venue, 1)
        entry = _enter(
            db,
            show,
            people["Ann"],
            5,
            has_guest=True,
            guest_name="Ann+1",
            guest_fallback="wait",
        )

        with patch(SEND_EMAIL) as mock_send:
            _run_ordered(db, show, [entry])

        ann = _primary(db, show, people["Ann"])
        assert ann.guest_waiting and ann.guest_name == "Ann+1"
        assert not ann.has_guest
        body = _emails_to(mock_send, people["Ann"])[0]["body_text"]
        assert "guest #1" in body

    def test_lottery_winners_attend_alone_guest_is_dropped(self, client, db, venue, people):
        show = _lottery_show(db, venue, 1)
        entry = _enter(db, show, people["Ann"], 5, has_guest=True, guest_name="Ann+1")

        with patch(SEND_EMAIL):
            _run_ordered(db, show, [entry])

        ann = _primary(db, show, people["Ann"])
        assert not ann.guest_waiting and ann.guest_name is None

    def test_promoted_alternates_guest_waits(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        ann = _claim(client, db, show, people["Ann"])
        _join(
            client,
            show,
            people["Ben"],
            has_guest=True,
            guest_name="Ben+1",
            guest_fallback="wait",
        )

        with patch(SEND_EMAIL) as mock_send:
            _release(client, people["Ann"], ann)

        ben = _primary(db, show, people["Ben"])
        assert ben.guest_waiting and ben.guest_name == "Ben+1"
        body = _emails_to(mock_send, people["Ben"])[0]["body_text"]
        assert "guest #1" in body
        assert "has been dropped" not in body

    def test_promoted_alternates_attend_alone_guest_is_dropped(
        self, client, db, venue, people
    ):
        show = _make_show(db, venue, 1)
        ann = _claim(client, db, show, people["Ann"])
        _join(client, show, people["Ben"], has_guest=True, guest_name="Ben+1")

        with patch(SEND_EMAIL):
            _release(client, people["Ann"], ann)

        ben = _primary(db, show, people["Ben"])
        assert not ben.guest_waiting and not ben.has_guest

    def test_waiting_guests_come_before_a_promoted_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        ben = _claim(client, db, show, people["Ben"])
        _join(
            client,
            show,
            people["Cat"],
            has_guest=True,
            guest_name="Cat+1",
            guest_fallback="wait",
        )

        with patch(SEND_EMAIL):
            PassService.adjust_passes_for_show(db, show, 3)
            _release(client, people["Ben"], ben)

        assert _primary(db, show, people["Ann"]).has_guest
        assert _waiting_names(db, show) == ["Cat+1"]


class TestCapacityAndLifecycle:
    def test_removed_hold_goes_back_to_waiting(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim_with_guest(client, db, show, people["Ann"])

        with patch(SEND_EMAIL) as mock_send:
            PassService.adjust_passes_for_show(db, show, 1)

        db.refresh(ann)
        assert ann.guest_waiting and ann.guest_name == "Ann+1"
        body = _emails_to(mock_send, people["Ann"])[0]["body_text"]
        assert "has been reduced" in body

    def test_cut_host_takes_the_request_along(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"])

        with patch(SEND_EMAIL):
            PassService.adjust_passes_for_show(db, show, 0)

        entry = AlternateService.get_waiting_entry(db, show.id, people["Ann"].id)
        assert entry.has_guest and entry.guest_name == "Ann+1"
        assert entry.guest_fallback == "wait"
        assert _waiting_names(db, show) == []

    def test_more_passes_go_to_staff_then_guests(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        _claim(client, db, show, people["Ben"])
        _join(client, show, people["Cat"])

        with patch(SEND_EMAIL):
            PassService.adjust_passes_for_show(db, show, 3)
        assert _primary(db, show, people["Cat"]) is not None
        assert _waiting_names(db, show) == ["Ann+1"]

        with patch(SEND_EMAIL):
            PassService.adjust_passes_for_show(db, show, 4)
        assert _primary(db, show, people["Ann"]).has_guest

    def test_host_on_leave_guest_is_skipped_but_keeps_place(
        self, client, db, venue, people
    ):
        show = _make_show(db, venue, 3)
        _claim_with_guest(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])
        assert _primary(db, show, people["Ben"]).guest_waiting
        _claim(client, db, show, people["Cat"])
        assert _waiting_names(db, show) == ["Ann+1", "Ben+1"]
        people["Ann"].loa_start = date.today()
        people["Ann"].loa_end = date.today() + timedelta(days=60)
        db.commit()

        with patch(SEND_EMAIL):
            PassService.adjust_passes_for_show(db, show, 4)

        assert _primary(db, show, people["Ben"]).has_guest
        assert _waiting_names(db, show) == ["Ann+1"]

    def test_reopen_can_seat_a_waiting_guest(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"])
        with patch(SEND_EMAIL):
            assert client.post(f"/api/shows/{show.id}/close", headers=_h(promo)).is_success
            PassService.adjust_passes_for_show(db, show, 2)
            assert _primary(db, show, people["Ann"]).guest_waiting

            resp = client.post(f"/api/shows/{show.id}/reopen", headers=_h(promo))

        assert resp.status_code == 200, resp.text
        ann = _primary(db, show, people["Ann"])
        assert ann.has_guest and not ann.guest_waiting

    def test_deleted_show_email_mentions_the_waiting_guest(
        self, client, db, venue, people, promo
    ):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"])

        with patch(SEND_EMAIL) as mock_send:
            resp = client.delete(f"/api/shows/{show.id}", headers=_h(promo))

        assert resp.status_code == 204, resp.text
        body = _emails_to(mock_send, people["Ann"])[0]["body_text"]
        assert "alternate list for Ann+1 is cancelled" in body

    def test_unpublished_show_holds_guests_in_place(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"])
        show.status = "draft"
        db.commit()

        with patch(SEND_EMAIL):
            PassService.adjust_passes_for_show(db, show, 2)
            assert _primary(db, show, people["Ann"]).guest_waiting

            show.status = "published"
            db.commit()
            result = AlternateService.fill_open_passes(db, show, trigger="show_published")
            db.commit()

        assert _primary(db, show, people["Ann"]).has_guest
        assert [h.staff_id for h in result.guests_seated] == [people["Ann"].id]


class TestQueueResponse:
    def test_lists_waiting_guests_with_hosts(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        ann = _claim_with_guest(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])

        data = _queue(client, show, people["Ann"])

        assert data["entries"] == []
        assert data["waiting_guests"] == [
            {
                "pass_id": ann.id,
                "position": 1,
                "guest_name": "Ann+1",
                "host_staff_id": people["Ann"].id,
                "host_name": "Ann",
                "is_mine": True,
            },
            {
                "pass_id": _primary(db, show, people["Ben"]).id,
                "position": 2,
                "guest_name": "Ben+1",
                "host_staff_id": people["Ben"].id,
                "host_name": "Ben",
                "is_mine": False,
            },
        ]

    def test_after_close_only_promotions_see_them(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"])
        show.status = "closed"
        db.commit()

        assert _queue(client, show, people["Ben"])["waiting_guests"] == []
        assert len(_queue(client, show, promo)["waiting_guests"]) == 1

    def test_release_warning_names_the_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        _claim(client, db, show, people["Ben"])

        data = _queue(client, show, people["Ben"])

        assert data["next_candidate_name"] == "Ann+1 (Ann's guest)"
        assert data["next_candidate_staff_id"] is None

    def test_release_warning_skips_your_own_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"])

        assert _queue(client, show, people["Ann"])["next_candidate_name"] is None

    def test_staff_alternate_named_ahead_of_a_guest(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        _claim(client, db, show, people["Ben"])
        _join(client, show, people["Cat"])

        assert _queue(client, show, people["Ben"])["next_candidate_name"] == "Cat"

    def test_my_passes_shows_the_position(self, client, db, venue, people):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"])
        _claim_with_guest(client, db, show, people["Ben"])

        passes = client.get("/api/passes/staff/my-claims", headers=_h(people["Ben"]))

        assert passes.status_code == 200, passes.text
        assert passes.json()[0]["guest_waiting"] is True
        assert passes.json()[0]["guest_position"] == 2


def _close(client, show, promo):
    resp = client.post(f"/api/shows/{show.id}/close", headers=_h(promo))
    assert resp.status_code == 200, resp.text


def _reopen(client, show, promo):
    resp = client.post(f"/api/shows/{show.id}/reopen", headers=_h(promo))
    assert resp.status_code == 200, resp.text


def _two_hosts_waiting(client, db, show, people, fallback="wait_then_release"):
    """On a two-pass show, Ann then Ben claim, and neither guest has a pass."""
    _claim_with_guest(client, db, show, people["Ann"], fallback)
    _claim_with_guest(client, db, show, people["Ben"], fallback)
    assert _waiting_names(db, show) == ["Ann+1", "Ben+1"]


class TestReleaseAtClose:
    def test_wait_host_stays_on_the_list_alone(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait")

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        db.refresh(show)
        text = ShowService._build_guest_list_text(show)
        assert "1 pass for Ann" in text and "Ann+1" not in text
        (email,) = _emails_to(mock_send, people["Ann"])
        assert "didn't get a pass" in email["subject"]
        assert "You're on the guest list, but Ann+1" in email["body_text"]

    def test_latest_host_goes_first_and_can_save_the_other(
        self, client, db, venue, people, promo
    ):
        show = _make_show(db, venue, 2)
        _two_hosts_waiting(client, db, show, people)

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        ann = _primary(db, show, people["Ann"])
        assert ann.has_guest and not ann.guest_waiting
        assert _primary(db, show, people["Ben"]) is None
        db.refresh(show)
        text = ShowService._build_guest_list_text(show)
        assert "Ann and a guest" in text and "Ben" not in text

        (ann_email,) = _emails_to(mock_send, people["Ann"])
        assert "confirmed" in ann_email["subject"]
        (ben_email,) = _emails_to(mock_send, people["Ben"])
        assert "has been released" in ben_email["subject"]
        assert "neither of you" in ben_email["body_text"]

    def test_staff_alternate_gets_the_pass_ahead_of_the_guest(
        self, client, db, venue, people, promo
    ):
        show = _make_show(db, venue, 2)
        _two_hosts_waiting(client, db, show, people)
        assert _join(client, show, people["Cat"]).status_code == 201

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        assert _primary(db, show, people["Cat"]) is not None
        assert _primary(db, show, people["Ann"]) is None
        assert _primary(db, show, people["Ben"]) is None
        (cat_email,) = _emails_to(mock_send, people["Cat"])
        assert "You got a staff pass" in cat_email["subject"]
        assert "has been released" in _emails_to(mock_send, people["Ann"])[0]["subject"]

    def test_released_even_if_nobody_can_use_the_pass(
        self, client, db, venue, people, promo
    ):
        show = _make_show(db, venue, 1)
        ann = _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")

        with patch(SEND_EMAIL):
            _close(client, show, promo)

        db.refresh(ann)
        assert ann.status == "available"
        assert _primary(db, show, people["Ann"]) is None

    def test_seated_guest_means_no_release(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 2)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        assert _primary(db, show, people["Ann"]).has_guest
        assert "confirmed" in _emails_to(mock_send, people["Ann"])[0]["subject"]

    def test_removed_guest_means_no_release(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        ann = _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")
        client.delete(f"/api/passes/{ann.id}/guest", headers=_h(people["Ann"]))

        with patch(SEND_EMAIL):
            _close(client, show, promo)

        assert _primary(db, show, people["Ann"]) is not None

    def test_option_4_alternate_needs_two_passes_at_close(
        self, client, db, venue, people, promo
    ):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")
        _join(
            client,
            show,
            people["Cat"],
            has_guest=True,
            guest_name="Cat+1",
            guest_fallback="wait_then_release",
        )

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        assert _primary(db, show, people["Cat"]) is None
        (cat_email,) = _emails_to(mock_send, people["Cat"])
        assert "No staff pass" in cat_email["subject"]

    def test_option_4_alternate_gets_a_pair_at_close(
        self, client, db, venue, people, promo
    ):
        # A host on leave's guest is skipped, leaving a pass free until the close.
        show = _make_show(db, venue, 2)
        ann = _claim(client, db, show, people["Ann"])
        PassService._start_guest_waiting(
            ann, datetime.now(timezone.utc), "Ann+1", "wait_then_release"
        )
        db.commit()
        _add_waiting(
            db,
            show,
            people["Cat"],
            has_guest=True,
            guest_name="Cat+1",
            guest_fallback="wait_then_release",
        )

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        assert _primary(db, show, people["Cat"]).has_guest
        (cat_email,) = _emails_to(mock_send, people["Cat"])
        assert "You got a staff pass" in cat_email["subject"]
        assert "both on the guest list" in cat_email["body_text"]

    def test_released_host_listed_for_promotions(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")

        with patch(SEND_EMAIL):
            _close(client, show, promo)

        entries = _queue(client, show, promo)["entries"]
        assert [e["staff_name"] for e in entries] == ["Ann"]
        assert entries[0]["source"] == "released_at_close"
        assert entries[0]["guest_name"] == "Ann+1"

    def test_release_is_audited(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")

        with patch(SEND_EMAIL):
            _close(client, show, promo)

        events = [e.event_type for e in db.query(AuditLog).all()]
        assert "pass_released_at_close" in events

    def test_reopen_gives_an_unused_pass_back(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")
        with patch(SEND_EMAIL):
            _close(client, show, promo)
        assert _primary(db, show, people["Ann"]) is None

        with patch(SEND_EMAIL) as mock_send:
            _reopen(client, show, promo)

        # The freed pass went unused, so Ann gets it back with her guest waiting.
        ann = _primary(db, show, people["Ann"])
        assert ann is not None and ann.guest_waiting
        assert "You got a staff pass" in _emails_to(mock_send, people["Ann"])[0]["subject"]

    def test_second_close_doesnt_say_released_again(self, client, db, venue, people, promo):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")
        _join(client, show, people["Cat"])
        with patch(SEND_EMAIL):
            _close(client, show, promo)
            assert _primary(db, show, people["Cat"]) is not None
            _reopen(client, show, promo)
        entry = AlternateService.get_waiting_entry(db, show.id, people["Ann"].id)
        assert entry is not None and entry.source == "joined"

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        assert "No staff pass" in _emails_to(mock_send, people["Ann"])[0]["subject"]

    def test_auto_close_releases_too(self, db, venue, people, client):
        from app.scheduler import _close_automatically

        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")

        with patch(SEND_EMAIL) as mock_send:
            _close_automatically(db, show.id)

        assert _primary(db, show, people["Ann"]) is None
        (email,) = _emails_to(mock_send, people["Ann"])
        assert "has been released" in email["subject"]


class TestOneEmailAtClose:
    def test_lottery_winner_and_guest(self, client, db, venue, people, promo):
        show = _lottery_show(db, venue, 2)
        _enter(db, show, people["Ann"], 5, has_guest=True, guest_name="Ann+1")

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        (email,) = _emails_to(mock_send, people["Ann"])
        assert "You won" in email["subject"]
        assert "selected in the lottery" in email["body_text"]
        assert "both on the guest list" in email["body_text"]
        assert "may go to another staff member" not in email["body_text"]

    def test_lottery_winner_alone_gets_the_result(self, client, db, venue, people, promo):
        show = _lottery_show(db, venue, 1)
        _enter(db, show, people["Ann"], 5)

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        (email,) = _emails_to(mock_send, people["Ann"])
        assert "Your staff pass has been reserved" in email["body_text"]

    def test_lottery_loser(self, client, db, venue, people, promo):
        show = _lottery_show(db, venue, 1)
        ann = _enter(db, show, people["Ann"], 10)
        ben = _enter(db, show, people["Ben"], 5)

        def fake_shuffle(entries):
            entries.sort(key=lambda e: [ann.id, ben.id].index(e.id))

        with (
            patch(SEND_EMAIL) as mock_send,
            patch("random.shuffle", side_effect=fake_shuffle),
        ):
            _close(client, show, promo)

        (email,) = _emails_to(mock_send, people["Ben"])
        assert "not selected" in email["body_text"]
        assert "no staff pass became available" in email["body_text"]
        assert "alternate #" not in email["body_text"]
        assert "Thank you for entering" not in email["body_text"]

    def test_lottery_winner_released_hears_only_once(
        self, client, db, venue, people, promo
    ):
        show = _lottery_show(db, venue, 1)
        _enter(
            db,
            show,
            people["Ann"],
            5,
            has_guest=True,
            guest_name="Ann+1",
            guest_fallback="wait_then_release",
        )

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        (email,) = _emails_to(mock_send, people["Ann"])
        assert "has been released" in email["subject"]
        assert "selected in the lottery" in email["body_text"]

    def test_promoted_alternate_with_a_waiting_guest(
        self, client, db, venue, people, promo
    ):
        show = _make_show(db, venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")
        _join(
            client,
            show,
            people["Cat"],
            has_guest=True,
            guest_name="Cat+1",
            guest_fallback="wait",
        )

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        (email,) = _emails_to(mock_send, people["Cat"])
        assert "You got a staff pass" in email["subject"]
        assert "You're on the guest list, but Cat+1" in email["body_text"]
        assert "guest #" not in email["body_text"]

    def test_guest_seated_during_close_gets_no_separate_email(
        self, client, db, venue, people, promo
    ):
        show = _make_show(db, venue, 2)
        _two_hosts_waiting(client, db, show, people)

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)

        assert len(_emails_to(mock_send, people["Ann"])) == 1
        assert "guest_given_pass" in [e.event_type for e in db.query(AuditLog).all()]


class TestHeldEmails:
    @pytest.fixture
    def held_venue(self, db, venue):
        venue.hold_close_notifications = True
        db.commit()
        return venue

    def _send(self, client, show, promo):
        return client.post(
            f"/api/shows/{show.id}/send-close-notifications", headers=_h(promo)
        )

    def test_only_waiting_guests_still_holds(self, client, db, held_venue, people, promo):
        show = _make_show(db, held_venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait")

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)
            assert _emails_to(mock_send, people["Ann"]) == []
            db.refresh(show)
            assert show.close_notifications_held

            resp = self._send(client, show, promo)

        assert resp.status_code == 200, resp.text
        (email,) = _emails_to(mock_send, people["Ann"])
        assert "didn't get a pass" in email["subject"]

    def test_released_host_waits_for_the_rep(self, client, db, held_venue, people, promo):
        show = _make_show(db, held_venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)
            assert _emails_to(mock_send, people["Ann"]) == []
            assert _queue(client, show, people["Ann"])["my_outcome_pending"] is True
            self._send(client, show, promo)

        (email,) = _emails_to(mock_send, people["Ann"])
        assert "has been released" in email["subject"]

    def test_promoted_alternate_hears_now_and_confirmed_later(
        self, client, db, held_venue, people, promo
    ):
        show = _make_show(db, held_venue, 2)
        ann = _claim(client, db, show, people["Ann"])
        PassService._start_guest_waiting(
            ann, datetime.now(timezone.utc), "Ann+1", "wait_then_release"
        )
        db.commit()
        _add_waiting(
            db,
            show,
            people["Cat"],
            has_guest=True,
            guest_name="Cat+1",
            guest_fallback="wait_then_release",
        )

        with patch(SEND_EMAIL) as mock_send:
            _close(client, show, promo)
            (now_email,) = _emails_to(mock_send, people["Cat"])
            assert "You got a staff pass" in now_email["subject"]
            assert "both on the guest list" not in now_email["body_text"]

            self._send(client, show, promo)

        later = _emails_to(mock_send, people["Cat"])[1]
        assert "confirmed" in later["subject"]

    def test_lottery_result_goes_now_and_outcome_later(
        self, client, db, held_venue, people, promo
    ):
        show = _lottery_show(db, held_venue, 1)
        ann = _enter(db, show, people["Ann"], 10)
        ben = _enter(db, show, people["Ben"], 5)

        def fake_shuffle(entries):
            entries.sort(key=lambda e: [ann.id, ben.id].index(e.id))

        with (
            patch(SEND_EMAIL) as mock_send,
            patch("random.shuffle", side_effect=fake_shuffle),
        ):
            _close(client, show, promo)
            (now_email,) = _emails_to(mock_send, people["Ben"])
            assert "not selected" in now_email["body_text"]
            assert "alternate #" not in now_email["body_text"]

            self._send(client, show, promo)

        assert "No staff pass" in _emails_to(mock_send, people["Ben"])[1]["subject"]

    def test_reopen_tells_a_released_host_who_never_heard(
        self, client, db, held_venue, people, promo
    ):
        show = _make_show(db, held_venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait_then_release")
        _join(client, show, people["Cat"])
        with patch(SEND_EMAIL):
            _close(client, show, promo)

        with patch(SEND_EMAIL) as mock_send:
            _reopen(client, show, promo)

        (email,) = _emails_to(mock_send, people["Ann"])
        assert "back on the alternate list" in email["subject"]
        assert "was released when the show closed" in email["body_text"]

    def test_send_counts_are_audited(self, client, db, held_venue, people, promo):
        show = _make_show(db, held_venue, 1)
        _claim_with_guest(client, db, show, people["Ann"], "wait")
        with patch(SEND_EMAIL):
            _close(client, show, promo)
            self._send(client, show, promo)

        entry = (
            db.query(AuditLog)
            .filter(AuditLog.event_type == "close_notifications_sent")
            .one()
        )
        assert entry.details["waiting_guest_hosts"] == 1
