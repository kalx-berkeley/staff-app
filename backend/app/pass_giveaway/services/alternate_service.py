"""Alternate queue service for staff passes.

When every staff pass for a show is held by a staff member, staff can join an
ordered alternate queue. Whenever a staff pass frees up, ``fill_open_passes``
promotes waiting alternates into real claims, in order:

1. Staff seats for alternates who will attend alone if needed, in queue order.
   A seat is an available pass or, failing that, the newest guest hold (staff
   always take priority over +1 guests).
2. Pairs for "only with my guest" alternates, once nobody in step 1 is waiting.
   Both passes must be genuinely available (displacing another claimer's guest
   would only trade one guest for a later one); those who can't get a pair are
   skipped but keep their place.
3. Leftover available passes go to guests, in priority order: guests waiting on
   the alternate list, including those of the alternates just promoted, then the
   other guests of alternates promoted in step 1. A guest whose fallback is to wait
   stays on the list, and any other guest request that can't be met is dropped.

``fill_open_passes`` never commits. Callers commit together with the change that
freed the pass, then call ``finalize_promotions`` to send emails and audit.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.common.areas import PASS_GIVEAWAY_AREA
from app.config import settings
from app.models.guest_fallback import GuestFallback
from app.pass_giveaway.services.close_digest import CloseDigest
from app.models.notification_preferences import NotificationPreferences
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_pass_alternate import StaffPassAlternate
from app.common.services.leave_service import (
    ensure_not_on_leave_for_show,
    leave_covers_show,
)

logger = logging.getLogger(__name__)


def _utc(dt: datetime | None) -> datetime:
    """Return dt as UTC-aware, treating naive datetimes as UTC (SQLite stores naively)."""
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _queue_key(entry: StaffPassAlternate):
    return (_utc(entry.priority_at), entry.id or 0)


@dataclass
class MovedGuest:
    """A host's +1 guest who just lost their pass and went on the alternate list."""

    primary: Pass
    reason: str = "claimed"  # "claimed" or "capacity_change"


@dataclass
class Promotion:
    """An alternate who was just given a staff pass."""

    entry: StaffPassAlternate
    pass_item: Pass
    guest_requested: bool
    guest_granted: bool
    trigger: str
    triggering_pass_id: int | None = None
    actor_email: str | None = None


@dataclass
class FillResult:
    """What ``fill_open_passes`` changed, to report once the caller has committed."""

    promotions: list[Promotion] = field(default_factory=list)
    # Hosts whose waiting guest was just given a pass.
    guests_seated: list[Pass] = field(default_factory=list)
    guests_moved: list[MovedGuest] = field(default_factory=list)
    trigger: str | None = None
    actor_email: str | None = None

    def add_moved_guest(self, primary: Pass, reason: str = "claimed") -> None:
        self.guests_moved.append(MovedGuest(primary, reason))


