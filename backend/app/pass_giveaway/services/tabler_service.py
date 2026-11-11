"""
Tabler passes for the KALX Co-Announce Table.

At a co-announce show, Publicity members sit at the KALX table. Some of the
show's staff passes are set aside for them as tabler passes: ``Pass`` rows with
``pass_type = "tabler"``. Staff rows plus tabler rows always add up to
``show.num_staff_passes``, and there are ``show.num_tabler_passes`` tabler rows.
Tabler passes are always first come, first served, and never have a +1 guest,
an alternate list or a lottery. The design is in
``docs/pass-giveaway/specs/tabler-passes/plan.md``.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth import is_current_staff
from app.common.services.leave_service import ensure_not_on_leave_for_show
from app.models.lottery_entry import LotteryEntry
from app.models.pass_model import STAFF_CLAIM_PASS_TYPES, Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_pass_alternate import StaffPassAlternate

TABLER = "tabler"
DEFAULT_TABLER_PASSES = 2
TABLE_NAME = "KALX Co-Announce Table"


def _as_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def newest_first(passes: list[Pass]) -> list[Pass]:
    """Claimed passes, most recently claimed first (the order they're bumped in)."""
    return sorted(passes, key=lambda p: (_as_utc(p.claimed_at), p.id), reverse=True)


def target_count(
    *,
    co_announce: bool,
    requested: int | None,
    current: int,
    was_co_announce: bool,
) -> int | None:
    """
    The tabler pass count a show should end up with after a save.

    :param requested: The count sent with the save, or None when it wasn't sent.
    :param current: The show's count before the save (0 for a new show).
    :returns: The count, or None to keep whatever a change to the staff pass
        total leaves.
    """
    if not co_announce:
        return 0
    if requested is not None:
        return requested
    return None if was_co_announce else DEFAULT_TABLER_PASSES


@dataclass
class TablerPlan:
    """What a save would do to a show's tabler passes."""

    # Claimed tabler passes that would be released, newest claim first
    lost: list[Pass] = field(default_factory=list)


def plan(show: Show, new_total: int, target: int | None) -> TablerPlan:
    """
    Work out what changing the staff pass total and the tabler count would do.

    Mirrors ``PassService.adjust_passes_for_show`` (which removes unclaimed staff
    passes, then unclaimed tabler passes, then staff claims, then tabler claims)
    followed by ``apply_count``. Raises a 400 when the tabler passes wouldn't fit
    in the unclaimed staff passes.
    """
    staff = [p for p in show.passes if p.pass_type == "staff"]
    tabler = [p for p in show.passes if p.pass_type == TABLER]
    claimed_tabler = newest_first([p for p in tabler if p.status == "claimed"])
    staff_free = sum(1 for p in staff if p.status == "available")
    staff_claimed = len(staff) - staff_free
    tabler_free = len(tabler) - len(claimed_tabler)

    # The staff pass total changes first.
    excess = max(0, len(staff) + len(tabler) - new_total)
    added = max(0, new_total - len(staff) - len(tabler))
    r = excess
    cut_staff_free = min(r, staff_free)
    r -= cut_staff_free
    cut_tabler_free = min(r, tabler_free)
    r -= cut_tabler_free
    cut_staff_claimed = min(r, staff_claimed)
    r -= cut_staff_claimed
    cut_tabler_claimed = r

    staff_free_after = staff_free - cut_staff_free + added
    staff_claimed_after = staff_claimed - cut_staff_claimed
    tabler_after = len(tabler) - cut_tabler_free - cut_tabler_claimed
    tabler_free_after = tabler_free - cut_tabler_free

    # Then the tabler count.
    released = cut_tabler_claimed
    if target is None:
        target = tabler_after
    if target > tabler_after:
        needed = target - tabler_after
        if needed > staff_free_after:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"There's room for at most {tabler_after + staff_free_after} tabler"
                    f" passes: {staff_claimed_after} of the {new_total} staff passes"
                    " are claimed"
                    " (including +1 guest passes). Raise the Staff Pass Adjustment to"
                    " make room."
                ),
            )
    elif target < tabler_after:
        drop = tabler_after - target
        released += max(0, drop - tabler_free_after)
    return TablerPlan(lost=claimed_tabler[:released])


def lost_tablers_conflict(lost: list[Pass]) -> HTTPException:
    """The 409 that asks the form to confirm releasing these tablers' passes."""
    names = [p.staff.name if p.staff else "Unknown" for p in lost]
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "tabler_claims_released",
            "message": (
                "This save releases tabler passes that people have claimed: "
                + ", ".join(names)
            ),
            "tablers": names,
        },
    )


def apply_count(db: Session, show: Show, target: int) -> list[Staff]:
    """
    Convert passes between staff and tabler so the show has *target* tabler passes.

    Raising the count turns unclaimed staff passes into tabler passes. Lowering
    it turns unclaimed tabler passes into staff passes first, then releases the
    newest tabler claims. Doesn't commit, and doesn't fill freed staff passes
    from the alternate list: the caller does both.

    :returns: The tablers whose pass was released, to be emailed.
    """
    tabler = [p for p in show.passes if p.pass_type == TABLER]
    now = datetime.now(timezone.utc)
    released: list[Staff] = []
    if target > len(tabler):
        free_staff = [
            p for p in show.passes if p.pass_type == "staff" and p.status == "available"
        ]
        needed = target - len(tabler)
        if needed > len(free_staff):
            # plan() should have refused this first.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="There aren't enough unclaimed staff passes for the tabler passes",
            )
        for p in free_staff[:needed]:
            p.pass_type = TABLER
            p.updated_at = now
    elif target < len(tabler):
        drop = len(tabler) - target
        free = [p for p in tabler if p.status == "available"]
        claimed = newest_first([p for p in tabler if p.status == "claimed"])
        for p in (free + claimed)[:drop]:
            if p.status == "claimed":
                if p.staff:
                    released.append(p.staff)
                clear_claim(p, now)
            p.pass_type = "staff"
            p.updated_at = now
    show.num_tabler_passes = target
    return released


