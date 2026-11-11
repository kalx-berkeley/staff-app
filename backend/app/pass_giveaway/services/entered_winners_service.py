"""Winners a promotions rep enters on the show form.

A show that replaces a cancelled, postponed or moved one can carry some of its
on-air and staff winners over. The rep types them in under Advanced on the
New Show or Edit Show form. See
docs/pass-giveaway/specs/preassigned-winners/plan.md.

They skip the venue's win-frequency limit and the lottery, and no one is
emailed. The venue's guest list rules and the normal staff claim rules
(Active only, not on leave) still apply.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth import can_claim_staff_passes
from app.common.areas import PASS_GIVEAWAY_AREA
from app.common.services import audit_service
from app.common.services.leave_service import format_leave, on_leave
from app.models.guest_fallback import GuestFallback
from app.models.lottery_entry import LotteryEntry
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import STAFF_CLAIM_PASS_TYPES, Pass
from app.models.promoter import Promoter
from app.models.show import Show
from app.models.staff import Staff
from app.models.venue import Venue
from app.pass_giveaway.services.pass_service import PassService, normalize_phone

ENTERABLE_STATUSES = ("draft", "published")


class OnAirWinnerData(Protocol):
    """An on-air winner's details, from the show form or the legacy import."""

    recipient_name: str
    recipient_phone: str
    recipient_email: str | None
    given_away_by_dj: str | None


class StaffWinnerData(Protocol):
    """A staff claim, from the show form or the legacy import."""

    staff_id: int
    has_guest: bool
    guest_name: str | None


@dataclass
class FreePasses:
    """How many passes the entered winners can go on."""

    pairs: int
    staff: int


def _reject(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def guest_list_rules_owner(
    db: Session, venue_id: int, promoter_id: int | None
) -> Promoter | Venue:
    """The promoter or, when there's none, the venue, whose guest list rules apply."""
    if promoter_id is not None:
        promoter = db.query(Promoter).filter(Promoter.id == promoter_id).first()
        if promoter is not None:
            return promoter
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if venue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venue with id {venue_id} not found",
        )
    return venue


def free_passes_after_adjustment(
    show: Show,
    num_pass_pairs: int,
    staff_pass_adjustment: int,
    num_tabler_passes: int | None = None,
) -> FreePasses:
    """
    Count the passes winners can go on once the show's pass counts change.

    Mirrors ``PassService.adjust_passes_for_show``, which adds free passes when
    a count goes up and removes free ones first when it goes down. Pass pairs
    reserved for a DJ never count, and nor do tabler passes.

    :param num_tabler_passes: The show's tabler pass count after the change
        (defaults to its current count).
    """
    pairs = [p for p in show.passes if p.pass_type == "pair"]
    staff = [p for p in show.passes if p.pass_type == "staff"]
    if num_tabler_passes is None:
        num_tabler_passes = sum(1 for p in show.passes if p.pass_type == "tabler")
    free_pairs = sum(1 for p in pairs if p.status == "available" and not p.preassigned_dj)
    free_staff = sum(1 for p in staff if p.status == "available")
    pair_delta = num_pass_pairs - len(pairs)
    staff_delta = num_pass_pairs + staff_pass_adjustment - num_tabler_passes - len(staff)
    return FreePasses(
        pairs=max(0, free_pairs + pair_delta),
        staff=max(0, free_staff + staff_delta),
    )


def validate(
    db: Session,
    *,
    rules_owner: Promoter | Venue,
    first_day: date,
    last_day: date,
    free: FreePasses,
    on_air_winners: Sequence[OnAirWinnerData],
    staff_winners: Sequence[StaffWinnerData],
    show: Show | None = None,
) -> list[Staff]:
    """
    Check the entered winners before anything is saved.

    :param rules_owner: The promoter or venue whose guest list rules apply.
    :param first_day: The show's first day (its start date, or its date).
    :param last_day: The show's date.
    :param free: The passes the winners can go on.
    :param show: The show being edited, or None for a new show.
    :returns: The staff members, in the order of ``staff_winners``.
    :raises HTTPException: 422 naming the first problem found.
    """
    if show is not None and show.status not in ENTERABLE_STATUSES:
        raise _reject(f"Winners can't be entered on a {show.status} show")

    for winner in on_air_winners:
        if not winner.recipient_name.strip():
            raise _reject("Every on-air winner needs a name")
        if not normalize_phone(winner.recipient_phone):
            raise _reject(f"{winner.recipient_name} needs a phone number")
        if (
            rules_owner.requires_email_address
            and not (winner.recipient_email or "").strip()
        ):
            raise _reject(
                f"{rules_owner.name} requires an email address for every on-air winner"
            )

    claimants: list[Staff] = []
    seen: set[int] = set()
    for entry in staff_winners:
        staff = db.query(Staff).filter(Staff.id == entry.staff_id).first()
        if staff is None:
            raise _reject(f"Staff member with id {entry.staff_id} not found")
        name = staff.name or staff.email
        if entry.staff_id in seen:
            raise _reject(f"{name} is entered more than once")
        seen.add(entry.staff_id)
        if not can_claim_staff_passes(staff):
            raise _reject(f"{name} isn't Active staff, so can't get a staff pass")
        if on_leave(staff, first_day) and on_leave(staff, last_day):
            raise _reject(
                f"{name} is on leave of absence {format_leave(staff)}, so can't get a"
                " staff pass for this show"
            )
        if show is not None and any(
            p.pass_type in STAFF_CLAIM_PASS_TYPES
            and p.status == "claimed"
            and p.staff_id == staff.id
            and p.guest_of_pass_id is None
            for p in show.passes
        ):
            raise _reject(f"{name} already has a staff pass for this show")
        if (
            entry.has_guest
            and rules_owner.staff_guest_requires_name
            and not (entry.guest_name or "").strip()
        ):
            raise _reject(f"{rules_owner.name} requires a name for every staff +1 guest")
        claimants.append(staff)

    pairs_short = len(on_air_winners) - free.pairs
    if pairs_short > 0:
        raise _reject(
            f"{len(on_air_winners)} on-air winners need {pairs_short} more free pass"
            f" pair{'' if pairs_short == 1 else 's'} than this show has"
        )
    staff_needed = sum(2 if e.has_guest else 1 for e in staff_winners)
    staff_short = staff_needed - free.staff
    if staff_short > 0:
        raise _reject(
            f"The staff winners and their guests need {staff_short} more free staff"
            f" pass{'' if staff_short == 1 else 'es'} than this show has"
        )
    return claimants