class AlternateService:
    """Service for the staff-pass alternate queue."""

    # ── Queries ──────────────────────────────────────────────────────────────

    @staticmethod
    def waiting_entries(db: Session, show_id: int) -> list[StaffPassAlternate]:
        """Waiting entries for a show in queue order."""
        entries = (
            db.query(StaffPassAlternate)
            .filter(
                StaffPassAlternate.show_id == show_id,
                StaffPassAlternate.status == "waiting",
            )
            .all()
        )
        return sorted(entries, key=_queue_key)

    @staticmethod
    def waiting_guests(db: Session, show_id: int) -> list[Pass]:
        """Passes whose +1 guest is on the alternate list, next in line first."""
        hosts = (
            db.query(Pass)
            .filter(
                Pass.show_id == show_id,
                Pass.pass_type == "staff",
                Pass.status == "claimed",
                Pass.guest_waiting.is_(True),
            )
            .all()
        )
        return sorted(hosts, key=lambda p: p.guest_queue_key)

    @staticmethod
    def entries_expired_at_close(db: Session, show_id: int) -> list[StaffPassAlternate]:
        """
        Entries still waiting when a closed show last closed, in queue order.

        ``expire_on_close`` gives every entry it expires the same ``resolved_at``.
        Older expired entries were left behind by an earlier close, because
        reopening doesn't restore anyone who held a pass at the time. Someone
        who has since been given a pass is left out too.
        """
        expired = (
            db.query(StaffPassAlternate)
            .filter(
                StaffPassAlternate.show_id == show_id,
                StaffPassAlternate.status == "expired",
            )
            .all()
        )
        if not expired:
            return []
        last_close = max(entry.resolved_at for entry in expired)
        return sorted(
            (
                entry
                for entry in expired
                if entry.resolved_at == last_close
                and not AlternateService._has_claim(db, show_id, entry.staff_id)
            ),
            key=_queue_key,
        )

    @staticmethod
    def _eligible(
        show: Show, waiting: list[StaffPassAlternate]
    ) -> list[StaffPassAlternate]:
        """
        Waiting entries that can be promoted now, in queue order.

        Alternates on leave of absence for the whole show are skipped but keep
        their place, so they're eligible again if their leave changes.
        """
        return [e for e in waiting if not leave_covers_show(e.staff, show)]

    @staticmethod
    def _staff_passes(db: Session, show_id: int) -> list[Pass]:
        return (
            db.query(Pass).filter(Pass.show_id == show_id, Pass.pass_type == "staff").all()
        )

    @staticmethod
    def _available(passes: list[Pass]) -> list[Pass]:
        return sorted((p for p in passes if p.status == "available"), key=lambda p: p.id)

    @staticmethod
    def _guest_holds_newest_first(passes: list[Pass]) -> list[Pass]:
        holds = [
            p for p in passes if p.status == "claimed" and p.guest_of_pass_id is not None
        ]
        return sorted(holds, key=lambda p: (_utc(p.claimed_at), p.id), reverse=True)

    @staticmethod
    def _promotion_blocked(db: Session, show: Show) -> bool:
        """Promotion only happens on published shows whose lottery (if any) is drawn."""
        from app.models.lottery_entry import LotteryEntry
        from app.pass_giveaway.services.lottery_service import LotteryService

        if show.status != "published":
            return True
        if not LotteryService.is_lottery_active(show):
            return False
        drawn = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show.id,
                LotteryEntry.status.in_(["won", "lost"]),
            )
            .first()
        ) is not None
        return not drawn

    @staticmethod
    def is_queue_open(db: Session, show: Show) -> bool:
        """True when staff may join: every staff pass is held by a staff member."""
        from app.pass_giveaway.services.lottery_service import LotteryService

        # Joining follows the same lottery rule as direct claims.
        if show.status != "published" or LotteryService.is_lottery_active(show):
            return False
        passes = AlternateService._staff_passes(db, show.id)
        if not passes:
            return False
        return not AlternateService._available(
            passes
        ) and not AlternateService._guest_holds_newest_first(passes)

    @staticmethod
    def get_waiting_entry(
        db: Session, show_id: int, staff_id: int
    ) -> StaffPassAlternate | None:
        return (
            db.query(StaffPassAlternate)
            .filter(
                StaffPassAlternate.show_id == show_id,
                StaffPassAlternate.staff_id == staff_id,
                StaffPassAlternate.status == "waiting",
            )
            .first()
        )

    @staticmethod
    def next_candidate(
        db: Session, show: Show, freed_passes: int
    ) -> StaffPassAlternate | None:
        """
        Who would be promoted if ``freed_passes`` staff passes were released now.

        Used to warn a claimer who is about to release their pass.
        """
        waiting = AlternateService._eligible(
            show, AlternateService.waiting_entries(db, show.id)
        )
        if not waiting or freed_passes <= 0 or show.status != "published":
            return None
        for entry in waiting:
            if entry.guest_fallback != GuestFallback.RELEASE:
                return entry
        passes = AlternateService._staff_passes(db, show.id)
        available = len(AlternateService._available(passes)) + freed_passes
        return waiting[0] if available >= 2 else None

    @staticmethod
    def next_guest_candidate(
        db: Session, show: Show, releasing_pass_id: int
    ) -> Pass | None:
        """The host whose waiting guest would get a released pass, if a guest would."""
        if show.status != "published":
            return None
        for host in AlternateService.waiting_guests(db, show.id):
            if host.id == releasing_pass_id:
                continue
            if not (host.staff and leave_covers_show(host.staff, show)):
                return host
        return None

    # ── Queue membership ────────────────────────────────────────────────────

    @staticmethod
    def _has_claim(db: Session, show_id: int, staff_id: int) -> bool:
        return (
            db.query(Pass)
            .filter(
                Pass.show_id == show_id,
                Pass.pass_type == "staff",
                Pass.staff_id == staff_id,
                Pass.status == "claimed",
                Pass.guest_of_pass_id.is_(None),
            )
            .first()
        ) is not None

    @staticmethod
    def join(
        db: Session,
        show: Show,
        staff: Staff,
        has_guest: bool = False,
        guest_name: str | None = None,
        guest_fallback: str = GuestFallback.ATTEND_ALONE,
    ) -> StaffPassAlternate:
        """Add a staff member to the bottom of a show's alternate queue."""
        from app.pass_giveaway.services.pass_service import PassService

        if show.status != "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The alternate queue is only available for published shows",
            )
        # Same close-time rules as a direct claim.
        PassService._validate_show_claimable(show)
        ensure_not_on_leave_for_show(staff, show)

        if AlternateService._has_claim(db, show.id, staff.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a staff pass for this show",
            )
        if AlternateService.get_waiting_entry(db, show.id, staff.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already in the alternate queue for this show",
            )
        if not AlternateService.is_queue_open(db, show):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Staff passes are still available for this show — claim one"
                    " directly instead of joining the alternate queue"
                ),
            )
        guest_name = guest_name.strip() if guest_name else None
        if has_guest and show.promoted_by.staff_guest_requires_name and not guest_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This show requires a name for your +1 guest",
            )

        now = datetime.now(timezone.utc)
        entry = StaffPassAlternate(
            show_id=show.id,
            staff_id=staff.id,
            has_guest=has_guest,
            guest_name=guest_name if has_guest else None,
            guest_fallback=guest_fallback if has_guest else GuestFallback.ATTEND_ALONE,
            priority_at=now,
            source="joined",
            status="waiting",
            created_at=now,
            updated_at=now,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def update_guest(
        db: Session,
        entry: StaffPassAlternate,
        has_guest: bool,
        guest_name: str | None,
        guest_fallback: str,
    ) -> StaffPassAlternate:
        """Change an entry's +1 details without changing its place in line."""
        guest_name = guest_name.strip() if guest_name else None
        show = entry.show
        if has_guest and show.promoted_by.staff_guest_requires_name and not guest_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This show requires a name for your +1 guest",
            )
        entry.has_guest = has_guest
        entry.guest_name = guest_name if has_guest else None
        entry.guest_fallback = guest_fallback if has_guest else GuestFallback.ATTEND_ALONE
        entry.updated_at = datetime.now(timezone.utc)

        # Dropping the only-with-guest condition can make this entry promotable.
        promotions = AlternateService.fill_open_passes(
            db, show, trigger="alternate_updated"
        )
        db.commit()
        AlternateService.finalize_promotions(db, promotions)
        db.refresh(entry)
        return entry

    @staticmethod
    def leave(db: Session, entry: StaffPassAlternate) -> None:
        """Remove a staff member from the queue at their own request."""
        AlternateService._resolve(entry, "left", datetime.now(timezone.utc))
        db.commit()

    @staticmethod
    def leave_if_waiting(db: Session, show_id: int, staff_id: int, now: datetime) -> None:
        """End a waiting entry because its staff member claimed directly (no commit)."""
        entry = AlternateService.get_waiting_entry(db, show_id, staff_id)
        if entry:
            AlternateService._resolve(entry, "left", now)

    @staticmethod
    def remove(db: Session, entry: StaffPassAlternate, remover: Staff) -> None:
        """Remove an entry on behalf of promotions staff and email the alternate."""
        now = datetime.now(timezone.utc)
        AlternateService._resolve(entry, "removed", now)
        entry.removed_by_staff_id = remover.id
        db.commit()

        show = entry.show
        AlternateService._email(
            db,
            entry.staff,
            subject=f"You have been removed from the alternate list: {show.event_name}",
            lines=[
                (
                    f"{remover.name or remover.email} from KALX Promotions has removed you"
                    " from the staff pass alternate list for"
                    f" {AlternateService._show_desc(show)}."
                ),
                "",
                "If you think this was a mistake, please reply to promotions.",
            ],
        )

    @staticmethod
    def _resolve(entry: StaffPassAlternate, new_status: str, now: datetime) -> None:
        entry.status = new_status
        entry.resolved_at = now
        entry.updated_at = now

    @staticmethod
    def enqueue_lottery_losers(
        db: Session, show: Show, entries: list
    ) -> list[StaffPassAlternate]:
        """Queue staff lottery losers in the order they entered (no commit)."""
        created: list[StaffPassAlternate] = []
        for lottery_entry in sorted(entries, key=lambda e: (_utc(e.entered_at), e.id)):
            if lottery_entry.staff_id is None:
                continue
            if AlternateService.get_waiting_entry(db, show.id, lottery_entry.staff_id):
                continue
            now = datetime.now(timezone.utc)
            created.append(
                StaffPassAlternate(
                    show_id=show.id,
                    staff_id=lottery_entry.staff_id,
                    has_guest=lottery_entry.has_guest,
                    guest_name=lottery_entry.guest_name,
                    guest_fallback=lottery_entry.guest_fallback,
                    priority_at=lottery_entry.entered_at,
                    source="lottery",
                    status="waiting",
                    created_at=now,
                    updated_at=now,
                )
            )
        db.add_all(created)
        db.flush()
        return created

    @staticmethod
    def enqueue_cut_claim(db: Session, show: Show, pass_item: Pass, now: datetime) -> None:
        """
        Queue a claimer whose pass was removed by a pass-count reduction (no commit).

        Their original claim time puts them ahead of every alternate who joined
        later. A lottery winner's claim time is when they entered, so they go
        behind any lottery loser who entered before them.
        """
        existing = AlternateService.get_waiting_entry(db, show.id, pass_item.staff_id)
        if existing:
            return
        db.add(
            StaffPassAlternate(
                show_id=show.id,
                staff_id=pass_item.staff_id,
                has_guest=pass_item.has_guest or pass_item.guest_waiting,
                guest_name=pass_item.guest_name,
                guest_fallback=pass_item.guest_fallback,
                priority_at=pass_item.claimed_at or now,
                source="capacity_cut",
                status="waiting",
                created_at=now,
                updated_at=now,
            )
        )
        db.flush()

    @staticmethod
    def notify_cut_claims(db: Session, show: Show, staff_ids: list[int]) -> None:
        """
        Email claimers whose pass was removed by a pass-count reduction.

        Called after the queue has been refilled, so the email states their
        actual position. Anyone already promoted back into a pass got the
        promotion email instead and is skipped here.
        """
        if not staff_ids:
            return
        positions = {
            e.staff_id: i
            for i, e in enumerate(AlternateService.waiting_entries(db, show.id), start=1)
        }
        for staff_id in staff_ids:
            if staff_id not in positions:
                continue
            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            AlternateService._email(
                db,
                staff,
                subject=f"Your staff pass has been removed: {show.event_name}",
                lines=[
                    (
                        "The number of staff passes for"
                        f" {AlternateService._show_desc(show)} has been reduced, and"
                        " your staff pass was one of those removed."
                    ),
                    "",
                    (
                        "Because you claimed your pass before anyone on the alternate list"
                        " joined, you have been moved to the front of the list as"
                        f" alternate #{positions[staff_id]}."
                    ),
                    (
                        "If a staff pass frees up, it will be assigned to you automatically"
                        " and you'll be emailed."
                    ),
                    "",
                    AlternateService._show_url(show),
                ],
            )

    # ── Promotion ───────────────────────────────────────────────────────────

    @staticmethod
    def fill_open_passes(
        db: Session,
        show: Show,
        trigger: str,
        triggering_pass_id: int | None = None,
        actor_email: str | None = None,
        closing: bool = False,
        digest: CloseDigest | None = None,
    ) -> FillResult:
        """
        Give any free staff passes to waiting alternates, then to waiting guests.

        Does not commit. Returns what changed so the caller can
        ``finalize_promotions`` after committing.

        :param closing: The show is closing, so an alternate who'd give up their pass
            if their guest has none at close only gets a pass with one for the guest.
        :param digest: Where a bump's email goes when part of a close.
        """
        from app.pass_giveaway.services.pass_service import PassService

        result = FillResult(trigger=trigger, actor_email=actor_email)
        if show is None:
            return result
        db.flush()
        if AlternateService._promotion_blocked(db, show):
            return result

        waiting = AlternateService._eligible(
            show, AlternateService.waiting_entries(db, show.id)
        )

        passes = AlternateService._staff_passes(db, show.id)
        by_id = {p.id: p for p in passes}
        now = datetime.now(timezone.utc)
        promotions = result.promotions

        def needs_pair(entry: StaffPassAlternate) -> bool:
            return entry.guest_fallback == GuestFallback.RELEASE or (
                closing and entry.guest_fallback == GuestFallback.WAIT_THEN_RELEASE
            )

        def take_seat() -> Pass | None:
            available = AlternateService._available(passes)
            if available:
                return available[0]
            holds = AlternateService._guest_holds_newest_first(passes)
            if not holds:
                return None
            hold = holds[0]
            primary = by_id.get(hold.guest_of_pass_id)
            PassService._displace_guest_hold(db, hold, primary, show, now, digest)
            if primary is not None and primary.guest_waiting:
                result.add_moved_guest(primary)
            return hold

        def promote(entry: StaffPassAlternate, seat: Pass, guest_pass: Pass | None) -> None:
            PassService._assign_claim(seat, entry.staff_id, now)
            if guest_pass is not None:
                PassService._assign_guest_hold(
                    seat, guest_pass, now, entry.guest_name, entry.guest_fallback
                )
            AlternateService._resolve(entry, "promoted", now)
            entry.promoted_pass_id = seat.id
            waiting.remove(entry)
            promotions.append(
                Promotion(
                    entry=entry,
                    pass_item=seat,
                    guest_requested=entry.has_guest,
                    guest_granted=guest_pass is not None,
                    trigger=trigger,
                    triggering_pass_id=triggering_pass_id,
                    actor_email=actor_email,
                )
            )

        changed = True
        while changed and waiting:
            changed = False

            # Step 1: seats for alternates who will attend without their guest.
            for entry in [e for e in waiting if not needs_pair(e)]:
                seat = take_seat()
                if seat is None:
                    break
                promote(entry, seat, None)
                changed = True
            if any(not needs_pair(e) for e in waiting):
                # Still people waiting for a seat: nothing left for pairs.
                continue

            # Step 2: pairs for only-with-guest alternates. Both passes must be
            # genuinely free: displacing someone else's guest here would only
            # make room for this alternate's guest, and earlier guests win.
            for entry in list(waiting):
                available = AlternateService._available(passes)
                if len(available) < 2:
                    break
                promote(entry, available[0], available[1])
                changed = True

        # Step 3: leftover passes go to guests. Waiting guests come first in priority
        # order, including guests of the alternates just promoted if they can wait.
        promotion_by_seat = {p.pass_item.id: p for p in promotions}
        for promotion in promotions:
            entry = promotion.entry
            if (
                promotion.guest_requested
                and not promotion.guest_granted
                and GuestFallback.waits(entry.guest_fallback)
            ):
                PassService._start_guest_waiting(
                    promotion.pass_item, now, entry.guest_name, entry.guest_fallback
                )

        waiting_hosts = sorted(
            (
                p
                for p in passes
                if p.status == "claimed"
                and p.guest_waiting
                and not (p.staff and leave_covers_show(p.staff, show))
            ),
            key=lambda p: p.guest_queue_key,
        )
        for host in waiting_hosts:
            available = AlternateService._available(passes)
            if not available:
                break
            PassService._assign_guest_hold(
                host, available[0], now, host.guest_name, host.guest_fallback
            )
            if host.id in promotion_by_seat:
                promotion_by_seat[host.id].guest_granted = True
            else:
                result.guests_seated.append(host)

        # Other guests of the alternates just promoted get whatever is left.
        for promotion in promotions:
            if not promotion.guest_requested or promotion.guest_granted:
                continue
            if GuestFallback.waits(promotion.entry.guest_fallback):
                continue
            available = AlternateService._available(passes)
            if not available:
                break
            entry = promotion.entry
            PassService._assign_guest_hold(
                promotion.pass_item,
                available[0],
                now,
                entry.guest_name,
                entry.guest_fallback,
            )
            promotion.guest_granted = True

        return result

    @staticmethod
    def finalize_promotions(
        db: Session, result: FillResult, digest: CloseDigest | None = None
    ) -> None:
        """
        Email and audit what ``fill_open_passes`` did, after the caller commits it.

        :param digest: Part of a close. Promotion news goes in the digest, and guest
            news is left out, because the close outcome says where a guest ended up.
        """
        from app.common.services import audit_service

        moved_host_ids = {moved.primary.id for moved in result.guests_moved}
        for moved in result.guests_moved:
            # A guest given a new pass in the same change has nothing to report.
            if not moved.primary.guest_waiting:
                continue
            AlternateService._report_guest_event(
                db,
                moved.primary,
                "guest_moved_to_alternates",
                None if digest is not None else AlternateService._email_guest_moved,
                moved.reason,
                result,
            )
        for host in result.guests_seated:
            if host.id in moved_host_ids:
                continue
            AlternateService._report_guest_event(
                db,
                host,
                "guest_given_pass",
                None if digest is not None else AlternateService._email_guest_seated,
                result.trigger,
                result,
            )

        for promotion in result.promotions:
            entry = promotion.entry
            try:
                AlternateService._email_promoted(db, promotion, digest)
            except Exception:
                logger.error(
                    "Failed to send alternate promotion email for entry %s",
                    entry.id,
                    exc_info=True,
                )
            audit_service.log_event(
                db,
                event_type="alternate_promoted",
                area=PASS_GIVEAWAY_AREA,
                actor_email=promotion.actor_email,
                actor_role="system",
                entity_type="pass",
                entity_id=promotion.pass_item.id,
                details={
                    "show_id": entry.show_id,
                    "staff_id": entry.staff_id,
                    "alternate_id": entry.id,
                    "trigger": promotion.trigger,
                    "triggering_pass_id": promotion.triggering_pass_id,
                    "guest_requested": promotion.guest_requested,
                    "guest_granted": promotion.guest_granted,
                },
            )

    @staticmethod
    def _report_guest_event(
        db: Session,
        host: Pass,
        event_type: str,
        send_email,
        reason: str | None,
        result: FillResult,
    ) -> None:
        """Email a host about their guest and write the audit log entry."""
        from app.common.services import audit_service

        details = {
            "show_id": host.show_id,
            "staff_id": host.staff_id,
            "guest_name": host.guest_name,
            "guest_fallback": host.guest_fallback,
            "reason": reason,
        }
        try:
            if send_email is not None:
                send_email(db, host, reason)
        except Exception:
            logger.error(
                "Failed to send %s email for pass %s", event_type, host.id, exc_info=True
            )
        audit_service.log_event(
            db,
            event_type=event_type,
            area=PASS_GIVEAWAY_AREA,
            actor_email=result.actor_email,
            actor_role="system",
            entity_type="pass",
            entity_id=host.id,
            details=details,
        )

    # ── Show lifecycle ──────────────────────────────────────────────────────

    @staticmethod
    def release_hosts_without_guests(
        db: Session, show: Show, digest: CloseDigest
    ) -> tuple[list[FillResult], list[StaffPassAlternate]]:
        """
        Release hosts who asked to go only if their waiting guest has a pass by close.

        Runs while the show is still published, so the passes can still be used. It
        releases one host at a time, last in guest order first, and reassigns the pass
        each time, because it may seat an earlier guest and save that host.

        Each released host gets an alternate entry with their original claim time,
        which ``expire_on_close`` expires with the rest of the queue. That's how they
        get their close email, appear under the guest list and return if the show
        reopens. The entries are added at the end so that this close can't promote
        them back. Does not commit.

        :returns: The results to ``finalize_promotions``, and the new entries.
        """
        from app.pass_giveaway.services.pass_service import PassService

        now = datetime.now(timezone.utc)
        results: list[FillResult] = []
        released: list[StaffPassAlternate] = []
        while True:
            # The session doesn't autoflush, and the last pass may have seated a guest.
            db.flush()
            hosts = [
                host
                for host in AlternateService.waiting_guests(db, show.id)
                if host.guest_fallback == GuestFallback.WAIT_THEN_RELEASE
            ]
            if not hosts:
                break
            host = hosts[-1]
            if host.staff_id is not None:
                released.append(
                    StaffPassAlternate(
                        show_id=show.id,
                        staff_id=host.staff_id,
                        has_guest=True,
                        guest_name=host.guest_name,
                        guest_fallback=host.guest_fallback,
                        priority_at=host.claimed_at or now,
                        source="released_at_close",
                        status="waiting",
                        created_at=now,
                        updated_at=now,
                    )
                )
            pass_id = host.id
            PassService._clear_claim(host, now)
            results.append(
                AlternateService.fill_open_passes(
                    db,
                    show,
                    trigger="close_release",
                    triggering_pass_id=pass_id,
                    closing=True,
                    digest=digest,
                )
            )
        db.add_all(released)
        db.flush()
        return results, released

    @staticmethod
    def expire_on_close(db: Session, show: Show) -> int:
        """Close out the queue when the show closes. The caller tells each alternate."""
        waiting = AlternateService.waiting_entries(db, show.id)
        if not waiting:
            return 0
        now = datetime.now(timezone.utc)
        for entry in waiting:
            AlternateService._resolve(entry, "expired", now)
        db.commit()
        AlternateService._audit_bulk(db, "alternates_expired", show, waiting)
        return len(waiting)

    @staticmethod
    def add_expired_outcomes(db: Session, show: Show, digest: CloseDigest) -> int:
        """Add the close email for everyone expired by the last close."""
        entries = AlternateService.entries_expired_at_close(db, show.id)
        for entry in entries:
            desc = AlternateService._show_desc(show)
            if entry.source == "released_at_close":
                guest_label = entry.guest_name or "Your guest"
                digest.add_outcome(
                    entry.staff,
                    f"Your staff pass has been released: {show.event_name}",
                    [
                        f"The guest list for {desc} has been closed.",
                        "",
                        (
                            f"{guest_label} didn't get a pass before the show closed. You"
                            " asked to release your pass in that case, so neither of you"
                            " is on the guest list."
                        ),
                    ],
                    subject_wins=True,
                )
            else:
                digest.add_outcome(
                    entry.staff,
                    f"No staff pass available: {show.event_name}",
                    [
                        f"The guest list for {desc} has been closed.",
                        "",
                        (
                            "Unfortunately, no staff pass became available while you were"
                            " on the alternate list, so you will not be on the guest list."
                        ),
                        "",
                        "Thank you for your interest!",
                    ],
                )
        return len(entries)

    @staticmethod
    def restore_on_reopen(db: Session, show: Show, notify_restored: bool = True) -> int:
        """
        Put entries expired by a close back in line when the show is reopened.

        :param notify_restored: False when the close's emails were being held, so
            restored alternates never heard they were off the list. Anyone promoted
            is still told, and so is anyone whose pass was released at that close,
            who would otherwise still think they had it.
        """
        expired = (
            db.query(StaffPassAlternate)
            .filter(
                StaffPassAlternate.show_id == show.id,
                StaffPassAlternate.status == "expired",
            )
            .all()
        )
        now = datetime.now(timezone.utc)
        restored = []
        released_ids = set()
        for entry in sorted(expired, key=_queue_key):
            # Someone may have claimed a pass or rejoined in the meantime.
            if AlternateService._has_claim(
                db, show.id, entry.staff_id
            ) or AlternateService.get_waiting_entry(db, show.id, entry.staff_id):
                continue
            # From here they're an ordinary alternate, so a later close says so.
            if entry.source == "released_at_close":
                released_ids.add(entry.id)
                entry.source = "joined"
            entry.status = "waiting"
            entry.resolved_at = None
            entry.updated_at = now
            db.flush()
            restored.append(entry)
        # Runs even with nobody restored, because waiting guests can get free passes.
        promotions = AlternateService.fill_open_passes(db, show, trigger="show_reopened")
        db.commit()
        if restored:
            AlternateService._audit_bulk(db, "alternates_restored", show, restored)
        AlternateService.finalize_promotions(db, promotions)
        if not restored:
            return 0

        promoted_ids = {p.entry.id for p in promotions.promotions}
        positions = {
            e.id: i for i, e in enumerate(AlternateService.waiting_entries(db, show.id), 1)
        }
        for entry in restored:
            if entry.id in promoted_ids or entry.id not in positions:
                continue
            was_released = entry.id in released_ids
            if not notify_restored and not was_released:
                continue
            AlternateService._email(
                db,
                entry.staff,
                subject=f"You're back on the alternate list: {show.event_name}",
                lines=[
                    (
                        f"{AlternateService._show_desc(show)} has been reopened, and you"
                        " are back on the staff pass alternate list."
                    ),
                    *(
                        [
                            "",
                            (
                                "Your staff pass was released when the show closed,"
                                f" because {entry.guest_name or 'your guest'} didn't have"
                                " a pass."
                            ),
                        ]
                        if was_released
                        else []
                    ),
                    "",
                    f"You are alternate #{positions[entry.id]}.",
                    (
                        "If a staff pass frees up, it will be assigned to you automatically"
                        " and you'll be emailed."
                    ),
                    "",
                    AlternateService._show_url(show),
                ],
            )
        return len(restored)

    @staticmethod
    def cancel_on_delete(db: Session, show: Show, notify_expired: bool = False) -> int:
        """
        Cancel the queue when the show is deleted and tell waiting alternates.

        :param notify_expired: Also tell those expired by the last close, because
            the email telling them the outcome was still being held.
        """
        entries = (
            db.query(StaffPassAlternate)
            .filter(
                StaffPassAlternate.show_id == show.id,
                StaffPassAlternate.status.in_(["waiting", "expired"]),
            )
            .all()
        )
        if not entries:
            return 0
        now = datetime.now(timezone.utc)
        notify = [e for e in entries if e.status == "waiting"]
        if notify_expired:
            notify += AlternateService.entries_expired_at_close(db, show.id)
        for entry in entries:
            AlternateService._resolve(entry, "cancelled", now)
        db.commit()
        AlternateService._audit_bulk(db, "alternates_cancelled", show, entries)
        for entry in notify:
            AlternateService._email(
                db,
                entry.staff,
                subject=f"Show cancelled: {show.event_name}",
                lines=[
                    (
                        f"{AlternateService._show_desc(show)} has been cancelled, so your"
                        " place on the staff pass alternate list has been removed."
                    ),
                ],
            )
        return len(entries)

    @staticmethod
    def _audit_bulk(db: Session, event_type: str, show: Show, entries: list) -> None:
        from app.common.services import audit_service

        audit_service.log_event(
            db,
            event_type=event_type,
            area=PASS_GIVEAWAY_AREA,
            actor_role="system",
            entity_type="show",
            entity_id=show.id,
            details={
                "alternate_ids": [e.id for e in entries],
                "staff_ids": [e.staff_id for e in entries],
            },
        )

    # ── Email helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _show_desc(show: Show) -> str:
        venue = show.venue.name if show.venue else "the venue"
        return f'"{show.event_name}" at {venue} on {show.show_date}'

    @staticmethod
    def _show_url(show: Show) -> str:
        return f"{settings.frontend_base_url}/pass-giveaway/staff/shows/{show.id}"

    @staticmethod
    def _email(db: Session, staff: Staff | None, subject: str, lines: list[str]) -> None:
        """Send a plain-text email if the staff member has email enabled."""
        from app.common.services import notification_service

        if not staff or not staff.email:
            return
        prefs = (
            db.query(NotificationPreferences)
            .filter(NotificationPreferences.staff_id == staff.id)
            .first()
        )
        if prefs and not prefs.email_enabled:
            return
        notification_service.send_email(
            to_email=staff.email,
            subject=subject,
            body_text="\n".join(lines),
            db=db,
            area=PASS_GIVEAWAY_AREA,
        )

    @staticmethod
    def _guest_waiting_lines(host: Pass) -> list[str]:
        """Where a host's waiting guest stands, and what happens if no pass comes up."""
        guest_label = host.guest_name or "Your guest"
        if host.guest_fallback == GuestFallback.WAIT_THEN_RELEASE:
            at_close = (
                f"If {host.guest_name or 'your guest'} doesn't have a pass when the show"
                " closes, your pass will be released too, and neither of you will be on"
                " the guest list."
            )
        else:
            at_close = (
                f"If {host.guest_name or 'your guest'} doesn't have a pass when the show"
                " closes, you'll still be on the guest list without them."
            )
        return [
            (
                f"{guest_label} is on the alternate list as guest #{host.guest_position}."
                " Staff on the alternate list get freed passes first. After that, if a"
                " pass frees up it will be held for your guest automatically, and we'll"
                " email you."
            ),
            "",
            at_close,
        ]

    @staticmethod
    def _email_guest_moved(db: Session, host: Pass, reason: str | None) -> None:
        """Tell a host that their guest lost their pass and is now waiting."""
        show = host.show
        if reason == "capacity_change":
            cause = (
                f"The number of staff passes for {AlternateService._show_desc(show)} has"
                " been reduced, so there is no longer a pass for your guest."
            )
        else:
            cause = (
                "Another staff member has claimed a pass for"
                f" {AlternateService._show_desc(show)}, so there is no longer a pass for"
                " your guest."
            )
        AlternateService._email(
            db,
            host.staff,
            subject=f"Your guest is on the alternate list: {show.event_name}",
            lines=[
                cause,
                "",
                *AlternateService._guest_waiting_lines(host),
                "",
                "You still have your own staff pass.",
                "",
                AlternateService._show_url(show),
            ],
        )

    @staticmethod
    def _email_guest_seated(db: Session, host: Pass, reason: str | None) -> None:
        """Tell a host that their waiting guest now has a pass."""
        show = host.show
        guest_label = host.guest_name or "your guest"
        AlternateService._email(
            db,
            host.staff,
            subject=f"Your guest has a pass: {show.event_name}",
            lines=[
                (
                    f"A staff pass has opened up for {AlternateService._show_desc(show)},"
                    f" and it is now being held for {guest_label}."
                ),
                "",
                (
                    "Staff take priority over guests, so until the show closes, your"
                    " guest's pass may go to another staff member who needs one. If that"
                    " happens, your guest goes back to the same place on the alternate"
                    " list and we'll email you. When the show closes, we'll email you to"
                    " confirm your guest."
                ),
                "",
                AlternateService._show_url(show),
            ],
        )

    @staticmethod
    def email_guest_removed(
        db: Session, host: Pass, guest_name: str | None, remover: Staff
    ) -> None:
        """Tell a host that promotions staff removed their guest."""
        show = host.show
        AlternateService._email(
            db,
            host.staff,
            subject=f"Your guest has been removed: {show.event_name}",
            lines=[
                (
                    f"{remover.name or remover.email} from KALX Promotions has removed"
                    f" {guest_name or 'your +1 guest'} from your staff pass for"
                    f" {AlternateService._show_desc(show)}."
                ),
                "",
                "You still have your own staff pass.",
                "",
                "If you think this was a mistake, please reply to promotions.",
            ],
        )

    @staticmethod
    def _email_promoted(
        db: Session, promotion: Promotion, digest: CloseDigest | None = None
    ) -> None:
        entry = promotion.entry
        show = entry.show
        guest_label = entry.guest_name or "your guest"
        lines = [
            (
                "Good news! A staff pass has opened up for"
                f" {AlternateService._show_desc(show)}, and because you were next on the"
                " alternate list it is now yours."
            ),
            "",
        ]
        if promotion.guest_requested and promotion.guest_granted:
            lines.append(f"A guest pass is also being held for {guest_label}.")
            lines.append("")
            bumped_line = (
                " Because you said you can only attend with your guest, your staff pass"
                " would be released too."
                if entry.guest_fallback == GuestFallback.RELEASE
                else ""
            )
            lines.append(
                "Staff take priority over guests, so until the show closes, your guest's"
                " pass may go to another staff member who needs one. If that happens,"
                f" we'll email you.{bumped_line} When the show closes, we'll email you to"
                " confirm your guest."
            )
            lines.append("")
        elif promotion.guest_requested and promotion.pass_item.guest_waiting:
            lines.extend(AlternateService._guest_waiting_lines(promotion.pass_item))
            lines.append("")
        elif promotion.guest_requested:
            lines.append(
                f"Unfortunately there was no pass left for {guest_label}, so your guest"
                " request has been dropped. You may still attend on your own."
            )
            lines.append("")
        lines.extend([
            (
                "No further action is needed. Your name will be on the guest list sent to"
                " the venue when the show closes."
            ),
            "",
            (
                "If you can no longer attend, please release your pass so it can go to the"
                " next person:"
            ),
            AlternateService._show_url(show),
        ])
        subject = f"You got a staff pass to {show.event_name}!"
        if digest is not None:
            digest.add_intro(entry.staff, subject, lines, short_lines=lines[:1])
        else:
            AlternateService._email(db, entry.staff, subject=subject, lines=lines)
