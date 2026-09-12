"""Pass service for business logic."""

from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException, status
import logging

from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.on_air_winner import OnAirWinner
from app.models.job_log import JobLog
from app.models.specialty_show import SpecialtyShow
from app.schemas.pass_schema import GiveawayData

import re

logger = logging.getLogger(__name__)

_LA = ZoneInfo("America/Los_Angeles")


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def format_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return phone


class PassService:
    """Service for managing pass_item operations."""

    @staticmethod
    def create_passes_for_show(db: Session, show_id: int, num_pairs: int) -> list[Pass]:
        """
        Create passes for a show.

        Creates N pass pairs and N staff passes based on num_pairs.
        This should be called automatically when a show is created.

        Args:
            db: Database session
            show_id: Show ID
            num_pairs: Number of pass pairs to create

        Returns:
            List of created passes (pairs + staff passes)

        Raises:
            HTTPException: If show not found or database error
        """
        try:
            # Verify show exists
            show = db.query(Show).filter(Show.id == show_id).first()
            if not show:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Show with id {show_id} not found",
                )

            passes = []

            # Create pass pairs
            for _ in range(num_pairs):
                pass_item = Pass(show_id=show_id, pass_type="pair", status="available")
                passes.append(pass_item)
                db.add(pass_item)

            # Create staff passes (one per pair)
            for _ in range(num_pairs):
                pass_item = Pass(show_id=show_id, pass_type="staff", status="available")
                passes.append(pass_item)
                db.add(pass_item)

            db.commit()
            for pass_item in passes:
                db.refresh(pass_item)
            return passes
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error creating passes for show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create passes",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating passes for show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while creating passes",
            )

    @staticmethod
    def give_away_pass_pair(db: Session, pass_id: int, giveaway_data: GiveawayData) -> Pass:
        """
        Give away a pass pair.

        Records winner information and marks the pass_item as given_away.

        Args:
            db: Database session
            pass_id: Pass ID
            giveaway_data: Giveaway data with recipient and DJ info

        Returns:
            Updated pass_item

        Raises:
            HTTPException: If pass_item not found, not a pair, already given away, or database error
        """
        try:
            pass_item = db.query(Pass).filter(Pass.id == pass_id).first()
            if not pass_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Pass with id {pass_id} not found",
                )

            # Validate pass_item type
            if pass_item.pass_type != "pair":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only pass pairs can be given away on-air",
                )

            # Validate pass_item is available
            if pass_item.status != "available":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pass is not available (current status: {pass_item.status})",
                )

            # Validate show is not closed
            show = db.query(Show).filter(Show.id == pass_item.show_id).first()
            if show and show.status == "closed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot give away passes for closed shows",
                )
            if show and show.planned_close_date and show.planned_close_time:
                planned_dt = datetime.combine(
                    show.planned_close_date, show.planned_close_time, tzinfo=_LA
                )
                if datetime.now(_LA) >= planned_dt:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "Cannot give away passes: the planned close time for this show"
                            " has passed"
                        ),
                    )

            # Enforce one giveaway per DJ per show within a 4-hour shift window
            four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=4)
            recent_dj_giveaway = (
                db.query(OnAirWinner)
                .filter(
                    OnAirWinner.show_id == pass_item.show_id,
                    OnAirWinner.given_away_by_dj == giveaway_data.given_away_by_dj,
                    OnAirWinner.created_at >= four_hours_ago,
                )
                .first()
            )
            if recent_dj_giveaway:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"DJ '{giveaway_data.given_away_by_dj}' has already given away"
                        " a pair of passes for this show within the last 4 hours"
                    ),
                )

            # Record giveaway on the pass
            pass_item.given_away_by_dj = giveaway_data.given_away_by_dj
            pass_item.given_away_at = datetime.now(timezone.utc)
            pass_item.status = "given_away"
            pass_item.updated_at = datetime.now(timezone.utc)

            # Create on_air_winner record with winner identity and venue/show context
            winner = OnAirWinner(
                pass_id=pass_item.id,
                venue_id=show.venue_id,
                show_id=show.id,
                recipient_name=giveaway_data.recipient_name,
                recipient_phone=normalize_phone(giveaway_data.recipient_phone),
                recipient_email=giveaway_data.recipient_email,
                given_away_by_dj=giveaway_data.given_away_by_dj,
            )
            db.add(winner)

            db.commit()
            db.refresh(pass_item)
            return pass_item
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error giving away pass_item {pass_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to record giveaway",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error giving away pass_item {pass_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while recording giveaway",
            )

    @staticmethod
    def get_dj_history(db: Session, dj_name: str) -> list[Pass]:
        """
        Get all passes given away by or pre-assigned to a specific DJ.

        Returns given_away passes where DJ is the giver, plus available passes
        that are currently pre-assigned to this DJ.

        Args:
            db: Database session
            dj_name: DJ name to filter by

        Returns:
            List of passes given away by or pre-assigned to the DJ
        """
        from sqlalchemy import or_

        return (
            db.query(Pass)
            .filter(
                or_(
                    (Pass.given_away_by_dj == dj_name) & (Pass.status == "given_away"),
                    (Pass.preassigned_dj == dj_name) & (Pass.status == "available"),
                )
            )
            .all()
        )

    @staticmethod
    def release_on_air_winner(
        db: Session,
        pass_item: Pass,
        reason: str,
        actor_name: str,
        actor_email: str,
        show,
    ) -> Pass:
        """
        Release an on-air winner from a pass, making it available again.

        Deletes the OnAirWinner record and resets the pass to available status.
        Logs an audit event.

        Args:
            db: Database session
            pass_item: The pass to release
            reason: Reason for releasing the winner
            actor_name: Name of the person performing the release
            actor_email: Email of the person performing the release
            show: The show the pass belongs to

        Returns:
            Updated pass
        """
        from app.services import audit_service

        winner = pass_item.on_air_winner
        winner_name = winner.recipient_name
        winner_phone = winner.recipient_phone

        db.delete(winner)

        pass_item.status = "available"
        pass_item.given_away_by_dj = None
        pass_item.given_away_at = None
        pass_item.updated_at = datetime.now(timezone.utc)

        db.commit()

        audit_service.log_event(
            db,
            event_type="winner_released",
            actor_email=actor_email,
            actor_role="dj",
            entity_type="pass",
            entity_id=pass_item.id,
            details={
                "reason": reason,
                "actor_name": actor_name,
                "winner_name": winner_name,
                "winner_phone": winner_phone,
                "show_id": show.id if show else None,
            },
        )
        return pass_item

    @staticmethod
    def release_claim(db: Session, pass_id: int) -> Pass:
        """
        Release a claimed staff pass, making it available again.

        Validates the pass is claimed and the show is not closed.

        Args:
            db: Database session
            pass_id: Pass ID

        Returns:
            Updated pass

        Raises:
            HTTPException: If pass not found, not claimed, or show is closed
        """
        pass_item = db.query(Pass).filter(Pass.id == pass_id).first()
        if not pass_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pass with id {pass_id} not found",
            )

        if pass_item.status != "claimed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pass is not claimed (current status: {pass_item.status})",
            )

        show = db.query(Show).filter(Show.id == pass_item.show_id).first()
        if show and show.status == "closed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot release passes for closed shows",
            )

        now = datetime.now(timezone.utc)
        pass_item.status = "available"
        pass_item.staff_id = None
        pass_item.claimed_at = None
        pass_item.has_guest = False
        pass_item.guest_name = None
        pass_item.only_attend_with_guest = False
        pass_item.updated_at = now

        # Release any guest hold that was linked to this pass.
        guest_hold = db.query(Pass).filter(Pass.guest_of_pass_id == pass_item.id).first()
        if guest_hold:
            guest_hold.status = "available"
            guest_hold.staff_id = None
            guest_hold.claimed_at = None
            guest_hold.guest_of_pass_id = None
            guest_hold.updated_at = now

        try:
            db.commit()
            db.refresh(pass_item)
            return pass_item
        except Exception as e:
            db.rollback()
            logger.error(f"Error releasing claim for pass {pass_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while releasing pass",
            )

    @staticmethod
    def get_dj_names_for_autocomplete(db: Session) -> list[str]:
        """
        Get DJ names for autocomplete.

        Returns the union of:
        - DJ names from the staff table (sourced from Airtable)
        - Distinct names of DJs who have given away passes (on_air_winners)

        Args:
            db: Database session

        Returns:
            Sorted, deduplicated list of DJ names
        """
        staff_names = {
            name.strip()
            for r in db.query(Staff.dj_name).filter(Staff.dj_name.isnot(None)).all()
            for name in r[0].split(",")
            if name.strip()
        }
        winner_names = {
            r[0] for r in db.query(OnAirWinner.given_away_by_dj).distinct().all()
        }
        specialty_names = {
            r[0]
            for r in (
                db.query(SpecialtyShow.name)
                .filter(SpecialtyShow.deleted == False)  # noqa: E712
                .all()
            )
        }
        return sorted(staff_names | winner_names | specialty_names)

    @staticmethod
    def suggest_djs_by_genre(db: Session, show: Show) -> list[dict]:
        """
        Suggest active Sublist DJs (and specialty shows they belong to) whose genre
        preferences overlap *show*'s genres, for the "Suggest DJs by genre" pre-assignment
        flow.

        A DJ's `Staff.dj_name` can be a comma-joined list of stage names (same
        convention as `get_dj_names_for_autocomplete`/self pre-assignment); each
        name is suggested individually. A specialty show is suggested once, with
        the union of its member DJs' matched genres, when at least one member has
        a genre match.

        :param db: Database session.
        :param show: Show to match genres against.
        :returns: List of dicts shaped like `DjSuggestion`, sorted by name.
        """
        from app.auth import _is_sublist_dj
        from app.models.staff_genre_preference import StaffGenrePreference
        from app.models.specialty_show_dj import (
            SpecialtyShowDJ,
        )  # noqa: F401 (via SpecialtyShow.dj_names)

        show_genres = {g.lower() for g in show.genre or []}
        if not show_genres:
            return []

        rows = (
            db.query(Staff, StaffGenrePreference)
            .join(StaffGenrePreference, StaffGenrePreference.staff_id == Staff.id)
            .filter(Staff.dj_name.isnot(None))
            .all()
        )

        # Lowercase individual DJ name -> (display name, matched genres).
        dj_matches: dict[str, tuple[str, set[str]]] = {}
        for staff, prefs in rows:
            if not _is_sublist_dj(staff):
                continue
            matched = {g.lower() for g in prefs.genres or []} & show_genres
            if not matched:
                continue
            for name in staff.dj_name.split(","):
                name = name.strip()
                if not name:
                    continue
                key = name.lower()
                if key in dj_matches:
                    dj_matches[key][1].update(matched)
                else:
                    dj_matches[key] = (name, set(matched))

        suggestions = [
            {"name": name, "is_specialty": False, "matched_genres": sorted(genres)}
            for name, genres in dj_matches.values()
        ]

        specialty_shows = (
            db.query(SpecialtyShow)
            .filter(SpecialtyShow.deleted == False)
            .all()  # noqa: E712
        )
        for specialty_show in specialty_shows:
            matched_genres: set[str] = set()
            for member_name in specialty_show.dj_names:
                entry = dj_matches.get(member_name.strip().lower())
                if entry:
                    matched_genres.update(entry[1])
            if matched_genres:
                suggestions.append({
                    "name": specialty_show.name,
                    "is_specialty": True,
                    "matched_genres": sorted(matched_genres),
                })

        suggestions.sort(key=lambda s: s["name"].lower())
        return suggestions

    @staticmethod
    def _validate_staff_pass_claimable(db: Session, pass_item: Pass) -> Show:
        """Shared validation for claiming a staff pass. Returns the show."""
        if pass_item.pass_type != "staff":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only staff passes can be claimed by staff members",
            )

        show = db.query(Show).filter(Show.id == pass_item.show_id).first()
        if show and show.status == "closed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot claim passes for closed shows",
            )
        if show and show.planned_close_date and show.planned_close_time:
            planned_dt = datetime.combine(
                show.planned_close_date, show.planned_close_time, tzinfo=_LA
            )
            if datetime.now(_LA) >= planned_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Cannot claim passes: the planned close time for this show has"
                        " passed"
                    ),
                )
        return show

    @staticmethod
    def _notify_guest_bumped(
        db: Session,
        primary_pass: Pass,
        show: Show,
        released: bool,
    ) -> None:
        """Send an email to a staff member whose guest was bumped by another staff claim."""
        from app.services import notification_service

        if not primary_pass.staff or not primary_pass.staff.email:
            return

        guest_name = primary_pass.guest_name

        if released:
            if guest_name:
                reason_line = (
                    f"Because you indicated you only wanted to attend if {guest_name}"
                    " could also attend, your staff pass has been released."
                )
            else:
                reason_line = (
                    "Because you indicated you only wanted to attend if your guest"
                    " could also attend, your staff pass has been released."
                )
            body = "\n".join([
                f"Unfortunately, another staff member has claimed a pass for"
                f' "{show.event_name}" at {show.venue.name} on {show.show_date}.',
                "",
                reason_line,
                "",
                "Your pass is now available for another staff member to claim.",
            ])
            subject = f"Your staff pass has been released: {show.event_name}"
        else:
            if guest_name:
                guest_line = (
                    f"There are no longer enough staff passes for {guest_name}"
                    " to attend as your guest."
                )
            else:
                guest_line = (
                    "There are no longer enough staff passes for your guest to attend."
                )
            body = "\n".join([
                f"Unfortunately, another staff member has claimed a pass for"
                f' "{show.event_name}" at {show.venue.name} on {show.show_date}.',
                "",
                guest_line,
                "",
                "You still have your own staff pass and are on the guest list.",
            ])
            subject = f"Your guest pass is no longer available: {show.event_name}"

        notification_service.send_email(
            to_email=primary_pass.staff.email,
            subject=subject,
            body_text=body,
            db=db,
        )

    @staticmethod
    def claim_staff_pass(
        db: Session,
        pass_id: int,
        staff_id: int | None,
        has_guest: bool = False,
        guest_name: str | None = None,
        only_attend_with_guest: bool = False,
    ) -> Pass:
        """
        Claim a staff pass, optionally reserving a second pass for a +1 guest.

        When ``has_guest=True``, a second available staff pass for the same show
        is atomically claimed as a guest hold (``guest_of_pass_id`` pointing back
        to the primary pass).  If the target pass is itself a guest hold, the
        existing guest reservation is displaced and the original staff member is
        notified.

        Args:
            db: Database session
            pass_id: Pass ID to claim
            staff_id: Staff member ID (may be None for promotions staff)
            has_guest: Whether to also reserve a guest hold pass
            guest_name: Optional guest name for the reservation
            only_attend_with_guest: Release this pass too if the guest loses their slot

        Returns:
            Updated primary pass

        Raises:
            HTTPException: If pass not found, not a staff pass, show closed, or
                           not enough passes available for a guest hold
        """
        try:
            pass_item = db.query(Pass).filter(Pass.id == pass_id).first()
            if not pass_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Pass with id {pass_id} not found",
                )

            show = PassService._validate_staff_pass_claimable(db, pass_item)

            if staff_id is not None:
                staff = db.query(Staff).filter(Staff.id == staff_id).first()
                if not staff:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Staff member with id {staff_id} not found",
                    )

            # Determine if the target pass is available or a guest hold (overridable).
            is_guest_hold = (
                pass_item.status == "claimed" and pass_item.guest_of_pass_id is not None
            )

            if not is_guest_hold and pass_item.status != "available":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pass is not available (current status: {pass_item.status})",
                )

            now = datetime.now(timezone.utc)

            if is_guest_hold:
                # Displace the existing guest reservation.
                primary_pass = (
                    db.query(Pass).filter(Pass.id == pass_item.guest_of_pass_id).first()
                )
                if primary_pass:
                    released = primary_pass.only_attend_with_guest
                    # Notify before clearing staff_id so the staff relationship
                    # is still intact when the email address is looked up.
                    PassService._notify_guest_bumped(db, primary_pass, show, released)

                    primary_pass.has_guest = False
                    primary_pass.guest_name = None
                    primary_pass.only_attend_with_guest = False
                    primary_pass.updated_at = now

                    if released:
                        primary_pass.status = "available"
                        primary_pass.staff_id = None
                        primary_pass.claimed_at = None

                pass_item.guest_of_pass_id = None

            # Claim the primary pass for the staff member.
            pass_item.staff_id = staff_id
            pass_item.claimed_at = now
            pass_item.status = "claimed"
            pass_item.has_guest = has_guest and not is_guest_hold
            pass_item.guest_name = None
            pass_item.only_attend_with_guest = False
            pass_item.updated_at = now

            if has_guest and not is_guest_hold:
                # Find a second available staff pass on the same show.
                guest_pass = (
                    db.query(Pass)
                    .filter(
                        Pass.show_id == pass_item.show_id,
                        Pass.pass_type == "staff",
                        Pass.status == "available",
                        Pass.id != pass_item.id,
                    )
                    .first()
                )
                if not guest_pass:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Not enough available staff passes to reserve a guest hold",
                    )
                pass_item.guest_name = guest_name
                pass_item.only_attend_with_guest = only_attend_with_guest
                guest_pass.staff_id = staff_id
                guest_pass.claimed_at = now
                guest_pass.status = "claimed"
                guest_pass.guest_of_pass_id = pass_item.id
                guest_pass.updated_at = now

            db.commit()
            db.refresh(pass_item)
            return pass_item
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error claiming pass_item {pass_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to claim pass_item",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error claiming pass_item {pass_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while claiming pass_item",
            )

    @staticmethod
    def set_preassignment(
        db: Session,
        pass_id: int,
        dj_name: str,
        assignment_date: date,
        preassigned_by_staff_id: int | None = None,
        preassigned_specialty_show_id: int | None = None,
    ) -> Pass:
        """
        Set pre-assignment for a pass pair.

        Records the assigned DJ and date for a pass pair.
        Only pass pairs can be pre-assigned.

        Args:
            db: Database session
            pass_id: Pass ID
            dj_name: DJ name to assign
            assignment_date: Date for the assignment

        Returns:
            Updated pass_item

        Raises:
            HTTPException: If pass_item not found, not a pair, or already given away
        """
        pass_item = db.query(Pass).filter(Pass.id == pass_id).first()
        if not pass_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pass with id {pass_id} not found",
            )

        # Validate pass_item type
        if pass_item.pass_type != "pair":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pass pairs can be pre-assigned",
            )

        # Validate pass_item is available
        if pass_item.status != "available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot pre-assign pass_item that is not available (current status:"
                    f" {pass_item.status})"
                ),
            )

        show = db.query(Show).filter(Show.id == pass_item.show_id).first()
        if show and show.planned_close_date and assignment_date > show.planned_close_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot pre-assign pass: the assignment date is after the planned close"
                    " date for this show"
                ),
            )

        # Set pre-assignment
        pass_item.preassigned_dj = dj_name
        pass_item.preassigned_date = assignment_date
        pass_item.preassigned_by_staff_id = preassigned_by_staff_id
        pass_item.preassigned_specialty_show_id = preassigned_specialty_show_id
        pass_item.updated_at = datetime.now(timezone.utc)

        try:
            db.commit()
            db.refresh(pass_item)
            return pass_item
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to set pre-assignment",
            )

    @staticmethod
    def remove_preassignment(db: Session, pass_id: int) -> Pass:
        """
        Remove pre-assignment from a pass pair.

        Clears the preassigned DJ and date fields.

        Args:
            db: Database session
            pass_id: Pass ID

        Returns:
            Updated pass_item

        Raises:
            HTTPException: If pass_item not found or not a pair
        """
        pass_item = db.query(Pass).filter(Pass.id == pass_id).first()
        if not pass_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pass with id {pass_id} not found",
            )

        # Validate pass_item type
        if pass_item.pass_type != "pair":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pass pairs can have pre-assignments removed",
            )

        # Clear pre-assignment
        pass_item.preassigned_dj = None
        pass_item.preassigned_date = None
        pass_item.preassigned_by_staff_id = None
        pass_item.preassigned_specialty_show_id = None
        pass_item.updated_at = datetime.now(timezone.utc)

        try:
            db.commit()
            db.refresh(pass_item)
            return pass_item
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove pre-assignment",
            )

    @staticmethod
    def expire_stale_preassignments(
        db: Session, trigger: str = "scheduled", _today: date | None = None
    ) -> list[Pass]:
        """
        Clear DJ pre-assignments for passes whose assigned date has elapsed.

        Finds pass pairs on published shows that still have a preassigned DJ
        but whose preassigned date is in the past and haven't been given away.
        Clears the preassigned_dj and preassigned_date fields so any DJ can
        give them away on-air.

        :param db: Database session
        :param trigger: "manual" or "scheduled"
        :param _today: Override today's date (for testing)
        :returns: List of passes that were updated
        """
        from app.services.audit_service import log_event

        today = _today if _today is not None else datetime.now(_LA).date()
        stale_passes = (
            db.query(Pass)
            .join(Show, Pass.show_id == Show.id)
            .filter(
                Pass.pass_type == "pair",
                Pass.status == "available",
                Pass.preassigned_dj.isnot(None),
                Pass.preassigned_date < today,
                Show.status == "published",
            )
            .all()
        )

        # Snapshot before-state so we can audit after the commit clears the fields.
        expired_info = [
            (p.id, p.preassigned_dj, str(p.preassigned_date), p.show_id)
            for p in stale_passes
        ]

        for pass_item in stale_passes:
            logger.info(
                f"Expiring stale preassignment: pass {pass_item.id}, "
                f"DJ '{pass_item.preassigned_dj}', date {pass_item.preassigned_date}"
            )
            pass_item.preassigned_dj = None
            pass_item.preassigned_date = None
            pass_item.preassigned_by_staff_id = None
            pass_item.preassigned_specialty_show_id = None
            pass_item.updated_at = datetime.now(timezone.utc)

        try:
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error expiring stale preassignments: {str(e)}")
            raise

        for pass_id, dj, assignment_date, show_id in expired_info:
            log_event(
                db,
                event_type="preassignment_expired",
                actor_role="system",
                entity_type="pass",
                entity_id=pass_id,
                details={
                    "dj": dj,
                    "assignment_date": assignment_date,
                    "show_id": show_id,
                },
            )

        try:
            db.add(JobLog(job_id="expire_stale_dj_preassignments", trigger=trigger))
            db.commit()
        except Exception:
            db.rollback()

        return stale_passes

    @staticmethod
    def adjust_passes_for_show(db: Session, show, new_num_pairs: int) -> dict:
        """
        Adjust the physical pass records to match a new num_pass_pairs value.

        Returns a dict with:
          - affected_djs: list of DJ names whose preassignment was removed
          - affected_staff: list of dicts with name/phone/email of staff who lost a pass
        """
        import random

        pair_passes = [p for p in show.passes if p.pass_type == "pair"]
        staff_passes = [p for p in show.passes if p.pass_type == "staff"]
        now = datetime.now(timezone.utc)
        affected_djs: list[str] = []
        affected_staff: list[dict] = []

        # --- pair passes ---
        pair_delta = new_num_pairs - len(pair_passes)
        if pair_delta > 0:
            for _ in range(pair_delta):
                db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
        elif pair_delta < 0:
            to_remove = -pair_delta
            given_away = [p for p in pair_passes if p.status == "given_away"]
            preassigned = [
                p for p in pair_passes if p.status == "available" and p.preassigned_dj
            ]
            free = [
                p for p in pair_passes if p.status == "available" and not p.preassigned_dj
            ]

            to_delete = []
            random.shuffle(free)
            for p in free:
                if to_remove <= 0:
                    break
                to_delete.append(p)
                to_remove -= 1

            if to_remove > 0:
                random.shuffle(preassigned)
                for p in preassigned:
                    if to_remove <= 0:
                        break
                    affected_djs.append(p.preassigned_dj)
                    to_delete.append(p)
                    to_remove -= 1

            # given_away passes are committed to callers; never delete them
            _ = given_away

            for p in to_delete:
                db.delete(p)

        # --- staff passes ---
        staff_delta = new_num_pairs - len(staff_passes)
        if staff_delta > 0:
            for _ in range(staff_delta):
                db.add(Pass(show_id=show.id, pass_type="staff", status="available"))
        elif staff_delta < 0:
            to_remove = -staff_delta

            available_s = [p for p in staff_passes if p.status == "available"]
            guest_holds = [
                p
                for p in staff_passes
                if p.status == "claimed" and p.guest_of_pass_id is not None
            ]
            primaries = [
                p
                for p in staff_passes
                if p.status == "claimed" and p.guest_of_pass_id is None
            ]
            to_delete_ids: set[int] = set()

            # Step 1: available unclaimed
            random.shuffle(available_s)
            for p in available_s:
                if to_remove <= 0:
                    break
                to_delete_ids.add(p.id)
                to_remove -= 1

            # Step 2: guest holds (least impact)
            random.shuffle(guest_holds)
            for gh in guest_holds:
                if to_remove <= 0:
                    break
                primary = next((p for p in primaries if p.id == gh.guest_of_pass_id), None)
                if primary:
                    if primary.only_attend_with_guest:
                        affected_staff.append({
                            "name": primary.staff.name if primary.staff else "Unknown",
                            "phone": primary.staff.phone if primary.staff else None,
                            "email": primary.staff.email if primary.staff else None,
                        })
                        primary.status = "available"
                        primary.staff_id = None
                        primary.claimed_at = None
                        primary.has_guest = False
                        primary.guest_name = None
                        primary.only_attend_with_guest = False
                        primary.updated_at = now
                        primaries.remove(primary)
                        # Delete the released primary too if we still need to shrink
                        if to_remove > 1:
                            to_delete_ids.add(primary.id)
                            to_remove -= 1
                    else:
                        primary.has_guest = False
                        primary.guest_name = None
                        primary.only_attend_with_guest = False
                        primary.updated_at = now

                gh.guest_of_pass_id = None
                to_delete_ids.add(gh.id)
                to_remove -= 1

            # Step 3: primary claimed passes
            random.shuffle(primaries)
            for p in primaries:
                if to_remove <= 0:
                    break
                if p.id in to_delete_ids:
                    continue
                affected_staff.append({
                    "name": p.staff.name if p.staff else "Unknown",
                    "phone": p.staff.phone if p.staff else None,
                    "email": p.staff.email if p.staff else None,
                })
                # Also delete any guest hold still linked to this primary
                linked_gh = next(
                    (
                        g
                        for g in guest_holds
                        if g.guest_of_pass_id == p.id and g.id not in to_delete_ids
                    ),
                    None,
                )
                if linked_gh:
                    to_delete_ids.add(linked_gh.id)
                    to_remove -= 1
                to_delete_ids.add(p.id)
                to_remove -= 1

            for p in staff_passes:
                if p.id in to_delete_ids:
                    db.delete(p)

        db.commit()
        db.refresh(show)
        return {"affected_djs": affected_djs, "affected_staff": affected_staff}

    @staticmethod
    def get_passes_for_show(
        db: Session,
        show_id: int,
        dj_name: str | None = None,
        current_date: date | None = None,
    ) -> list[Pass]:
        """
        Get passes for a show, optionally filtered by preassigned DJ.

        When dj_name and current_date are provided, returns:
        - Passes pre-assigned to that DJ for that date
        - Passes with no pre-assignment
        - Passes pre-assigned to that DJ for past dates (assignment expired)

        Args:
            db: Database session
            show_id: Show ID
            dj_name: Optional DJ name to filter by
            current_date: Optional current date for filtering expired assignments

        Returns:
            List of passes
        """
        query = db.query(Pass).filter(Pass.show_id == show_id)

        if dj_name and current_date:
            # Filter to show passes available to this DJ on this date
            query = query.filter(
                # Either not pre-assigned
                (Pass.preassigned_dj.is_(None))
                |
                # Or pre-assigned to this DJ for today
                ((Pass.preassigned_dj == dj_name) & (Pass.preassigned_date == current_date))
                |
                # Or pre-assigned to this DJ for a past date (expired)
                ((Pass.preassigned_dj == dj_name) & (Pass.preassigned_date < current_date))
            )

        return query.all()
