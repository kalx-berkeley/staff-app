"""Lottery service for managing show pass lotteries."""

import logging
import random
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.lottery_entry import LotteryEntry
from app.models.notification_preferences import NotificationPreferences
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff

logger = logging.getLogger(__name__)


def _utc(dt: datetime) -> datetime:
    """Return dt as UTC-aware, treating naive datetimes as UTC (SQLite stores naively)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class LotteryService:
    """Service for managing lottery entries and drawing results."""

    @staticmethod
    def is_lottery_active(show: Show) -> bool:
        """Return True if the lottery window is currently open for this show."""
        if not show.lottery_enabled or show.published_at is None:
            return False
        deadline = _utc(show.published_at) + timedelta(hours=show.lottery_window_hours)
        return datetime.now(timezone.utc) < deadline

    @staticmethod
    def get_lottery_deadline(show: Show) -> datetime | None:
        """Return the UTC datetime when the lottery closes, or None."""
        if not show.lottery_enabled or show.published_at is None:
            return None
        return _utc(show.published_at) + timedelta(hours=show.lottery_window_hours)

    @staticmethod
    def enter_staff_lottery(
        db: Session,
        show_id: int,
        staff_id: int,
        has_guest: bool = False,
        guest_name: str | None = None,
        only_attend_with_guest: bool = False,
    ) -> LotteryEntry:
        """Create or update a staff member's lottery entry for a show."""
        show = db.query(Show).filter(Show.id == show_id).first()
        if not show:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Show {show_id} not found",
            )
        if show.status != "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Show is not published",
            )
        if not LotteryService.is_lottery_active(show):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The lottery window for this show is not active",
            )

        existing = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show_id,
                LotteryEntry.staff_id == staff_id,
                LotteryEntry.entry_type == "staff",
                LotteryEntry.status == "pending",
            )
            .first()
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.has_guest = has_guest
            existing.guest_name = guest_name
            existing.only_attend_with_guest = only_attend_with_guest
            existing.updated_at = now
            db.commit()
            db.refresh(existing)
            return existing

        entry = LotteryEntry(
            show_id=show_id,
            entry_type="staff",
            staff_id=staff_id,
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

    @staticmethod
    def enter_dj_lottery(
        db: Session,
        show_id: int,
        staff_id: int,
        dj_name: str,
        assignment_date: date,
        specialty_show_id: int | None = None,
    ) -> LotteryEntry:
        """Create or update a DJ's lottery entry for a show."""
        show = db.query(Show).filter(Show.id == show_id).first()
        if not show:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Show {show_id} not found",
            )
        if show.status != "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Show is not published",
            )
        if not LotteryService.is_lottery_active(show):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The lottery window for this show is not active",
            )

        existing = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show_id,
                LotteryEntry.staff_id == staff_id,
                LotteryEntry.entry_type == "dj",
                LotteryEntry.status == "pending",
            )
            .first()
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.dj_name = dj_name
            existing.specialty_show_id = specialty_show_id
            existing.assignment_date = assignment_date
            existing.updated_at = now
            db.commit()
            db.refresh(existing)
            return existing

        entry = LotteryEntry(
            show_id=show_id,
            entry_type="dj",
            staff_id=staff_id,
            dj_name=dj_name,
            specialty_show_id=specialty_show_id,
            assignment_date=assignment_date,
            status="pending",
            entered_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def withdraw_staff_entry(db: Session, show_id: int, staff_id: int) -> None:
        """Remove a pending staff lottery entry."""
        entry = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show_id,
                LotteryEntry.staff_id == staff_id,
                LotteryEntry.entry_type == "staff",
                LotteryEntry.status == "pending",
            )
            .first()
        )
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active staff lottery entry found for this show",
            )
        show = db.query(Show).filter(Show.id == show_id).first()
        if show and not LotteryService.is_lottery_active(show):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The lottery window has closed; entries cannot be withdrawn",
            )
        db.delete(entry)
        db.commit()

    @staticmethod
    def withdraw_dj_entry(db: Session, show_id: int, staff_id: int) -> None:
        """Remove a pending DJ lottery entry."""
        entry = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show_id,
                LotteryEntry.staff_id == staff_id,
                LotteryEntry.entry_type == "dj",
                LotteryEntry.status == "pending",
            )
            .first()
        )
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active DJ lottery entry found for this show",
            )
        show = db.query(Show).filter(Show.id == show_id).first()
        if show and not LotteryService.is_lottery_active(show):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The lottery window has closed; entries cannot be withdrawn",
            )
        db.delete(entry)
        db.commit()

    @staticmethod
    def notify_entries_cancelled(
        db: Session, show: Show, entries: list[LotteryEntry]
    ) -> None:
        """Notify entrants that their lottery entry was cancelled (show unpublished)."""
        from app.services import notification_service

        for entry in entries:
            if not entry.staff or not entry.staff.email:
                continue
            prefs = (
                db.query(NotificationPreferences)
                .filter(NotificationPreferences.staff_id == entry.staff_id)
                .first()
            )
            if prefs and not prefs.email_enabled:
                continue
            body = "\n".join([
                (
                    f'Your lottery entry for "{show.event_name}" at {show.venue.name} on'
                    f" {show.show_date} has been cancelled."
                ),
                "",
                (
                    "The show has been unpublished and all pending lottery entries have"
                    " been removed."
                ),
                "",
                "If the show is republished, you will be able to enter the lottery again.",
            ])
            notification_service.send_email(
                to_email=entry.staff.email,
                subject=f"Lottery entry cancelled — {show.event_name} has been unpublished",
                body_text=body,
                db=db,
            )

    @staticmethod
    def run_lottery(db: Session, show_id: int) -> dict:
        """
        Execute the lottery for a show.

        Randomly assigns available passes to lottery entrants, then sends
        notification emails to all entrants (winners and losers).
        Returns a summary dict.
        """
        show = db.query(Show).filter(Show.id == show_id).first()
        if not show:
            logger.warning(f"Lottery run: show {show_id} not found")
            return {"error": "show not found"}

        if show.status != "published":
            logger.info(f"Lottery run: show {show_id} status is '{show.status}', skipping")
            return {"skipped": True, "status": show.status}

        staff_entries = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show_id,
                LotteryEntry.entry_type == "staff",
                LotteryEntry.status == "pending",
            )
            .all()
        )
        dj_entries = (
            db.query(LotteryEntry)
            .filter(
                LotteryEntry.show_id == show_id,
                LotteryEntry.entry_type == "dj",
                LotteryEntry.status == "pending",
            )
            .all()
        )

        now = datetime.now(timezone.utc)

        staff_summary = LotteryService._run_staff_lottery(db, show, staff_entries, now)
        dj_summary = LotteryService._run_dj_lottery(db, show, dj_entries, now)

        logger.info(
            f"Lottery complete for show {show_id}: staff"
            f" winners={staff_summary['winners']}, staff losers={staff_summary['losers']};"
            f" dj winners={dj_summary['winners']}, dj losers={dj_summary['losers']}"
        )
        return {"staff": staff_summary, "dj": dj_summary}

    @staticmethod
    def _run_staff_lottery(
        db: Session, show: Show, entries: list[LotteryEntry], now: datetime
    ) -> dict:
        """Run the staff pass lottery and claim passes for winners.

        Uses a two-loop algorithm: first award staff passes, then award guest
        passes. If a staff member with only_attend_with_guest cannot get a guest
        pass, their staff pass is returned and both loops repeat until no further
        conversions occur.
        """
        from app.services import notification_service

        if not entries:
            return {"winners": 0, "losers": 0}

        available_passes = (
            db.query(Pass)
            .filter(
                Pass.show_id == show.id,
                Pass.pass_type == "staff",
                Pass.status == "available",
            )
            .all()
        )

        random.shuffle(entries)
        passes = list(available_passes)

        # Keyed by entry.id throughout
        staff_pass: dict[int, Pass] = {}
        guest_pass: dict[int, Pass] = {}
        final_losers: set[int] = set()
        # Entries converted from winner→loser at least once due to only_attend_with_guest
        was_converted: set[int] = set()
        # Entries whose guest-pass fate is already settled (won or accepted loss)
        guest_decided: set[int] = set()

        def staff_loop() -> None:
            for entry in entries:
                if entry.id in staff_pass or entry.id in final_losers:
                    continue
                if passes:
                    staff_pass[entry.id] = passes.pop(0)
                else:
                    final_losers.add(entry.id)

        def guest_loop() -> list[LotteryEntry]:
            converted = []
            for entry in entries:
                if entry.id not in staff_pass:
                    continue
                if not entry.has_guest:
                    continue
                if entry.id in guest_pass or entry.id in guest_decided:
                    continue
                if passes:
                    guest_pass[entry.id] = passes.pop(0)
                    guest_decided.add(entry.id)
                elif entry.only_attend_with_guest:
                    # Return the staff pass and remove from winners.
                    # Two-strike rule: if already converted once, go straight to
                    # final_losers to prevent an infinite cycle when no other
                    # entries can benefit from the freed pass.
                    passes.append(staff_pass.pop(entry.id))
                    if entry.id in was_converted:
                        final_losers.add(entry.id)
                    else:
                        was_converted.add(entry.id)
                        converted.append(entry)
                else:
                    # Staff won their pass; guest simply didn't get one.
                    guest_decided.add(entry.id)
            return converted

        staff_loop()
        converted = guest_loop()
        while converted:
            staff_loop()
            converted = guest_loop()

        # Persist outcomes
        for entry in entries:
            if entry.id in staff_pass:
                primary = staff_pass[entry.id]
                primary.staff_id = entry.staff_id
                primary.claimed_at = now
                primary.status = "claimed"
                primary.has_guest = entry.id in guest_pass
                primary.guest_name = entry.guest_name if entry.id in guest_pass else None
                primary.only_attend_with_guest = (
                    entry.only_attend_with_guest if entry.id in guest_pass else False
                )
                primary.updated_at = now

                if entry.id in guest_pass:
                    gp = guest_pass[entry.id]
                    gp.staff_id = entry.staff_id
                    gp.claimed_at = now
                    gp.status = "claimed"
                    gp.guest_of_pass_id = primary.id
                    gp.updated_at = now

                entry.status = "won"
                entry.updated_at = now
            else:
                entry.status = "lost"
                entry.updated_at = now

        db.commit()

        # Send notification emails — 8 distinct outcome cases
        for entry in entries:
            staff_member = db.query(Staff).filter(Staff.id == entry.staff_id).first()
            if not staff_member or not staff_member.email:
                continue
            prefs = (
                db.query(NotificationPreferences)
                .filter(NotificationPreferences.staff_id == entry.staff_id)
                .first()
            )
            if prefs and not prefs.email_enabled:
                continue

            guest_label = entry.guest_name if entry.guest_name else "your guest"
            show_desc = f'"{show.event_name}" at {show.venue.name} on {show.show_date}'

            if entry.id in staff_pass:
                if entry.id in guest_pass:
                    # Cases 3 & 6: staff won, guest won
                    body = "\n".join([
                        (
                            "Congratulations! You have been selected in the"
                            f" lottery for {show_desc}."
                        ),
                        "",
                        (
                            f"Your staff pass and a guest pass for {guest_label} have both"
                            " been reserved."
                        ),
                        "",
                        (
                            "No further action is needed — both your name and your guest's"
                            " name are on the guest list."
                        ),
                    ])
                    subject = f"You won passes to {show.event_name}!"
                elif entry.has_guest:
                    # Case 4: staff won, guest lost (only_attend_with_guest is False here)
                    body = "\n".join([
                        (
                            "Congratulations! You have been selected in the"
                            f" lottery for {show_desc}."
                        ),
                        "",
                        "Your staff pass has been reserved.",
                        "",
                        (
                            "Unfortunately, there were not enough passes to also reserve a"
                            f" guest pass for {guest_label}."
                        ),
                        (
                            "You may still attend, but your guest will not be on the guest"
                            " list."
                        ),
                        "",
                        "No further action is needed — your name is on the guest list.",
                    ])
                    subject = f"You won a pass to {show.event_name}!"
                else:
                    # Case 1: staff won, no guest requested
                    body = "\n".join([
                        (
                            "Congratulations! You have been selected in the"
                            f" lottery for {show_desc}."
                        ),
                        "",
                        "Your staff pass has been reserved.",
                        "",
                        "No further action is needed — your name is on the guest list.",
                    ])
                    subject = f"You won a pass to {show.event_name}!"
            else:
                if entry.id in was_converted:
                    # Case 7: initially won a staff pass but returned it because no
                    # guest pass was available and only_attend_with_guest is True
                    body = "\n".join([
                        f"The lottery for staff passes to {show_desc} has concluded.",
                        "",
                        (
                            "You were initially selected to receive a staff pass, but"
                            " because no"
                        ),
                        (
                            "guest pass was available and you indicated you can only"
                            f" attend with {guest_label},"
                        ),
                        "your staff pass has been returned to the pool.",
                        "",
                        "Neither you nor your guest will be on the guest list.",
                        "",
                        "Thank you for entering!",
                    ])
                    subject = f"Lottery result for {show.event_name}"
                elif entry.has_guest and entry.only_attend_with_guest:
                    # Case 8: lost from the start, with only_attend_with_guest
                    body = "\n".join([
                        f"The lottery for staff passes to {show_desc} has concluded.",
                        "",
                        (
                            "Unfortunately, there were not enough passes for you to be"
                            " selected."
                        ),
                        f"As you indicated you can only attend with {guest_label},",
                        "neither you nor your guest will be on the guest list.",
                        "",
                        "Thank you for entering!",
                    ])
                    subject = f"Lottery result for {show.event_name}"
                elif entry.has_guest:
                    # Case 5: lost from the start, had a guest request
                    body = "\n".join([
                        f"The lottery for staff passes to {show_desc} has concluded.",
                        "",
                        (
                            "Unfortunately, neither you nor your guest were selected this"
                            " time."
                        ),
                        "",
                        "Thank you for entering!",
                    ])
                    subject = f"Lottery result for {show.event_name}"
                else:
                    # Case 2: lost, no guest requested
                    body = "\n".join([
                        f"The lottery for staff passes to {show_desc} has concluded.",
                        "",
                        "Unfortunately, you were not selected this time.",
                        "",
                        "Thank you for entering!",
                    ])
                    subject = f"Lottery result for {show.event_name}"

            notification_service.send_email(
                to_email=staff_member.email,
                subject=subject,
                body_text=body,
                db=db,
            )

        winners_count = sum(1 for e in entries if e.id in staff_pass)
        return {"winners": winners_count, "losers": len(entries) - winners_count}

    @staticmethod
    def _run_dj_lottery(
        db: Session, show: Show, entries: list[LotteryEntry], now: datetime
    ) -> dict:
        """Run the DJ pass-pair lottery and pre-assign passes to winners."""
        from app.services import notification_service

        if not entries:
            return {"winners": 0, "losers": 0}

        available_passes = (
            db.query(Pass)
            .filter(
                Pass.show_id == show.id,
                Pass.pass_type == "pair",
                Pass.status == "available",
                Pass.preassigned_dj.is_(None),
            )
            .all()
        )

        random.shuffle(entries)
        passes = list(available_passes)
        winners = []
        losers = []

        for entry in entries:
            if passes:
                winners.append((entry, passes.pop(0)))
            else:
                losers.append(entry)

        for entry, pair_pass in winners:
            if entry.specialty_show_id and entry.specialty_show:
                pair_pass.preassigned_dj = entry.specialty_show.name
                pair_pass.preassigned_specialty_show_id = entry.specialty_show_id
            else:
                pair_pass.preassigned_dj = entry.dj_name
                pair_pass.preassigned_specialty_show_id = None
            pair_pass.preassigned_date = entry.assignment_date
            pair_pass.preassigned_by_staff_id = entry.staff_id
            pair_pass.updated_at = now
            entry.status = "won"
            entry.updated_at = now

        for entry in losers:
            entry.status = "lost"
            entry.updated_at = now

        db.commit()

        for entry, _ in winners:
            staff = db.query(Staff).filter(Staff.id == entry.staff_id).first()
            if not staff or not staff.email:
                continue
            prefs = (
                db.query(NotificationPreferences)
                .filter(NotificationPreferences.staff_id == entry.staff_id)
                .first()
            )
            if prefs and not prefs.email_enabled:
                continue
            shift_label = (
                entry.specialty_show.name
                if entry.specialty_show_id and entry.specialty_show
                else entry.dj_name
            )
            body = "\n".join([
                (
                    "Congratulations! Your DJ shift has been selected in the lottery for"
                    f' "{show.event_name}" at {show.venue.name} on {show.show_date}.'
                ),
                "",
                (
                    f"The on-air pass pair for the {shift_label} shift on"
                    f" {entry.assignment_date} has been reserved."
                ),
                "",
                "No further action is needed.",
            ])
            notification_service.send_email(
                to_email=staff.email,
                subject=(
                    f"Your on-air pass pair reservation for {show.event_name} is confirmed"
                ),
                body_text=body,
                db=db,
            )

        for entry in losers:
            staff = db.query(Staff).filter(Staff.id == entry.staff_id).first()
            if not staff or not staff.email:
                continue
            prefs = (
                db.query(NotificationPreferences)
                .filter(NotificationPreferences.staff_id == entry.staff_id)
                .first()
            )
            if prefs and not prefs.email_enabled:
                continue
            body = "\n".join([
                (
                    f'The lottery for on-air pass pairs for "{show.event_name}"'
                    f" at {show.venue.name} on {show.show_date} has concluded."
                ),
                "",
                "Unfortunately, your DJ shift was not selected this time.",
                "",
                "Thank you for entering!",
            ])
            notification_service.send_email(
                to_email=staff.email,
                subject=f"Lottery result for {show.event_name} — DJ passes",
                body_text=body,
                db=db,
            )

        return {"winners": len(winners), "losers": len(losers)}