def assign_winners_and_claims(
    db: Session,
    show: Show,
    pair_pool: list[Pass],
    staff_pool: list[Pass],
    on_air_winners: Sequence[OnAirWinnerData],
    staff_winners: Sequence[StaffWinnerData],
    claimants: list[Staff],
    now: datetime,
) -> None:
    """
    Put on-air winners and staff claims on pools of free passes (no commit).

    The caller has checked that the pools are big enough. Each staff winner
    with a guest uses two staff passes: their own and a guest hold.
    """
    for pair_pass, data in zip(pair_pool, on_air_winners):
        dj = (data.given_away_by_dj or "").strip() or "Unknown"
        pair_pass.status = "given_away"
        pair_pass.given_away_by_dj = dj
        pair_pass.given_away_at = now
        pair_pass.updated_at = now
        db.add(
            OnAirWinner(
                pass_id=pair_pass.id,
                venue_id=show.venue_id,
                show_id=show.id,
                recipient_name=data.recipient_name.strip(),
                recipient_phone=normalize_phone(data.recipient_phone),
                recipient_email=(data.recipient_email or "").strip() or None,
                given_away_by_dj=dj,
                created_at=now,
            )
        )

    pool = iter(staff_pool)
    for data, staff in zip(staff_winners, claimants):
        primary = next(pool)
        PassService._assign_claim(primary, staff.id, now)
        if data.has_guest:
            guest_name = (data.guest_name or "").strip() or None
            PassService._assign_guest_hold(
                primary, next(pool), now, guest_name, GuestFallback.ATTEND_ALONE
            )


def enter(
    db: Session,
    show: Show,
    on_air_winners: Sequence[OnAirWinnerData],
    staff_winners: Sequence[StaffWinnerData],
    claimants: list[Staff],
    actor_email: str,
) -> None:
    """
    Put checked winners on the show's free passes, then commit and audit-log them.

    Like a direct claim, a staff winner's place on the alternate list ends. A
    pending staff lottery entry is removed too. No one is emailed.
    """
    from app.pass_giveaway.services.alternate_service import AlternateService

    if not on_air_winners and not staff_winners:
        return
    db.refresh(show)
    by_id = sorted(show.passes, key=lambda p: p.id)
    pair_pool = [
        p
        for p in by_id
        if p.pass_type == "pair" and p.status == "available" and not p.preassigned_dj
    ]
    staff_pool = [p for p in by_id if p.pass_type == "staff" and p.status == "available"]
    now = datetime.now(timezone.utc)

    assign_winners_and_claims(
        db, show, pair_pool, staff_pool, on_air_winners, staff_winners, claimants, now
    )
    for staff in claimants:
        AlternateService.leave_if_waiting(db, show.id, staff.id, now)
        db.query(LotteryEntry).filter(
            LotteryEntry.show_id == show.id,
            LotteryEntry.entry_type == "staff",
            LotteryEntry.staff_id == staff.id,
            LotteryEntry.status == "pending",
        ).delete(synchronize_session="fetch")
    db.commit()

    for data in on_air_winners:
        audit_service.log_event(
            db,
            event_type="on_air_winner_entered_by_promotions",
            area=PASS_GIVEAWAY_AREA,
            actor_email=actor_email,
            actor_role="promotions",
            entity_type="show",
            entity_id=show.id,
            details={
                "event_name": show.event_name,
                "recipient_name": data.recipient_name.strip(),
                "given_away_by_dj": (data.given_away_by_dj or "").strip() or "Unknown",
            },
        )
    for data, staff in zip(staff_winners, claimants):
        audit_service.log_event(
            db,
            event_type="staff_pass_assigned_by_promotions",
            area=PASS_GIVEAWAY_AREA,
            actor_email=actor_email,
            actor_role="promotions",
            entity_type="show",
            entity_id=show.id,
            details={
                "event_name": show.event_name,
                "staff_name": staff.name,
                "staff_email": staff.email,
                "has_guest": data.has_guest,
            },
        )
    db.refresh(show)
