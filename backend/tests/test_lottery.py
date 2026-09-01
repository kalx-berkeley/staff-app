"""Tests for the lottery system — all staff pass and DJ pre-assignment scenarios."""

import pytest
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.lottery_entry import LotteryEntry
from app.models.notification_preferences import NotificationPreferences
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.services.lottery_service import LotteryService

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def venue(db: Session):
    v = Venue(name="Lottery Test Venue", address="100 Radio St")
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@pytest.fixture
def promotions_staff(db: Session):
    staff = Staff(
        email="promotions@lottery.test", name="Promotions Staff", phone="555-0001"
    )
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


def _make_staff(db: Session, name: str, email: str) -> Staff:
    staff = Staff(email=email, name=name, phone="555-0000")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def joe(db: Session):
    return _make_staff(db, "Joe", "joe@lottery.test")


@pytest.fixture
def alice(db: Session):
    return _make_staff(db, "Alice", "alice@lottery.test")


@pytest.fixture
def bob(db: Session):
    return _make_staff(db, "Bob", "bob@lottery.test")


def _make_lottery_show(
    db: Session,
    venue: Venue,
    num_staff_passes: int,
    num_pair_passes: int = 0,
) -> Show:
    """Published show with lottery open, pre-populated with passes."""
    published_at = datetime.now(timezone.utc) - timedelta(hours=1)
    show = Show(
        event_name="Lottery Test Show",
        venue_id=venue.id,
        show_date=date(2025, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=num_pair_passes,
        status="published",
        lottery_enabled=True,
        lottery_window_hours=24,
        published_at=published_at,
    )
    db.add(show)
    db.commit()
    db.refresh(show)
    for _ in range(num_staff_passes):
        db.add(Pass(show_id=show.id, pass_type="staff", status="available"))
    for _ in range(num_pair_passes):
        db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    db.commit()
    return show


def _make_staff_entry(
    db: Session,
    show: Show,
    staff: Staff,
    has_guest: bool = False,
    guest_name: str | None = None,
    only_attend_with_guest: bool = False,
) -> LotteryEntry:
    now = datetime.now(timezone.utc)
    entry = LotteryEntry(
        show_id=show.id,
        entry_type="staff",
        staff_id=staff.id,
        has_guest=has_guest,
        guest_name=guest_name,
        only_attend_with_guest=only_attend_with_guest,
        status="pending",
        entered_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _make_dj_entry(
    db: Session,
    show: Show,
    staff: Staff,
    dj_name: str,
    assignment_date: date | None = None,
) -> LotteryEntry:
    now = datetime.now(timezone.utc)
    entry = LotteryEntry(
        show_id=show.id,
        entry_type="dj",
        staff_id=staff.id,
        dj_name=dj_name,
        assignment_date=assignment_date or date(2025, 12, 31),
        status="pending",
        entered_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _shuffle_to_order(desired_order: list):
    """Return a side_effect for random.shuffle that reorders to desired_order.

    Items in the shuffled list but absent from desired_order are appended at the end.
    """
    desired_ids = [item.id for item in desired_order]

    def _shuffle(lst):
        by_id = {item.id: item for item in lst}
        result = [by_id[eid] for eid in desired_ids if eid in by_id]
        extras = [item for item in lst if item.id not in set(desired_ids)]
        lst.clear()
        lst.extend(result + extras)

    return _shuffle


def _run_lottery(db: Session, show: Show) -> dict:
    """Run the lottery with email sending suppressed."""
    with patch("app.services.notification_service.send_email"):
        return LotteryService.run_lottery(db, show.id)


def _run_lottery_ordered(db: Session, show: Show, order: list) -> dict:
    """Run the lottery forcing a specific entry ordering."""
    with patch("random.shuffle", side_effect=_shuffle_to_order(order)):
        return _run_lottery(db, show)


def _primary_pass(db: Session, show: Show, staff: Staff) -> Pass | None:
    return (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "staff",
            Pass.staff_id == staff.id,
            Pass.guest_of_pass_id.is_(None),
        )
        .first()
    )


def _guest_pass(db: Session, show: Show, primary: Pass) -> Pass | None:
    return (
        db.query(Pass)
        .filter(Pass.show_id == show.id, Pass.guest_of_pass_id == primary.id)
        .first()
    )


def _count_passes(db: Session, show: Show, pass_type: str, status: str) -> int:
    return (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == pass_type,
            Pass.status == status,
        )
        .count()
    )


# ── Staff Pass Lottery Scenarios ──────────────────────────────────────────────


class TestStaffLotteryScenarios:
    """Tests for all 12 staff pass lottery scenarios."""

    # Scenario 1 ─────────────────────────────────────────────────────────────
    # 2 passes, 2 staff (no guests) → both staff win.

    def test_s1_both_staff_win(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(db, show, alice)

        _run_lottery(db, show)

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "won"
        assert _count_passes(db, show, "staff", "claimed") == 2
        assert _count_passes(db, show, "staff", "available") == 0

    # Scenario 2 ─────────────────────────────────────────────────────────────
    # 2 passes, 3 staff (no guests) → 2 win, 1 loses.

    def test_s2_one_staff_loses(self, db, venue, joe, alice, bob):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(db, show, alice)
        e_bob = _make_staff_entry(db, show, bob)

        _run_lottery(db, show)

        db.refresh(e_joe)
        db.refresh(e_alice)
        db.refresh(e_bob)
        statuses = [e_joe.status, e_alice.status, e_bob.status]
        assert statuses.count("won") == 2
        assert statuses.count("lost") == 1
        assert _count_passes(db, show, "staff", "claimed") == 2

    # Scenario 3 ─────────────────────────────────────────────────────────────
    # 2 passes, 1 staff + 1 staff-with-guest → both staff win, guest gets no pass.

    def test_s3_staff_win_guest_loses(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(db, show, alice, has_guest=True, guest_name="Alice+1")

        _run_lottery(db, show)

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "won"

        alice_primary = _primary_pass(db, show, alice)
        assert alice_primary is not None
        assert alice_primary.has_guest is False
        assert _guest_pass(db, show, alice_primary) is None

    # Scenario 4 ─────────────────────────────────────────────────────────────
    # 2 passes, 2 staff each with +1 → both staff win, both guests get no pass.

    def test_s4_both_staff_win_no_guests(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True, guest_name="Joe+1")
        e_alice = _make_staff_entry(db, show, alice, has_guest=True, guest_name="Alice+1")

        _run_lottery(db, show)

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "won"

        guest_passes = (
            db.query(Pass)
            .filter(
                Pass.show_id == show.id,
                Pass.pass_type == "staff",
                Pass.guest_of_pass_id.isnot(None),
            )
            .count()
        )
        assert guest_passes == 0

    # Scenario 5 ─────────────────────────────────────────────────────────────
    # 3 passes, Joe+guest and Alice+guest.
    # First-drawn staff member gets staff+guest; second gets staff only.

    def test_s5a_joe_first_gets_guest(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=3)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True, guest_name="Joe+1")
        e_alice = _make_staff_entry(db, show, alice, has_guest=True, guest_name="Alice+1")

        _run_lottery_ordered(db, show, [e_joe, e_alice])

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "won"

        joe_primary = _primary_pass(db, show, joe)
        alice_primary = _primary_pass(db, show, alice)
        assert joe_primary.has_guest is True
        assert _guest_pass(db, show, joe_primary) is not None
        assert alice_primary.has_guest is False
        assert _guest_pass(db, show, alice_primary) is None

    def test_s5b_alice_first_gets_guest(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=3)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True, guest_name="Joe+1")
        e_alice = _make_staff_entry(db, show, alice, has_guest=True, guest_name="Alice+1")

        _run_lottery_ordered(db, show, [e_alice, e_joe])

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "won"

        joe_primary = _primary_pass(db, show, joe)
        alice_primary = _primary_pass(db, show, alice)
        assert alice_primary.has_guest is True
        assert _guest_pass(db, show, alice_primary) is not None
        assert joe_primary.has_guest is False
        assert _guest_pass(db, show, joe_primary) is None

    # Scenario 6 ─────────────────────────────────────────────────────────────
    # 5 passes, 3 staff each with +1 → first 2 drawn get staff+guest, third gets staff only.

    def test_s6_first_two_get_guests_third_does_not(self, db, venue, joe, alice, bob):
        show = _make_lottery_show(db, venue, num_staff_passes=5)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True)
        e_alice = _make_staff_entry(db, show, alice, has_guest=True)
        e_bob = _make_staff_entry(db, show, bob, has_guest=True)

        _run_lottery_ordered(db, show, [e_joe, e_alice, e_bob])

        db.refresh(e_joe)
        db.refresh(e_alice)
        db.refresh(e_bob)
        assert e_joe.status == "won"
        assert e_alice.status == "won"
        assert e_bob.status == "won"

        joe_primary = _primary_pass(db, show, joe)
        alice_primary = _primary_pass(db, show, alice)
        bob_primary = _primary_pass(db, show, bob)
        assert joe_primary.has_guest is True
        assert alice_primary.has_guest is True
        assert bob_primary.has_guest is False

    # Scenario 7 ─────────────────────────────────────────────────────────────
    # 3 passes, 1 staff (no guest) + 1 staff-with-guest → both staff win AND guest wins.

    def test_s7_guest_also_wins(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=3)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(db, show, alice, has_guest=True, guest_name="Alice+1")

        _run_lottery(db, show)

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "won"

        alice_primary = _primary_pass(db, show, alice)
        assert alice_primary.has_guest is True
        assert _guest_pass(db, show, alice_primary) is not None

    # Scenario 8 ─────────────────────────────────────────────────────────────
    # 2 passes, Joe (no guest) + Alice (+1, only-with-guest) → Joe wins;
    # Alice cannot get guest → returns staff pass → Alice+guest both lose; 1 pass unfilled.

    def test_s8_only_with_guest_no_room_both_lose(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(
            db,
            show,
            alice,
            has_guest=True,
            guest_name="Alice+1",
            only_attend_with_guest=True,
        )

        _run_lottery_ordered(db, show, [e_joe, e_alice])

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "lost"
        assert _count_passes(db, show, "staff", "claimed") == 1
        assert _count_passes(db, show, "staff", "available") == 1

    # Scenario 9 ─────────────────────────────────────────────────────────────
    # 3 passes, Joe (no guest) + Alice (+1, only-with-guest) → Joe wins, Alice+guest both win.

    def test_s9_only_with_guest_enough_passes_both_win(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=3)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(
            db,
            show,
            alice,
            has_guest=True,
            guest_name="Alice+1",
            only_attend_with_guest=True,
        )

        _run_lottery(db, show)

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "won"

        alice_primary = _primary_pass(db, show, alice)
        assert _guest_pass(db, show, alice_primary) is not None

    # Scenario 10 ─────────────────────────────────────────────────────────────
    # 3 passes, Joe (+1 no only-with-guest) + Alice (+1, only-with-guest).
    # Joe first → Joe+guest; Alice returns pass → Alice+guest lose; 1 unfilled.
    # Alice first → Alice+guest; Joe wins; Joe's guest loses; 0 unfilled.

    def test_s10a_joe_first_alice_only_with_guest_loses(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=3)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True, guest_name="Joe+1")
        e_alice = _make_staff_entry(
            db,
            show,
            alice,
            has_guest=True,
            guest_name="Alice+1",
            only_attend_with_guest=True,
        )

        _run_lottery_ordered(db, show, [e_joe, e_alice])

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "lost"

        joe_primary = _primary_pass(db, show, joe)
        assert joe_primary.has_guest is True
        assert _count_passes(db, show, "staff", "available") == 1

    def test_s10b_alice_first_joe_wins_without_guest(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=3)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True, guest_name="Joe+1")
        e_alice = _make_staff_entry(
            db,
            show,
            alice,
            has_guest=True,
            guest_name="Alice+1",
            only_attend_with_guest=True,
        )

        _run_lottery_ordered(db, show, [e_alice, e_joe])

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_alice.status == "won"
        assert e_joe.status == "won"

        alice_primary = _primary_pass(db, show, alice)
        joe_primary = _primary_pass(db, show, joe)
        assert alice_primary.has_guest is True
        assert _guest_pass(db, show, alice_primary) is not None
        assert joe_primary.has_guest is False
        assert _guest_pass(db, show, joe_primary) is None

    # Scenario 11 ─────────────────────────────────────────────────────────────
    # 5 passes, Joe(+1), Bob(+1), Alice(+1 only-with-guest). 6 orderings:
    # When Alice is drawn before 4 passes are allocated, she gets her guest pass.
    # When Alice is drawn last (after 4 passes used), she loses and 1 pass is unfilled.

    def test_s11_joe_alice_bob(self, db, venue, joe, alice, bob):
        """Joe, Alice, Bob → Joe+guest, Alice+guest, Bob (no guest)."""
        show = _make_lottery_show(db, venue, num_staff_passes=5)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True)
        e_alice = _make_staff_entry(
            db, show, alice, has_guest=True, only_attend_with_guest=True
        )
        e_bob = _make_staff_entry(db, show, bob, has_guest=True)

        _run_lottery_ordered(db, show, [e_joe, e_alice, e_bob])

        db.refresh(e_joe)
        db.refresh(e_alice)
        db.refresh(e_bob)
        assert e_joe.status == "won"
        assert e_alice.status == "won"
        assert e_bob.status == "won"
        assert _primary_pass(db, show, joe).has_guest is True
        assert _primary_pass(db, show, alice).has_guest is True
        assert _primary_pass(db, show, bob).has_guest is False

    def test_s11_bob_alice_joe(self, db, venue, joe, alice, bob):
        """Bob, Alice, Joe → Bob+guest, Alice+guest, Joe (no guest)."""
        show = _make_lottery_show(db, venue, num_staff_passes=5)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True)
        e_alice = _make_staff_entry(
            db, show, alice, has_guest=True, only_attend_with_guest=True
        )
        e_bob = _make_staff_entry(db, show, bob, has_guest=True)

        _run_lottery_ordered(db, show, [e_bob, e_alice, e_joe])

        db.refresh(e_joe)
        db.refresh(e_alice)
        db.refresh(e_bob)
        assert e_bob.status == "won"
        assert e_alice.status == "won"
        assert e_joe.status == "won"
        assert _primary_pass(db, show, bob).has_guest is True
        assert _primary_pass(db, show, alice).has_guest is True
        assert _primary_pass(db, show, joe).has_guest is False

    def test_s11_alice_joe_bob(self, db, venue, joe, alice, bob):
        """Alice, Joe, Bob → Alice+guest, Joe+guest, Bob (no guest)."""
        show = _make_lottery_show(db, venue, num_staff_passes=5)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True)
        e_alice = _make_staff_entry(
            db, show, alice, has_guest=True, only_attend_with_guest=True
        )
        e_bob = _make_staff_entry(db, show, bob, has_guest=True)

        _run_lottery_ordered(db, show, [e_alice, e_joe, e_bob])

        db.refresh(e_joe)
        db.refresh(e_alice)
        db.refresh(e_bob)
        assert e_alice.status == "won"
        assert e_joe.status == "won"
        assert e_bob.status == "won"
        assert _primary_pass(db, show, alice).has_guest is True
        assert _primary_pass(db, show, joe).has_guest is True
        assert _primary_pass(db, show, bob).has_guest is False

    def test_s11_alice_bob_joe(self, db, venue, joe, alice, bob):
        """Alice, Bob, Joe → Alice+guest, Bob+guest, Joe (no guest)."""
        show = _make_lottery_show(db, venue, num_staff_passes=5)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True)
        e_alice = _make_staff_entry(
            db, show, alice, has_guest=True, only_attend_with_guest=True
        )
        e_bob = _make_staff_entry(db, show, bob, has_guest=True)

        _run_lottery_ordered(db, show, [e_alice, e_bob, e_joe])

        db.refresh(e_joe)
        db.refresh(e_alice)
        db.refresh(e_bob)
        assert e_alice.status == "won"
        assert e_bob.status == "won"
        assert e_joe.status == "won"
        assert _primary_pass(db, show, alice).has_guest is True
        assert _primary_pass(db, show, bob).has_guest is True
        assert _primary_pass(db, show, joe).has_guest is False

    def test_s11_joe_bob_alice(self, db, venue, joe, alice, bob):
        """Joe, Bob, Alice → Joe+guest, Bob+guest; Alice loses; 1 unfilled."""
        show = _make_lottery_show(db, venue, num_staff_passes=5)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True)
        e_alice = _make_staff_entry(
            db, show, alice, has_guest=True, only_attend_with_guest=True
        )
        e_bob = _make_staff_entry(db, show, bob, has_guest=True)

        _run_lottery_ordered(db, show, [e_joe, e_bob, e_alice])

        db.refresh(e_joe)
        db.refresh(e_alice)
        db.refresh(e_bob)
        assert e_joe.status == "won"
        assert e_bob.status == "won"
        assert e_alice.status == "lost"
        assert _count_passes(db, show, "staff", "available") == 1

    def test_s11_bob_joe_alice(self, db, venue, joe, alice, bob):
        """Bob, Joe, Alice → Bob+guest, Joe+guest; Alice loses; 1 unfilled."""
        show = _make_lottery_show(db, venue, num_staff_passes=5)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True)
        e_alice = _make_staff_entry(
            db, show, alice, has_guest=True, only_attend_with_guest=True
        )
        e_bob = _make_staff_entry(db, show, bob, has_guest=True)

        _run_lottery_ordered(db, show, [e_bob, e_joe, e_alice])

        db.refresh(e_joe)
        db.refresh(e_alice)
        db.refresh(e_bob)
        assert e_bob.status == "won"
        assert e_joe.status == "won"
        assert e_alice.status == "lost"
        assert _count_passes(db, show, "staff", "available") == 1

    # Scenario 12 ─────────────────────────────────────────────────────────────
    # 3 passes, Joe(+1 only-with-guest) + Alice(+1 only-with-guest).
    # First drawn: that person+guest win; second loses; 1 pass unfilled.

    def test_s12a_joe_first_wins_with_guest_alice_loses(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=3)
        e_joe = _make_staff_entry(
            db, show, joe, has_guest=True, guest_name="Joe+1", only_attend_with_guest=True
        )
        e_alice = _make_staff_entry(
            db,
            show,
            alice,
            has_guest=True,
            guest_name="Alice+1",
            only_attend_with_guest=True,
        )

        _run_lottery_ordered(db, show, [e_joe, e_alice])

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "lost"

        joe_primary = _primary_pass(db, show, joe)
        assert joe_primary.has_guest is True
        assert _guest_pass(db, show, joe_primary) is not None
        assert _count_passes(db, show, "staff", "available") == 1

    def test_s12b_alice_first_wins_with_guest_joe_loses(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=3)
        e_joe = _make_staff_entry(
            db, show, joe, has_guest=True, guest_name="Joe+1", only_attend_with_guest=True
        )
        e_alice = _make_staff_entry(
            db,
            show,
            alice,
            has_guest=True,
            guest_name="Alice+1",
            only_attend_with_guest=True,
        )

        _run_lottery_ordered(db, show, [e_alice, e_joe])

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_alice.status == "won"
        assert e_joe.status == "lost"

        alice_primary = _primary_pass(db, show, alice)
        assert alice_primary.has_guest is True
        assert _guest_pass(db, show, alice_primary) is not None
        assert _count_passes(db, show, "staff", "available") == 1


