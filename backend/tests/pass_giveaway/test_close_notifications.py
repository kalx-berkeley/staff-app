"""Tests for holding a closed show's emails until a promotions rep sends them."""

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.pass_model import Pass
from app.models.promoter import Promoter
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_pass_alternate import StaffPassAlternate
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.models.venue_owner import VenueOwner
from app.scheduler import _reschedule_pending_auto_close_jobs, auto_close_show

SEND_EMAIL = "app.common.services.notification_service.send_email"
_LA = ZoneInfo("America/Los_Angeles")


@pytest.fixture
def venue(db: Session) -> Venue:
    v = Venue(name="Hold Venue", address="1 Hold St", hold_close_notifications=True)
    db.add(v)
    db.commit()
    return v


def _staff(db: Session, name: str, department: str | None = None) -> Staff:
    staff = Staff(email=f"{name.lower()}@hold.test", name=name, phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    return staff


@pytest.fixture
def promo(db: Session) -> Staff:
    return _staff(db, "Pat", "Promotions")


@pytest.fixture
def host(db: Session) -> Staff:
    return _staff(db, "Hana")


@pytest.fixture
def alternate(db: Session) -> Staff:
    return _staff(db, "Alex")


@pytest.fixture
def show(db: Session, venue: Venue, host: Staff, alternate: Staff) -> Show:
    """A published show with a +1 host holding the one pass and one alternate waiting."""
    s = _show(db, venue)
    db.add(
        Pass(
            show_id=s.id,
            pass_type="staff",
            status="claimed",
            staff_id=host.id,
            has_guest=True,
        )
    )
    _wait(db, s, alternate)
    db.commit()
    return s


def _show(db: Session, venue: Venue, **kwargs) -> Show:
    s = Show(
        event_name="Hold Show",
        venue_id=venue.id,
        show_date=kwargs.pop("show_date", date.today() + timedelta(days=30)),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=1,
        status=kwargs.pop("status", "published"),
        published_at=datetime.now(timezone.utc) - timedelta(days=1),
        **kwargs,
    )
    db.add(s)
    db.commit()
    return s


def _wait(db: Session, show: Show, staff: Staff) -> None:
    db.add(
        StaffPassAlternate(
            show_id=show.id,
            staff_id=staff.id,
            status="waiting",
            priority_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def _h(staff: Staff) -> dict:
    return {"X-Forwarded-User": staff.email}


def _post(client, staff: Staff, show: Show, action: str):
    return client.post(f"/api/shows/{show.id}/{action}", headers=_h(staff))


def _subjects(mock_send, staff: Staff) -> list[str]:
    return [
        c.kwargs["subject"]
        for c in mock_send.call_args_list
        if c.kwargs.get("to_email") == staff.email
    ]


def _close(client, promo: Staff, show: Show):
    with patch(SEND_EMAIL) as mock_send:
        response = _post(client, promo, show, "close")
    assert response.status_code == 200
    return response.json(), mock_send


class TestClosing:
    def test_manual_close_holds_the_emails(self, client, promo, host, alternate, show):
        body, mock_send = _close(client, promo, show)

        assert mock_send.call_count == 0
        assert body["close_notifications_pending"] is True
        assert body["close_notifications_sent_at"] is None

    def test_setting_off_sends_at_close(
        self, client, db, venue, promo, host, alternate, show
    ):
        venue.hold_close_notifications = False
        db.commit()

        body, mock_send = _close(client, promo, show)

        assert _subjects(mock_send, host) == ["Your guest is confirmed: Hold Show"]
        assert _subjects(mock_send, alternate) == ["No staff pass available: Hold Show"]
        assert body["close_notifications_pending"] is False

    def test_promoter_setting_wins_over_venue(
        self, client, db, venue, promo, host, alternate, show
    ):
        promoter = Promoter(name="Open Promoter", hold_close_notifications=False)
        db.add(promoter)
        db.flush()
        show.promoter_id = promoter.id
        db.commit()

        _, mock_send = _close(client, promo, show)

        assert _subjects(mock_send, host)

    def test_venues_default_promoter_is_ignored(
        self, client, db, venue, promo, host, alternate, show
    ):
        promoter = Promoter(name="Default Promoter", hold_close_notifications=False)
        db.add(promoter)
        db.flush()
        venue.promoter_id = promoter.id
        db.commit()

        _, mock_send = _close(client, promo, show)

        assert not _subjects(mock_send, host)

    def test_nobody_to_notify_holds_nothing(self, client, db, venue, promo):
        show = _show(db, venue)

        body, _ = _close(client, promo, show)

        assert body["close_notifications_pending"] is False

    def test_setting_changed_after_close_keeps_the_button(
        self, client, db, venue, promo, host, alternate, show
    ):
        _close(client, promo, show)
        venue.hold_close_notifications = False
        db.commit()

        body = client.get(f"/api/shows/{show.id}", headers=_h(promo)).json()

        assert body["close_notifications_pending"] is True


REMINDER = "Reminder: you're on the guest list for Hold Show"


def _claim(db: Session, show: Show, staff: Staff, **kwargs) -> Pass:
    pass_item = Pass(
        show_id=show.id, pass_type="staff", status="claimed", staff_id=staff.id, **kwargs
    )
    db.add(pass_item)
    db.commit()
    return pass_item


class TestReminders:
    """Staff pass winners the close has nothing else to tell get a reminder."""

    def test_solo_winner_is_reminded(self, client, db, venue, promo, host):
        show = _show(db, venue, staff_instructions="Ask for Sam at the door.")
        _claim(db, show, host)

        _, mock_send = _close(client, promo, show)

        assert _subjects(mock_send, host) == [REMINDER]
        body = mock_send.call_args.kwargs["body_text"]
        assert '"Hold Show" at Hold Venue' in body
        assert "The show starts at 8:00pm." in body
        assert "Ask for Sam at the door." in body
        assert f"/pass-giveaway/staff/shows/{show.id}" in body

    def test_reminder_is_not_held(self, client, db, venue, promo, host, alternate, show):
        solo = _staff(db, "Sol")
        _claim(db, show, solo)

        body, mock_send = _close(client, promo, show)

        assert body["close_notifications_pending"] is True
        assert _subjects(mock_send, solo) == [REMINDER]
        assert _subjects(mock_send, host) == []
        assert _subjects(mock_send, alternate) == []

    def test_held_emails_dont_remind_again(
        self, client, db, venue, promo, host, alternate, show
    ):
        solo = _staff(db, "Sol")
        _claim(db, show, solo)
        _close(client, promo, show)

        with patch(SEND_EMAIL) as mock_send:
            _post(client, promo, show, "send-close-notifications")

        assert _subjects(mock_send, solo) == []
        assert _subjects(mock_send, host) == ["Your guest is confirmed: Hold Show"]

    def test_plus_one_host_gets_only_their_outcome(
        self, client, db, venue, promo, host, alternate, show
    ):
        venue.hold_close_notifications = False
        db.commit()

        _, mock_send = _close(client, promo, show)

        assert _subjects(mock_send, host) == ["Your guest is confirmed: Hold Show"]

    def test_host_with_waiting_guest_gets_only_their_outcome(
        self, client, db, venue, promo, host
    ):
        venue.hold_close_notifications = False
        show = _show(db, venue)
        _claim(
            db,
            show,
            host,
            guest_waiting=True,
            guest_name="Gus",
            guest_priority_at=datetime.now(timezone.utc),
        )

        _, mock_send = _close(client, promo, show)

        assert _subjects(mock_send, host) == ["Your guest didn't get a pass: Hold Show"]

    def test_held_host_with_waiting_guest_hears_nothing_at_close(
        self, client, db, venue, promo, host
    ):
        show = _show(db, venue)
        _claim(
            db,
            show,
            host,
            guest_waiting=True,
            guest_name="Gus",
            guest_priority_at=datetime.now(timezone.utc),
        )

        body, mock_send = _close(client, promo, show)

        assert body["close_notifications_pending"] is True
        assert _subjects(mock_send, host) == []

    def test_email_preference_off(self, client, db, venue, promo, host):
        from app.models.notification_preferences import NotificationPreferences

        db.add(NotificationPreferences(staff_id=host.id, email_enabled=False))
        show = _show(db, venue)
        _claim(db, show, host)

        _, mock_send = _close(client, promo, show)

        assert mock_send.call_count == 0

    def test_tabler_and_released_passes_arent_reminded(
        self, client, db, venue, promo, host, alternate
    ):
        show = _show(db, venue)
        db.add(
            Pass(show_id=show.id, pass_type="tabler", status="claimed", staff_id=host.id)
        )
        _claim(db, show, alternate).status = "available"
        db.commit()

        _, mock_send = _close(client, promo, show)

        assert mock_send.call_count == 0


class TestAutoClose:
    def _auto_close(self, db: Session, show: Show):
        with (
            patch("app.database.SessionLocal", return_value=db),
            patch.object(db, "close"),
            patch(SEND_EMAIL) as mock_send,
        ):
            asyncio.run(auto_close_show(show.id))
        return mock_send

    def _add_rep(self, db: Session, venue: Venue, rep: Staff) -> None:
        db.add(VenueOwner(venue_id=venue.id, staff_id=rep.id))
        db.commit()

    def test_reps_get_the_guest_list_and_a_note(
        self, db, venue, promo, host, alternate, show
    ):
        self._add_rep(db, venue, promo)

        mock_send = self._auto_close(db, show)

        assert _subjects(mock_send, host) == []
        assert _subjects(mock_send, alternate) == []
        rep_email = next(
            c.kwargs
            for c in mock_send.call_args_list
            if c.kwargs["to_email"] == promo.email
        )
        assert "Hana" in rep_email["body_text"]
        assert "No notifications have been sent" in rep_email["body_text"]
        assert "Notify Staff and Alternates" in rep_email["body_text"]
        assert f"/pass-giveaway/promotions/shows/{show.id}" in rep_email["body_text"]

    def test_no_note_with_nobody_to_notify(self, db, venue, promo):
        self._add_rep(db, venue, promo)
        show = _show(db, venue)

        mock_send = self._auto_close(db, show)

        body = mock_send.call_args.kwargs["body_text"]
        assert "No notifications have been sent" not in body
        assert "View this show:" in body

    def test_no_note_with_the_setting_off(self, db, venue, promo, host, alternate, show):
        self._add_rep(db, venue, promo)
        venue.hold_close_notifications = False
        db.commit()

        mock_send = self._auto_close(db, show)

        assert _subjects(mock_send, host)
        rep_email = next(
            c.kwargs
            for c in mock_send.call_args_list
            if c.kwargs["to_email"] == promo.email
        )
        assert "No notifications have been sent" not in rep_email["body_text"]


class TestButton:
    def test_sends_the_held_emails_once(self, client, db, promo, host, alternate, show):
        _close(client, promo, show)

        with patch(SEND_EMAIL) as mock_send:
            response = _post(client, promo, show, "send-close-notifications")

        assert response.status_code == 200
        body = response.json()
        assert body["close_notifications_pending"] is False
        assert body["close_notifications_sent_at"] is not None
        assert body["close_notifications_sent_by"] == "Pat"
        assert _subjects(mock_send, host) == ["Your guest is confirmed: Hold Show"]
        assert _subjects(mock_send, alternate) == ["No staff pass available: Hold Show"]
        assert _subjects(mock_send, promo) == []
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.event_type == "close_notifications_sent")
            .one()
        )
        assert audit.actor_email == promo.email

        with patch(SEND_EMAIL) as second_send:
            again = _post(client, promo, show, "send-close-notifications")
        assert again.status_code == 400
        assert second_send.call_count == 0

    def test_requires_promotions_staff(self, client, promo, host, alternate, show):
        _close(client, promo, show)

        response = _post(client, alternate, show, "send-close-notifications")

        assert response.status_code == 403

    def test_rejected_on_an_open_show(self, client, promo, show):
        assert _post(client, promo, show, "send-close-notifications").status_code == 400

    def test_gone_after_the_show_date(self, client, db, promo, host, alternate, show):
        _close(client, promo, show)
        show.show_date = date.today() - timedelta(days=2)
        db.commit()

        body = client.get(f"/api/shows/{show.id}", headers=_h(promo)).json()
        assert body["close_notifications_pending"] is False
        with patch(SEND_EMAIL) as mock_send:
            response = _post(client, promo, show, "send-close-notifications")
        assert response.status_code == 400
        assert mock_send.call_count == 0

    def test_show_date_today_still_works(self, client, db, promo, host, alternate, show):
        _close(client, promo, show)
        show.show_date = datetime.now(_LA).date()
        db.commit()

        with patch(SEND_EMAIL):
            response = _post(client, promo, show, "send-close-notifications")

        assert response.status_code == 200


class TestReopen:
    def test_held_alternate_isnt_told_they_are_back(
        self, client, promo, host, alternate, show
    ):
        _close(client, promo, show)

        with patch(SEND_EMAIL) as mock_send:
            body = _post(client, promo, show, "reopen").json()

        assert mock_send.call_count == 0
        assert body["close_notifications_pending"] is False

    def test_told_alternate_hears_they_are_back(self, client, promo, host, alternate, show):
        _close(client, promo, show)
        with patch(SEND_EMAIL):
            _post(client, promo, show, "send-close-notifications")

        with patch(SEND_EMAIL) as mock_send:
            body = _post(client, promo, show, "reopen").json()

        assert _subjects(mock_send, alternate) == [
            "You're back on the alternate list: Hold Show"
        ]
        assert body["close_notifications_sent_at"] is None

    def test_whole_workflow(self, client, db, promo, host, alternate, show):
        """Close, reopen, add a pass (promoting the alternate), re-close and send."""
        third = _staff(db, "Tess")
        _wait(db, show, third)
        _close(client, promo, show)
        with patch(SEND_EMAIL):
            _post(client, promo, show, "reopen")

        with patch(SEND_EMAIL) as promoted:
            response = client.put(
                f"/api/shows/{show.id}",
                headers=_h(promo),
                json={"staff_pass_adjustment": 1},
            )
        assert response.status_code == 200
        assert any("alex" in c.kwargs["to_email"] for c in promoted.call_args_list)

        body, close_send = _close(client, promo, show)
        # Only the promoted alternate, who now holds a pass alone, hears at close.
        assert _subjects(close_send, alternate) == [
            "Reminder: you're on the guest list for Hold Show"
        ]
        assert close_send.call_count == 1
        assert body["close_notifications_pending"] is True

        with patch(SEND_EMAIL) as mock_send:
            _post(client, promo, show, "send-close-notifications")
        assert _subjects(mock_send, third) == ["No staff pass available: Hold Show"]
        assert _subjects(mock_send, alternate) == []
        assert _subjects(mock_send, host) == ["Your guest is confirmed: Hold Show"]


class TestDelete:
    def test_held_alternate_hears_about_the_cancellation(
        self, client, db, promo, host, alternate, show
    ):
        _close(client, promo, show)

        with patch(SEND_EMAIL) as mock_send:
            response = client.delete(f"/api/shows/{show.id}", headers=_h(promo))

        assert response.status_code == 204
        assert _subjects(mock_send, alternate) == ["Show cancelled: Hold Show"]
        db.refresh(show)
        assert show.close_notifications_held is False

    def test_told_alternate_doesnt_hear_again(self, client, promo, host, alternate, show):
        _close(client, promo, show)
        with patch(SEND_EMAIL):
            _post(client, promo, show, "send-close-notifications")

        with patch(SEND_EMAIL) as mock_send:
            client.delete(f"/api/shows/{show.id}", headers=_h(promo))

        assert _subjects(mock_send, alternate) == []


class TestWhatStaffSee:
    def _queue(self, client, staff: Staff, show: Show) -> dict:
        return client.get(f"/api/shows/{show.id}/alternates", headers=_h(staff)).json()

    def _mine(self, client, staff: Staff) -> list[dict]:
        return client.get("/api/shows/alternates/my-entries", headers=_h(staff)).json()

    def test_alternate_keeps_their_entry_while_held(
        self, client, promo, host, alternate, show
    ):
        _close(client, promo, show)

        assert self._queue(client, alternate, show)["my_outcome_pending"] is True
        entries = self._mine(client, alternate)
        assert [e["show_id"] for e in entries] == [show.id]
        assert entries[0]["outcome_pending"] is True
        assert entries[0]["position"] == 1

    def test_others_see_no_pending_outcome(self, client, promo, host, alternate, show):
        _close(client, promo, show)

        assert self._queue(client, host, show)["my_outcome_pending"] is False
        assert self._mine(client, host) == []

    def test_entry_goes_away_once_sent(self, client, promo, host, alternate, show):
        _close(client, promo, show)
        with patch(SEND_EMAIL):
            _post(client, promo, show, "send-close-notifications")

        assert self._queue(client, alternate, show)["my_outcome_pending"] is False
        assert self._mine(client, alternate) == []

    def test_waiting_entries_arent_marked_pending(self, client, alternate, show):
        entries = self._mine(client, alternate)

        assert [e["outcome_pending"] for e in entries] == [False]


class TestSetting:
    def test_venue_setting_round_trips(self, client, db, promo):
        created = client.post(
            "/api/venues",
            headers=_h(promo),
            json={"name": "V", "address": "A", "hold_close_notifications": True},
        )
        assert created.status_code in (200, 201), created.text
        assert created.json()["hold_close_notifications"] is True

        updated = client.put(
            f"/api/venues/{created.json()['id']}",
            headers=_h(promo),
            json={"hold_close_notifications": False},
        )
        assert updated.json()["hold_close_notifications"] is False

    def test_promoter_setting_round_trips(self, client, db, promo):
        created = client.post(
            "/api/promoters",
            headers=_h(promo),
            json={"name": "P", "hold_close_notifications": True},
        )
        assert created.status_code in (200, 201), created.text
        assert created.json()["hold_close_notifications"] is True

        updated = client.put(
            f"/api/promoters/{created.json()['id']}",
            headers=_h(promo),
            json={"hold_close_notifications": False},
        )
        assert updated.json()["hold_close_notifications"] is False

    def test_defaults_to_off(self, client, promo):
        created = client.post(
            "/api/venues", headers=_h(promo), json={"name": "V", "address": "A"}
        )
        assert created.json()["hold_close_notifications"] is False


class TestRestart:
    """A restart must not auto-close a show a rep reopened after its close time."""

    def _restart(self, db: Session) -> None:
        with (
            patch.dict("os.environ", {"TESTING": "0"}),
            patch("app.database.SessionLocal", return_value=db),
            patch.object(db, "close"),
            patch(SEND_EMAIL),
        ):
            _reschedule_pending_auto_close_jobs()

    def _past_close_show(self, db: Session, venue: Venue, **kwargs) -> Show:
        close_at = datetime.now(_LA) - timedelta(hours=2)
        return _show(
            db,
            venue,
            auto_close=True,
            planned_close_date=close_at.date(),
            planned_close_time=close_at.time(),
            **kwargs,
        )

    def test_reopened_after_close_time_stays_open(self, db, venue):
        show = self._past_close_show(db, venue, reopened_at=datetime.now(timezone.utc))

        self._restart(db)

        db.refresh(show)
        assert show.status == "published"

    def test_reopened_before_close_time_still_closes(self, db, venue):
        show = self._past_close_show(
            db, venue, reopened_at=datetime.now(timezone.utc) - timedelta(days=1)
        )

        self._restart(db)

        db.refresh(show)
        assert show.status == "closed"

    def test_never_reopened_still_closes(self, db, venue):
        show = self._past_close_show(db, venue)

        self._restart(db)

        db.refresh(show)
        assert show.status == "closed"

    def test_reopen_records_the_time(self, client, promo, host, alternate, show, db):
        _close(client, promo, show)
        with patch(SEND_EMAIL):
            _post(client, promo, show, "reopen")

        db.refresh(show)
        assert show.reopened_at is not None
