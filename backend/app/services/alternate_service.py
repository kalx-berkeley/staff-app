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
3. Leftover available passes go to the +1 guests of the alternates promoted in
   step 1. Guest requests that can't be met are dropped.

``fill_open_passes`` never commits. Callers commit together with the change that
freed the pass, then call ``finalize_promotions`` to send emails and audit.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.notification_preferences import NotificationPreferences
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_pass_alternate import StaffPassAlternate

logger = logging.getLogger(__name__)


def _utc(dt: datetime | None) -> datetime:
    """Return dt as UTC-aware, treating naive datetimes as UTC (SQLite stores naively)."""
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _queue_key(entry: StaffPassAlternate):
    return (_utc(entry.priority_at), entry.id or 0)


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
        from app.services.lottery_service import LotteryService

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
        from app.services.lottery_service import LotteryService

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
        waiting = AlternateService.waiting_entries(db, show.id)
        if not waiting or freed_passes <= 0 or show.status != "published":
            return None
        for entry in waiting:
            if not entry.only_attend_with_guest:
                return entry
        passes = AlternateService._staff_passes(db, show.id)
        available = len(AlternateService._available(passes)) + freed_passes
        return waiting[0] if available >= 2 else None

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
        only_attend_with_guest: bool = False,
    ) -> StaffPassAlternate:
        """Add a staff member to the bottom of a show's alternate queue."""
        from app.services.pass_service import PassService

        if show.status != "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The alternate queue is only available for published shows",
            )
        # Same close-time rules as a direct claim.
        PassService._validate_show_claimable(show)

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
        if (
            has_guest
            and show.venue
            and show.venue.staff_guest_requires_name
            and not guest_name
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This venue requires a name for your +1 guest",
            )

        now = datetime.now(timezone.utc)
        entry = StaffPassAlternate(
            show_id=show.id,
            staff_id=staff.id,
            has_guest=has_guest,
            guest_name=guest_name if has_guest else None,
            only_attend_with_guest=only_attend_with_guest if has_guest else False,
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
        only_attend_with_guest: bool,
    ) -> StaffPassAlternate:
        """Change an entry's +1 details without changing its place in line."""
        guest_name = guest_name.strip() if guest_name else None
        show = entry.show
        if (
            has_guest
            and show.venue
            and show.venue.staff_guest_requires_name
            and not guest_name
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This venue requires a name for your +1 guest",
            )
        entry.has_guest = has_guest
        entry.guest_name = guest_name if has_guest else None
        entry.only_attend_with_guest = only_attend_with_guest if has_guest else False
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
                    only_attend_with_guest=lottery_entry.only_attend_with_guest,
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

        Their original claim time puts them ahead of every existing alternate.
        """
        existing = AlternateService.get_waiting_entry(db, show.id, pass_item.staff_id)
        if existing:
            return
        db.add(
            StaffPassAlternate(
                show_id=show.id,
                staff_id=pass_item.staff_id,
                has_guest=pass_item.has_guest,
                guest_name=pass_item.guest_name,
                only_attend_with_guest=pass_item.only_attend_with_guest,
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
    ) -> list[Promotion]:
        """
        Promote waiting alternates into any free staff passes. Does not commit.

        Returns the promotions made so the caller can ``finalize_promotions``
        after committing.
        """
        from app.services.pass_service import PassService

        if show is None:
            return []
        db.flush()
        if AlternateService._promotion_blocked(db, show):
            return []

        waiting = AlternateService.waiting_entries(db, show.id)
        if not waiting:
            return []

        passes = AlternateService._staff_passes(db, show.id)
        by_id = {p.id: p for p in passes}
        now = datetime.now(timezone.utc)
        promotions: list[Promotion] = []

        def take_seat() -> Pass | None:
            available = AlternateService._available(passes)
            if available:
                return available[0]
            holds = AlternateService._guest_holds_newest_first(passes)
            if not holds:
                return None
            hold = holds[0]
            primary = by_id.get(hold.guest_of_pass_id)
            PassService._displace_guest_hold(db, hold, primary, show, now)
            return hold

        def promote(entry: StaffPassAlternate, seat: Pass, guest_pass: Pass | None) -> None:
            PassService._assign_claim(seat, entry.staff_id, now)
            if guest_pass is not None:
                PassService._assign_guest_hold(
                    seat, guest_pass, now, entry.guest_name, entry.only_attend_with_guest
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
            for entry in [e for e in waiting if not e.only_attend_with_guest]:
                seat = take_seat()
                if seat is None:
                    break
                promote(entry, seat, None)
                changed = True
            if any(not e.only_attend_with_guest for e in waiting):
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

        # Step 3: leftover passes go to guests of alternates promoted in step 1.
        for promotion in promotions:
            if not promotion.guest_requested or promotion.guest_granted:
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
                entry.only_attend_with_guest,
            )
            promotion.guest_granted = True

        return promotions

    @staticmethod
    def finalize_promotions(db: Session, promotions: list[Promotion]) -> None:
        """Email and audit promotions after the caller has committed them."""
        from app.services import audit_service

        for promotion in promotions:
            entry = promotion.entry
            try:
                AlternateService._email_promoted(db, promotion)
            except Exception:
                logger.error(
                    "Failed to send alternate promotion email for entry %s",
                    entry.id,
                    exc_info=True,
                )
            audit_service.log_event(
                db,
                event_type="alternate_promoted",
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

    # ── Show lifecycle ──────────────────────────────────────────────────────

    @staticmethod
    def expire_on_close(db: Session, show: Show) -> int:
        """Close out the queue when the show closes and tell each alternate."""
        waiting = AlternateService.waiting_entries(db, show.id)
        if not waiting:
            return 0
        now = datetime.now(timezone.utc)
        for entry in waiting:
            AlternateService._resolve(entry, "expired", now)
        db.commit()
        AlternateService._audit_bulk(db, "alternates_expired", show, waiting)
        for entry in waiting:
            AlternateService._email(
                db,
                entry.staff,
                subject=f"No staff pass available: {show.event_name}",
                lines=[
                    (
                        f"The guest list for {AlternateService._show_desc(show)} has been"
                        " closed."
                    ),
                    "",
                    (
                        "Unfortunately, no staff pass became available while you were on"
                        " the alternate list, so you will not be on the guest list."
                    ),
                    "",
                    "Thank you for your interest!",
                ],
            )
        return len(waiting)

    @staticmethod
    def restore_on_reopen(db: Session, show: Show) -> int:
        """Put entries expired by a close back in line when the show is reopened."""
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
        for entry in sorted(expired, key=_queue_key):
            # Someone may have claimed a pass or rejoined in the meantime.
            if AlternateService._has_claim(
                db, show.id, entry.staff_id
            ) or AlternateService.get_waiting_entry(db, show.id, entry.staff_id):
                continue
            entry.status = "waiting"
            entry.resolved_at = None
            entry.updated_at = now
            db.flush()
            restored.append(entry)
        if not restored:
            return 0

        promotions = AlternateService.fill_open_passes(db, show, trigger="show_reopened")
        db.commit()
        AlternateService._audit_bulk(db, "alternates_restored", show, restored)
        AlternateService.finalize_promotions(db, promotions)

        promoted_ids = {p.entry.id for p in promotions}
        positions = {
            e.id: i for i, e in enumerate(AlternateService.waiting_entries(db, show.id), 1)
        }
        for entry in restored:
            if entry.id in promoted_ids or entry.id not in positions:
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
    def cancel_on_delete(db: Session, show: Show) -> int:
        """Cancel the queue when the show is deleted and tell waiting alternates."""
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
        from app.services import audit_service

        audit_service.log_event(
            db,
            event_type=event_type,
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
        from app.services import notification_service

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
        )

    @staticmethod
    def _email_promoted(db: Session, promotion: Promotion) -> None:
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
            lines.append(f"A guest pass for {guest_label} has also been reserved.")
            lines.append("")
        elif promotion.guest_requested:
            lines.append(
                f"Unfortunately there was no pass left for {guest_label}, so your guest"
                " request has been dropped. You may still attend on your own."
            )
            lines.append("")
        lines.extend([
            "No further action is needed — your name is on the guest list.",
            "",
            (
                "If you can no longer attend, please release your pass so it can go to the"
                " next person:"
            ),
            AlternateService._show_url(show),
        ])
        AlternateService._email(
            db,
            entry.staff,
            subject=f"You got a staff pass to {show.event_name}!",
            lines=lines,
        )