# ── DJ Pre-Assigned Pass Lottery Scenarios ────────────────────────────────────


class TestDJLotteryScenarios:
    """Tests for all 3 DJ pre-assignment lottery scenarios."""

    # DJ Scenario 1 ───────────────────────────────────────────────────────────
    # 2 pair passes, 1 DJ → 1 pair assigned to DJ, 1 pair unassigned.

    def test_dj_s1_one_dj_wins_one_pair_unassigned(self, db, venue, joe):
        show = _make_lottery_show(db, venue, num_staff_passes=0, num_pair_passes=2)
        e_joe = _make_dj_entry(db, show, joe, dj_name="DJ Joe")

        _run_lottery(db, show)

        db.refresh(e_joe)
        assert e_joe.status == "won"

        assigned = (
            db.query(Pass)
            .filter(
                Pass.show_id == show.id,
                Pass.pass_type == "pair",
                Pass.preassigned_dj.isnot(None),
            )
            .count()
        )
        unassigned = (
            db.query(Pass)
            .filter(
                Pass.show_id == show.id,
                Pass.pass_type == "pair",
                Pass.preassigned_dj.is_(None),
            )
            .count()
        )
        assert assigned == 1
        assert unassigned == 1

        assigned_pass = (
            db.query(Pass)
            .filter(
                Pass.show_id == show.id,
                Pass.pass_type == "pair",
                Pass.preassigned_dj == "DJ Joe",
            )
            .first()
        )
        assert assigned_pass is not None
        assert assigned_pass.preassigned_date == date(2025, 12, 31)

    # DJ Scenario 2 ───────────────────────────────────────────────────────────
    # 2 pair passes, 2 DJs → each DJ gets one pass.

    def test_dj_s2_two_djs_each_get_one_pair(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=0, num_pair_passes=2)
        e_joe = _make_dj_entry(db, show, joe, dj_name="DJ Joe")
        e_alice = _make_dj_entry(db, show, alice, dj_name="DJ Alice")

        _run_lottery(db, show)

        db.refresh(e_joe)
        db.refresh(e_alice)
        assert e_joe.status == "won"
        assert e_alice.status == "won"

        joe_pass = (
            db.query(Pass)
            .filter(
                Pass.show_id == show.id,
                Pass.pass_type == "pair",
                Pass.preassigned_dj == "DJ Joe",
            )
            .first()
        )
        alice_pass = (
            db.query(Pass)
            .filter(
                Pass.show_id == show.id,
                Pass.pass_type == "pair",
                Pass.preassigned_dj == "DJ Alice",
            )
            .first()
        )
        assert joe_pass is not None
        assert alice_pass is not None
        assert joe_pass.id != alice_pass.id

    # DJ Scenario 3 ───────────────────────────────────────────────────────────
    # 2 pair passes, 3 DJs → 2 win, 1 loses.

    def test_dj_s3_three_djs_one_loses(self, db, venue, joe, alice, bob):
        show = _make_lottery_show(db, venue, num_staff_passes=0, num_pair_passes=2)
        e_joe = _make_dj_entry(db, show, joe, dj_name="DJ Joe")
        e_alice = _make_dj_entry(db, show, alice, dj_name="DJ Alice")
        e_bob = _make_dj_entry(db, show, bob, dj_name="DJ Bob")

        _run_lottery_ordered(db, show, [e_joe, e_alice, e_bob])

        db.refresh(e_joe)
        db.refresh(e_alice)
        db.refresh(e_bob)
        statuses = [e_joe.status, e_alice.status, e_bob.status]
        assert statuses.count("won") == 2
        assert statuses.count("lost") == 1
        assert e_bob.status == "lost"

        assigned = (
            db.query(Pass)
            .filter(
                Pass.show_id == show.id,
                Pass.pass_type == "pair",
                Pass.preassigned_dj.isnot(None),
            )
            .count()
        )
        assert assigned == 2