def clear_claim(pass_item: Pass, now: datetime) -> None:
    pass_item.staff_id = None
    pass_item.claimed_at = None
    pass_item.status = "available"
    pass_item.updated_at = now


def held_pass(db: Session, show_id: int, staff_id: int) -> Pass | None:
    """The staff or tabler pass this person holds for the show, if any."""
    return (
        db.query(Pass)
        .filter(
            Pass.show_id == show_id,
            Pass.pass_type.in_(STAFF_CLAIM_PASS_TYPES),
            Pass.staff_id == staff_id,
            Pass.status == "claimed",
            Pass.guest_of_pass_id.is_(None),
        )
        .first()
    )


def holds_tabler_pass(db: Session, show_id: int, staff_id: int) -> bool:
    return (
        db.query(Pass)
        .filter(
            Pass.show_id == show_id,
            Pass.pass_type == TABLER,
            Pass.staff_id == staff_id,
            Pass.status == "claimed",
        )
        .first()
    ) is not None


def ensure_holds_no_tabler_pass(db: Session, show_id: int, staff_id: int, who: str) -> None:
    """Refuse a staff pass, lottery entry or alternate spot to a tabler."""
    if holds_tabler_pass(db, show_id, staff_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{who} a tabler pass for this show. Release it first to get a staff"
                " pass instead."
            ),
        )


def _ensure_free_to_table(db: Session, show: Show, staff: Staff, you: bool) -> None:
    """One pass per person per show: no tabler pass for anyone holding or waiting."""
    who = "You already have" if you else f"{staff.name} already has"
    held = held_pass(db, show.id, staff.id)
    if held is not None:
        kind = "a tabler pass" if held.pass_type == TABLER else "a staff pass"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{who} {kind} for this show"
            + ("" if held.pass_type == TABLER else ". Release it first."),
        )
    waiting = (
        db.query(StaffPassAlternate)
        .filter(
            StaffPassAlternate.show_id == show.id,
            StaffPassAlternate.staff_id == staff.id,
            StaffPassAlternate.status == "waiting",
        )
        .first()
    )
    if waiting is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{'You are' if you else staff.name + ' is'} on the alternate list for"
                " this show. Leave it first."
            ),
        )
    entry = (
        db.query(LotteryEntry)
        .filter(
            LotteryEntry.show_id == show.id,
            LotteryEntry.staff_id == staff.id,
            LotteryEntry.entry_type == "staff",
            LotteryEntry.status == "pending",
        )
        .first()
    )
    if entry is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{'You have' if you else staff.name + ' has'} entered the staff pass"
                " lottery for this show. Withdraw first."
            ),
        )


def claim(db: Session, show: Show, staff: Staff, *, by_self: bool) -> Pass:
    """
    Give *staff* one of the show's open tabler passes and commit.

    The caller checks who may claim (Publicity for themselves, any current
    staff when promotions assigns).
    """
    from app.pass_giveaway.services.pass_service import PassService

    if not show.co_announce or show.num_tabler_passes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This show has no tabler passes",
        )
    PassService._validate_show_claimable(show)
    if not is_current_staff(staff):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{staff.name} isn't current staff, so can't get a tabler pass",
        )
    ensure_not_on_leave_for_show(staff, show)
    _ensure_free_to_table(db, show, staff, you=by_self)
    open_pass = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == TABLER,
            Pass.status == "available",
        )
        .order_by(Pass.id)
        .first()
    )
    if open_pass is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All the tabler passes for this show have been claimed",
        )
    now = datetime.now(timezone.utc)
    open_pass.staff_id = staff.id
    open_pass.claimed_at = now
    open_pass.status = "claimed"
    open_pass.updated_at = now
    db.commit()
    db.refresh(open_pass)
    return open_pass


def _email(db: Session, staff: Staff, show: Show, subject: str, first_line: str) -> None:
    from app.pass_giveaway.services.alternate_service import AlternateService

    AlternateService._email(
        db,
        staff,
        subject=subject,
        lines=[first_line, "", AlternateService._show_url(show)],
    )


def email_assigned(db: Session, staff: Staff, show: Show) -> None:
    from app.pass_giveaway.services.alternate_service import AlternateService

    _email(
        db,
        staff,
        show,
        f"You have a tabler pass: {show.event_name}",
        "KALX Promotions has given you a tabler pass for"
        f" {AlternateService._show_desc(show)}, to help at the {TABLE_NAME}.",
    )


def email_released_by_promotions(db: Session, staff: Staff, show: Show) -> None:
    from app.pass_giveaway.services.alternate_service import AlternateService

    _email(
        db,
        staff,
        show,
        f"Your tabler pass was released: {show.event_name}",
        "KALX Promotions has released your tabler pass for"
        f" {AlternateService._show_desc(show)}, so you're no longer on the guest"
        f" list for the {TABLE_NAME}.",
    )


def email_count_lowered(db: Session, staff_list: list[Staff], show: Show) -> None:
    """Tell tablers whose pass went because the tabler or staff passes were lowered."""
    from app.pass_giveaway.services.alternate_service import AlternateService

    for staff in staff_list:
        _email(
            db,
            staff,
            show,
            f"Your tabler pass was released: {show.event_name}",
            "KALX Promotions has reduced the number of tabler passes for"
            f" {AlternateService._show_desc(show)}, so your tabler pass for the"
            f" {TABLE_NAME} has been released.",
        )