# ── Admin Page (GET /api/shows/{show_id}/lottery) ─────────────────────────────


class TestAdminPageLotteryDisplay:
    """Tests for what the /promotions/admin page shows via the lottery status API."""

    def test_is_active_true_while_window_open(self, client, db, venue, promotions_staff):
        """Lottery is marked active while window is open and not yet drawn."""
        show = _make_lottery_show(db, venue, num_staff_passes=2)

        response = client.get(
            f"/api/shows/{show.id}/lottery",
            headers={"X-Forwarded-User": promotions_staff.email},
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_is_active_false_after_early_run(
        self, client, db, venue, promotions_staff, joe, alice
    ):
        """After lottery runs early (window still open), is_active becomes False."""
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        _make_staff_entry(db, show, joe)
        _make_staff_entry(db, show, alice)

        _run_lottery(db, show)  # run while window is still open

        response = client.get(
            f"/api/shows/{show.id}/lottery",
            headers={"X-Forwarded-User": promotions_staff.email},
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_pending_count_zero_after_lottery(
        self, client, db, venue, promotions_staff, joe, alice
    ):
        """staff_entry_count reflects only pending entries (0 after lottery runs)."""
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        _make_staff_entry(db, show, joe)
        _make_staff_entry(db, show, alice)

        assert (
            client.get(
                f"/api/shows/{show.id}/lottery",
                headers={"X-Forwarded-User": promotions_staff.email},
            ).json()["staff_entry_count"]
            == 2
        )

        _run_lottery(db, show)

        assert (
            client.get(
                f"/api/shows/{show.id}/lottery",
                headers={"X-Forwarded-User": promotions_staff.email},
            ).json()["staff_entry_count"]
            == 0
        )

    def test_promotions_sees_all_entries_with_outcomes(
        self, client, db, venue, promotions_staff, joe, alice
    ):
        """Promotions staff see all_staff_entries with won/lost status after lottery."""
        show = _make_lottery_show(db, venue, num_staff_passes=1)
        _make_staff_entry(db, show, joe)
        _make_staff_entry(db, show, alice)

        _run_lottery(db, show)

        data = client.get(
            f"/api/shows/{show.id}/lottery",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        entries = data["all_staff_entries"]
        assert len(entries) == 2
        statuses = {e["status"] for e in entries}
        assert "won" in statuses
        assert "lost" in statuses

    def test_promotions_sees_pending_entries_before_lottery(
        self, client, db, venue, promotions_staff, joe, alice
    ):
        """Promotions staff see pending entries before lottery runs."""
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        _make_staff_entry(db, show, joe)
        _make_staff_entry(db, show, alice)

        data = client.get(
            f"/api/shows/{show.id}/lottery",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        entries = data["all_staff_entries"]
        assert len(entries) == 2
        assert all(e["status"] == "pending" for e in entries)

    def test_promotions_sees_dj_entries(
        self, client, db, venue, promotions_staff, joe, alice, bob
    ):
        """Promotions staff see all_dj_entries with won/lost status after lottery."""
        show = _make_lottery_show(db, venue, num_staff_passes=0, num_pair_passes=2)
        e_joe = _make_dj_entry(db, show, joe, dj_name="DJ Joe")
        e_alice = _make_dj_entry(db, show, alice, dj_name="DJ Alice")
        e_bob = _make_dj_entry(db, show, bob, dj_name="DJ Bob")

        _run_lottery_ordered(db, show, [e_joe, e_alice, e_bob])

        data = client.get(
            f"/api/shows/{show.id}/lottery",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        dj_entries = data["all_dj_entries"]
        assert len(dj_entries) == 3
        statuses = {e["status"] for e in dj_entries}
        assert "won" in statuses
        assert "lost" in statuses

    def test_regular_staff_cannot_see_all_entries(self, client, db, venue, joe, alice):
        """Regular staff member sees only their own entry, not all_staff_entries."""
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        _make_staff_entry(db, show, joe)
        _make_staff_entry(db, show, alice)

        data = client.get(
            f"/api/shows/{show.id}/lottery",
            headers={"X-Forwarded-User": joe.email},
        ).json()

        assert data["all_staff_entries"] is None
        assert data["my_staff_entry"] is not None
        assert data["my_staff_entry"]["staff_id"] == joe.id


# ── Notification Tests ────────────────────────────────────────────────────────


class TestLotteryNotifications:
    """Tests that the right notification content is sent to the right users."""

    # Case 1: staff won, no guest requested.

    def test_notify_won_no_guest(self, db, venue, joe):
        show = _make_lottery_show(db, venue, num_staff_passes=1)
        _make_staff_entry(db, show, joe)

        with patch("app.services.notification_service.send_email") as mock_send:
            LotteryService.run_lottery(db, show.id)

        mock_send.assert_called_once()
        kw = mock_send.call_args.kwargs
        assert kw["to_email"] == joe.email
        assert "Congratulations" in kw["body_text"]
        assert "staff pass has been reserved" in kw["body_text"]
        assert "guest pass" not in kw["body_text"].lower()

    # Case 2: staff lost, no guest requested.

    def test_notify_lost_no_guest(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=1)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(db, show, alice)

        with patch("random.shuffle", side_effect=_shuffle_to_order([e_joe, e_alice])):
            with patch("app.services.notification_service.send_email") as mock_send:
                LotteryService.run_lottery(db, show.id)

        by_recipient = {c.kwargs["to_email"]: c.kwargs for c in mock_send.call_args_list}
        alice_kw = by_recipient[alice.email]
        assert "not selected" in alice_kw["body_text"]
        assert "Congratulations" not in alice_kw["body_text"]

    # Case 3: staff won, guest also won.

    def test_notify_won_with_guest_pass(self, db, venue, joe):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        _make_staff_entry(db, show, joe, has_guest=True, guest_name="Joe+1")

        with patch("app.services.notification_service.send_email") as mock_send:
            LotteryService.run_lottery(db, show.id)

        kw = next(
            c.kwargs for c in mock_send.call_args_list if c.kwargs["to_email"] == joe.email
        )
        assert "Congratulations" in kw["body_text"]
        assert "guest pass" in kw["body_text"].lower()
        assert "Joe+1" in kw["body_text"]

    # Case 4: staff won, guest did not (has_guest=True, only_attend_with_guest=False).

    def test_notify_won_but_guest_lost(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe, has_guest=True, guest_name="Joe+1")
        e_alice = _make_staff_entry(db, show, alice, has_guest=True, guest_name="Alice+1")

        # 2 staff passes, 2 guests → both staff win, neither guest wins
        with patch("random.shuffle", side_effect=_shuffle_to_order([e_joe, e_alice])):
            with patch("app.services.notification_service.send_email") as mock_send:
                LotteryService.run_lottery(db, show.id)

        by_recipient = {c.kwargs["to_email"]: c.kwargs for c in mock_send.call_args_list}
        joe_kw = by_recipient[joe.email]
        assert "Congratulations" in joe_kw["body_text"]
        assert "not enough passes" in joe_kw["body_text"].lower()
        assert "Joe+1" in joe_kw["body_text"]

    # Case 5: lost from the start, had a guest request (no only_with_guest).

    def test_notify_lost_had_guest(self, db, venue, joe, alice, bob):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(db, show, alice)
        e_bob = _make_staff_entry(db, show, bob, has_guest=True, guest_name="Bob+1")

        with patch(
            "random.shuffle", side_effect=_shuffle_to_order([e_joe, e_alice, e_bob])
        ):
            with patch("app.services.notification_service.send_email") as mock_send:
                LotteryService.run_lottery(db, show.id)

        by_recipient = {c.kwargs["to_email"]: c.kwargs for c in mock_send.call_args_list}
        bob_kw = by_recipient[bob.email]
        assert "neither you nor your guest" in bob_kw["body_text"].lower()

    # Case 7: won a staff pass initially, returned it because no guest + only_with_guest.

    def test_notify_converted_from_winner_to_loser(self, db, venue, joe, alice):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(
            db,
            show,
            alice,
            has_guest=True,
            guest_name="Alice+1",
            only_attend_with_guest=True,
        )

        # Joe first → Joe wins pass1, Alice wins pass2, but Alice can't get a guest
        # pass (none left) → Alice returns pass2. Two-strike rule eventually makes Alice lose.
        with patch("random.shuffle", side_effect=_shuffle_to_order([e_joe, e_alice])):
            with patch("app.services.notification_service.send_email") as mock_send:
                LotteryService.run_lottery(db, show.id)

        db.refresh(e_alice)
        assert e_alice.status == "lost"

        by_recipient = {c.kwargs["to_email"]: c.kwargs for c in mock_send.call_args_list}
        alice_kw = by_recipient[alice.email]
        assert "initially selected" in alice_kw["body_text"].lower()
        assert "returned" in alice_kw["body_text"].lower()

    # Case 8: lost from the start, had only_attend_with_guest.

    def test_notify_lost_only_with_guest(self, db, venue, joe, alice, bob):
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(db, show, alice)
        e_bob = _make_staff_entry(
            db, show, bob, has_guest=True, guest_name="Bob+1", only_attend_with_guest=True
        )

        # Bob ends up third and never gets a pass at all
        with patch(
            "random.shuffle", side_effect=_shuffle_to_order([e_joe, e_alice, e_bob])
        ):
            with patch("app.services.notification_service.send_email") as mock_send:
                LotteryService.run_lottery(db, show.id)

        db.refresh(e_bob)
        assert e_bob.status == "lost"

        by_recipient = {c.kwargs["to_email"]: c.kwargs for c in mock_send.call_args_list}
        bob_kw = by_recipient[bob.email]
        # Should mention that they can only attend with their guest
        assert (
            "only attend" in bob_kw["body_text"].lower()
            or "can only" in bob_kw["body_text"].lower()
        )
        assert "neither you nor your guest" in bob_kw["body_text"].lower()

    # DJ notifications.

    def test_notify_dj_won(self, db, venue, joe):
        show = _make_lottery_show(db, venue, num_staff_passes=0, num_pair_passes=2)
        _make_dj_entry(db, show, joe, dj_name="DJ Joe", assignment_date=date(2025, 12, 31))

        with patch("app.services.notification_service.send_email") as mock_send:
            LotteryService.run_lottery(db, show.id)

        kw = next(
            c.kwargs for c in mock_send.call_args_list if c.kwargs["to_email"] == joe.email
        )
        assert "Congratulations" in kw["body_text"]
        assert "DJ Joe" in kw["body_text"]
        assert (
            "confirmed" in kw["subject"].lower() or "reservation" in kw["subject"].lower()
        )

    def test_notify_dj_lost(self, db, venue, joe, alice, bob):
        show = _make_lottery_show(db, venue, num_staff_passes=0, num_pair_passes=2)
        e_joe = _make_dj_entry(db, show, joe, dj_name="DJ Joe")
        e_alice = _make_dj_entry(db, show, alice, dj_name="DJ Alice")
        e_bob = _make_dj_entry(db, show, bob, dj_name="DJ Bob")

        with patch(
            "random.shuffle", side_effect=_shuffle_to_order([e_joe, e_alice, e_bob])
        ):
            with patch("app.services.notification_service.send_email") as mock_send:
                LotteryService.run_lottery(db, show.id)

        db.refresh(e_bob)
        assert e_bob.status == "lost"

        by_recipient = {c.kwargs["to_email"]: c.kwargs for c in mock_send.call_args_list}
        bob_kw = by_recipient[bob.email]
        assert "not selected" in bob_kw["body_text"].lower()

    def test_no_notification_when_email_disabled(self, db, venue, joe):
        """No email is sent when the user has notifications disabled."""
        show = _make_lottery_show(db, venue, num_staff_passes=1)
        _make_staff_entry(db, show, joe)
        db.add(NotificationPreferences(staff_id=joe.id, email_enabled=False))
        db.commit()

        with patch("app.services.notification_service.send_email") as mock_send:
            LotteryService.run_lottery(db, show.id)

        joe_calls = [
            c for c in mock_send.call_args_list if c.kwargs.get("to_email") == joe.email
        ]
        assert len(joe_calls) == 0

    def test_notification_sent_to_each_entrant(self, db, venue, joe, alice, bob):
        """Every entrant receives exactly one notification."""
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        _make_staff_entry(db, show, joe)
        _make_staff_entry(db, show, alice)
        _make_staff_entry(db, show, bob)

        with patch("app.services.notification_service.send_email") as mock_send:
            LotteryService.run_lottery(db, show.id)

        recipients = {c.kwargs["to_email"] for c in mock_send.call_args_list}
        assert joe.email in recipients
        assert alice.email in recipients
        assert bob.email in recipients
        assert mock_send.call_count == 3


# ── Staff Show Page Tests ─────────────────────────────────────────────────────


class TestStaffShowPage:
    """Tests for what staff see on /staff/shows/:id via the passes and lottery APIs."""

    def test_won_pass_appears_as_claimed_in_passes(
        self, client, db, venue, promotions_staff, joe
    ):
        """After lottery, Joe's won pass appears claimed and linked to Joe."""
        show = _make_lottery_show(db, venue, num_staff_passes=1)
        _make_staff_entry(db, show, joe)

        _run_lottery(db, show)

        passes = client.get(
            f"/api/shows/{show.id}/passes",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        claimed = [
            p for p in passes if p["status"] == "claimed" and p["pass_type"] == "staff"
        ]
        assert len(claimed) == 1
        assert claimed[0]["staff_id"] == joe.id

    def test_loser_has_no_claimed_pass(
        self, client, db, venue, promotions_staff, joe, alice
    ):
        """Staff member who lost has no claimed pass."""
        show = _make_lottery_show(db, venue, num_staff_passes=1)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(db, show, alice)

        _run_lottery_ordered(db, show, [e_joe, e_alice])

        db.refresh(e_alice)
        assert e_alice.status == "lost"

        passes = client.get(
            f"/api/shows/{show.id}/passes",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        alice_passes = [p for p in passes if p.get("staff_id") == alice.id]
        assert len(alice_passes) == 0

    def test_guest_pass_linked_to_primary(self, client, db, venue, promotions_staff, joe):
        """Won guest pass is visible and linked to the primary pass via guest_of_pass_id."""
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        _make_staff_entry(db, show, joe, has_guest=True, guest_name="Joe+1")

        _run_lottery(db, show)

        passes = client.get(
            f"/api/shows/{show.id}/passes",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        claimed = [p for p in passes if p["status"] == "claimed"]
        assert len(claimed) == 2

        primary = next((p for p in claimed if p["guest_of_pass_id"] is None), None)
        guest = next((p for p in claimed if p["guest_of_pass_id"] is not None), None)
        assert primary is not None
        assert guest is not None
        assert guest["guest_of_pass_id"] == primary["id"]
        assert primary["has_guest"] is True

    def test_lottery_status_inactive_after_draw(self, client, db, venue, joe):
        """Staff member sees lottery as inactive on their show page after lottery runs."""
        show = _make_lottery_show(db, venue, num_staff_passes=1)
        _make_staff_entry(db, show, joe)

        _run_lottery(db, show)

        data = client.get(
            f"/api/shows/{show.id}/lottery",
            headers={"X-Forwarded-User": joe.email},
        ).json()

        assert data["is_active"] is False
        # my_staff_entry is None because it's no longer "pending"
        assert data["my_staff_entry"] is None

    def test_unfilled_pass_remains_available(
        self, client, db, venue, promotions_staff, joe, alice
    ):
        """Pass not assigned due to only-with-guest rule is still available."""
        show = _make_lottery_show(db, venue, num_staff_passes=2)
        e_joe = _make_staff_entry(db, show, joe)
        e_alice = _make_staff_entry(
            db,
            show,
            alice,
            has_guest=True,
            guest_name="Alice+1",
            only_attend_with_guest=True,
        )

        _run_lottery_ordered(db, show, [e_joe, e_alice])

        passes = client.get(
            f"/api/shows/{show.id}/passes",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        staff_passes = [p for p in passes if p["pass_type"] == "staff"]
        available = [p for p in staff_passes if p["status"] == "available"]
        claimed = [p for p in staff_passes if p["status"] == "claimed"]
        assert len(available) == 1
        assert len(claimed) == 1


# ── DJ Show Page Tests ────────────────────────────────────────────────────────


class TestDJShowPage:
    """Tests for what DJs see on /dj/shows/:id via the passes and lottery APIs."""

    def test_winning_dj_pair_appears_preassigned(
        self, client, db, venue, promotions_staff, joe
    ):
        """After DJ lottery, the winning DJ's pass has preassigned_dj set."""
        show = _make_lottery_show(db, venue, num_staff_passes=0, num_pair_passes=2)
        _make_dj_entry(db, show, joe, dj_name="DJ Joe", assignment_date=date(2025, 12, 31))

        _run_lottery(db, show)

        passes = client.get(
            f"/api/shows/{show.id}/passes",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        pair_passes = [p for p in passes if p["pass_type"] == "pair"]
        assigned = [p for p in pair_passes if p["preassigned_dj"] is not None]
        unassigned = [p for p in pair_passes if p["preassigned_dj"] is None]

        assert len(assigned) == 1
        assert assigned[0]["preassigned_dj"] == "DJ Joe"
        assert assigned[0]["preassigned_date"] == "2025-12-31"
        assert len(unassigned) == 1

    def test_losing_dj_has_no_preassignment(
        self, client, db, venue, promotions_staff, joe, alice, bob
    ):
        """Losing DJ has no preassigned pass after lottery."""
        show = _make_lottery_show(db, venue, num_staff_passes=0, num_pair_passes=2)
        e_joe = _make_dj_entry(db, show, joe, dj_name="DJ Joe")
        e_alice = _make_dj_entry(db, show, alice, dj_name="DJ Alice")
        e_bob = _make_dj_entry(db, show, bob, dj_name="DJ Bob")

        _run_lottery_ordered(db, show, [e_joe, e_alice, e_bob])

        passes = client.get(
            f"/api/shows/{show.id}/passes",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        pair_passes = [p for p in passes if p["pass_type"] == "pair"]
        bob_assigned = [p for p in pair_passes if p["preassigned_dj"] == "DJ Bob"]
        assert len(bob_assigned) == 0

    def test_all_pairs_assigned_when_djs_equal_passes(
        self, client, db, venue, promotions_staff, joe, alice
    ):
        """When DJ count equals pair count, all pairs get assigned."""
        show = _make_lottery_show(db, venue, num_staff_passes=0, num_pair_passes=2)
        _make_dj_entry(db, show, joe, dj_name="DJ Joe")
        _make_dj_entry(db, show, alice, dj_name="DJ Alice")

        _run_lottery(db, show)

        passes = client.get(
            f"/api/shows/{show.id}/passes",
            headers={"X-Forwarded-User": promotions_staff.email},
        ).json()

        pair_passes = [p for p in passes if p["pass_type"] == "pair"]
        assert all(p["preassigned_dj"] is not None for p in pair_passes)
