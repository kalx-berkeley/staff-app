"""Show service for business logic."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import cast, String
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException, status
import logging

from app.models.show import Show
from app.models.show_attempt import ShowAttempt
from app.models.venue import Venue
from app.models.notification_preferences import NotificationPreferences
from app.models.job_log import JobLog
from app.schemas.show import ShowCreate, ShowUpdate
from app.services.pass_service import PassService, format_phone
from app.services import notification_service
from app.config import settings

logger = logging.getLogger(__name__)

_LA = ZoneInfo("America/Los_Angeles")


class ShowService:
    """Service for managing show operations."""

    @staticmethod
    def create_show(db: Session, show_data: ShowCreate) -> Show:
        """
        Create a new show.

        Automatically sets status to "draft".

        Args:
            db: Database session
            show_data: Show creation data

        Returns:
            Created show

        Raises:
            HTTPException: If venue not found or database error
        """
        try:
            # Verify venue exists
            venue = db.query(Venue).filter(Venue.id == show_data.venue_id).first()
            if not venue:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Venue with id {show_data.venue_id} not found",
                )

            show = Show(
                event_name=show_data.event_name,
                genre=show_data.genre,
                venue_id=show_data.venue_id,
                promoter_id=show_data.promoter_id,
                show_date=show_data.show_date,
                show_time=show_data.show_time,
                show_start_date=show_data.show_start_date,
                on_air_description=show_data.on_air_description,
                caller_special_instructions=show_data.caller_special_instructions,
                age_restriction=show_data.age_restriction,
                wheelchair_accessible=show_data.wheelchair_accessible,
                num_pass_pairs=show_data.num_pass_pairs,
                planned_close_date=show_data.planned_close_date,
                planned_close_time=show_data.planned_close_time,
                auto_close=show_data.auto_close,
                co_announce=show_data.co_announce,
                lottery_enabled=show_data.lottery_enabled,
                lottery_window_hours=show_data.lottery_window_hours,
                dj_preassign_prohibition_days=show_data.dj_preassign_prohibition_days,
                status="draft",
            )

            db.add(show)
            db.commit()
            db.refresh(show)

            # Automatically create passes for the show
            PassService.create_passes_for_show(db, show.id, show.num_pass_pairs)

            return show
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error creating show: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create show due to constraint violation",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating show: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while creating show",
            )

    @staticmethod
    def get_show(db: Session, show_id: int) -> Show:
        """
        Get a show by ID.

        Args:
            db: Database session
            show_id: Show ID

        Returns:
            Show

        Raises:
            HTTPException: If show not found or database error
        """
        try:
            show = db.query(Show).filter(Show.id == show_id).first()
            if not show:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Show with id {show_id} not found",
                )
            return show
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while fetching show",
            )

    @staticmethod
    def update_show(db: Session, show_id: int, show_data: ShowUpdate) -> Show:
        """
        Update a show.

        Args:
            db: Database session
            show_id: Show ID
            show_data: Show update data

        Returns:
            Updated show

        Raises:
            HTTPException: If show not found, venue not found, or database error
        """
        try:
            show = ShowService.get_show(db, show_id)

            # Verify venue exists if being updated
            if show_data.venue_id is not None:
                venue = db.query(Venue).filter(Venue.id == show_data.venue_id).first()
                if not venue:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Venue with id {show_data.venue_id} not found",
                    )

            # Update fields if provided
            if show_data.event_name is not None:
                show.event_name = show_data.event_name
            if show_data.genre is not None:
                show.genre = show_data.genre
            if show_data.venue_id is not None:
                show.venue_id = show_data.venue_id
            if "promoter_id" in show_data.model_fields_set:
                show.promoter_id = show_data.promoter_id
            if show_data.show_date is not None:
                show.show_date = show_data.show_date
            # show_time and show_start_date can be explicitly set to null, so use
            # model_fields_set to distinguish "not provided" from "explicitly null"
            if "show_time" in show_data.model_fields_set:
                show.show_time = show_data.show_time
            if "show_start_date" in show_data.model_fields_set:
                show.show_start_date = show_data.show_start_date
            if show_data.on_air_description is not None:
                show.on_air_description = show_data.on_air_description
            if show_data.caller_special_instructions is not None:
                show.caller_special_instructions = show_data.caller_special_instructions
            if show_data.age_restriction is not None:
                show.age_restriction = show_data.age_restriction
            if show_data.wheelchair_accessible is not None:
                show.wheelchair_accessible = show_data.wheelchair_accessible
            if show_data.num_pass_pairs is not None:
                show.num_pass_pairs = show_data.num_pass_pairs
            if "planned_close_date" in show_data.model_fields_set:
                show.planned_close_date = show_data.planned_close_date
            if "planned_close_time" in show_data.model_fields_set:
                show.planned_close_time = show_data.planned_close_time
            if "auto_close" in show_data.model_fields_set:
                show.auto_close = show_data.auto_close
            if "co_announce" in show_data.model_fields_set:
                show.co_announce = show_data.co_announce
            if "lottery_enabled" in show_data.model_fields_set:
                show.lottery_enabled = show_data.lottery_enabled
            if "lottery_window_hours" in show_data.model_fields_set:
                show.lottery_window_hours = show_data.lottery_window_hours
            if "dj_preassign_prohibition_days" in show_data.model_fields_set:
                show.dj_preassign_prohibition_days = show_data.dj_preassign_prohibition_days

            show.updated_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(show)
            return show
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error updating show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update show due to constraint violation",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while updating show",
            )

    @staticmethod
    def list_shows(
        db: Session,
        user_role: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Show]:
        """
        List shows filtered by user role and optional date range.

        Role-based filtering:
        - Draft shows: only visible to promotions staff
        - Published/closed shows: visible to all authenticated users

        Args:
            db: Database session
            user_role: User role ("promotions", "staff", "dj", or None for no filtering)
            date_from: Only return shows on or after this date (filters on show_date)
            date_to: Only return shows on or before this date (filters on show_date)

        Returns:
            List of shows ordered by show date descending, filtered by role

        Raises:
            HTTPException: If database error occurs
        """
        try:
            query = db.query(Show)

            # Apply role-based filtering; deleted shows are always excluded here
            if user_role == "promotions":
                query = query.filter(Show.status != "deleted")
            elif user_role in ["staff", "dj"]:
                query = query.filter(Show.status.in_(["published", "closed"]))

            if date_from is not None:
                query = query.filter(Show.show_date >= date_from)
            if date_to is not None:
                query = query.filter(Show.show_date <= date_to)

            return query.order_by(Show.show_date.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error listing shows: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while listing shows",
            )

    @staticmethod
    def publish_show(db: Session, show_id: int) -> Show:
        """Publish a show (transition from draft to published)."""
        try:
            show = ShowService.get_show(db, show_id)

            if show.status != "draft":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot publish show with status '{show.status}'. Only draft shows"
                        " can be published."
                    ),
                )

            now = datetime.now(timezone.utc)
            show.status = "published"
            show.published_at = now
            show.updated_at = now

            db.commit()
            db.refresh(show)
            return show
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error publishing show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to publish show"
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error publishing show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while publishing show",
            )

    @staticmethod
    def close_show(db: Session, show_id: int) -> Show:
        """Close a show (transition from published to closed)."""
        try:
            show = ShowService.get_show(db, show_id)

            if show.status != "published":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot close show with status '{show.status}'. Only published"
                        " shows can be closed."
                    ),
                )

            show.status = "closed"
            show.updated_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(show)
            return show
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error closing show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to close show"
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error closing show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while closing show",
            )

    @staticmethod
    def unpublish_show(db: Session, show_id: int) -> Show:
        """Unpublish a show (transition from published back to draft)."""
        try:
            show = ShowService.get_show(db, show_id)

            if show.status != "published":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot unpublish show with status '{show.status}'. Only published"
                        " shows can be unpublished."
                    ),
                )

            show.status = "draft"
            show.updated_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(show)
            return show
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error unpublishing show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to unpublish show",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error unpublishing show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while unpublishing show",
            )

    @staticmethod
    def reopen_show(db: Session, show_id: int) -> Show:
        """Reopen a closed show (transition from closed back to published)."""
        try:
            show = ShowService.get_show(db, show_id)

            if show.status != "closed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot reopen show with status '{show.status}'. Only closed"
                        " shows can be reopened."
                    ),
                )

            if show.show_date < datetime.now(_LA).date():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reopen a show whose date has already passed.",
                )

            show.status = "published"
            show.updated_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(show)
            return show
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error reopening show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to reopen show",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error reopening show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while reopening show",
            )

    @staticmethod
    def delete_show(db: Session, show_id: int, actor_email: str) -> None:
        """
        Soft-delete a show by setting its status to "deleted".

        When there are given-away passes, claimed staff passes, or failed attempts,
        sends a cancellation notification to venue owners who have email enabled.
        """
        try:
            show = ShowService.get_show(db, show_id)

            given_away = [
                p for p in show.passes if p.pass_type == "pair" and p.status == "given_away"
            ]
            claimed = [
                p for p in show.passes if p.pass_type == "staff" and p.status == "claimed"
            ]
            attempts = list(show.attempts or [])

            needs_notification = bool(given_away or claimed or attempts)
            if needs_notification:
                ShowService._notify_venue_owners_of_cancellation(
                    db, show, given_away, claimed, attempts, actor_email
                )

            show.status = "deleted"
            show.updated_at = datetime.now(timezone.utc)
            db.commit()
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while deleting show",
            )

    @staticmethod
    def list_deleted_shows(db: Session) -> list[Show]:
        """Return all shows with status 'deleted', ordered by show date descending."""
        try:
            return (
                db.query(Show)
                .filter(Show.status == "deleted")
                .order_by(Show.show_date.desc())
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error listing deleted shows: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while listing deleted shows",
            )

    @staticmethod
    def undelete_show(db: Session, show_id: int) -> Show:
        """Restore a deleted show by setting its status back to 'draft'."""
        try:
            show = ShowService.get_show(db, show_id)

            if show.status != "deleted":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot restore show with status '{show.status}'."
                        " Only deleted shows can be restored."
                    ),
                )

            show.status = "draft"
            show.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(show)
            return show
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error restoring show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while restoring show",
            )

    @staticmethod
    def _notify_venue_owners_of_cancellation(
        db: Session,
        show,
        given_away: list,
        claimed: list,
        attempts: list,
        actor_email: str,
    ) -> None:
        """Send cancellation email to venue owners who have email notifications enabled."""
        lines = [
            (
                f'The show "{show.event_name}" at {show.venue.name} on {show.show_date}'
                f" has been deleted by {actor_email}."
            ),
            "",
        ]

        if given_away:
            lines.append("On-air winners whose passes will no longer be valid:")
            for p in given_away:
                w = p.on_air_winner
                if w:
                    lines.append(
                        f"  - {w.recipient_name} ({format_phone(w.recipient_phone)})"
                        f" — given away by {w.given_away_by_dj}"
                    )
            lines.append("")

        if claimed:
            lines.append("Staff who claimed passes:")
            for p in claimed:
                lines.append(f"  - {p.staff_name} ({format_phone(p.staff_phone)})")
            lines.append("")

        if attempts:
            lines.append(f"Failed on-air giveaway attempts ({len(attempts)}):")
            for a in attempts:
                lines.append(f"  - {a.dj_name} at {a.attempted_at}")
            lines.append("")

        lines.append(
            "Please contact the above individuals to inform them the show has been"
            " cancelled."
        )
        body = "\n".join(lines)
        subject = f"Show cancelled: {show.event_name}"

        effective_promoter = show.effective_promoter
        owners = effective_promoter.owners if effective_promoter else show.venue.owners
        for owner in owners:
            if not owner.staff:
                continue
            prefs = (
                db.query(NotificationPreferences)
                .filter(NotificationPreferences.staff_id == owner.staff.id)
                .first()
            )
            email_enabled = prefs.email_enabled if prefs else True
            if email_enabled:
                notification_service.send_email(
                    to_email=owner.staff.email,
                    subject=subject,
                    body_text=body,
                    db=db,
                )

    @staticmethod
    def _notify_venue_owners_of_pass_reduction(
        db: Session,
        show,
        affected_djs: list[str],
        affected_staff: list[dict],
    ) -> None:
        """Email venue owners when a pass count reduction affects pre-assigned or claimed passes."""
        lines = [
            (
                f'The number of passes for "{show.event_name}" at {show.venue.name}'
                f" on {show.show_date} has been reduced."
            ),
            "",
            "The following people have been affected and will need to be contacted:",
            "",
        ]
        if affected_djs:
            lines.append("DJs whose pre-assigned passes have been removed:")
            for dj in affected_djs:
                lines.append(f"  - {dj}")
            lines.append("")
        if affected_staff:
            lines.append("Staff members who no longer have a claimed pass:")
            for s in affected_staff:
                parts = [s["name"]]
                if s.get("phone"):
                    parts.append(format_phone(s["phone"]))
                if s.get("email"):
                    parts.append(s["email"])
                lines.append(f"  - {', '.join(parts)}")
            lines.append("")
        lines.append("Please contact the affected individuals to let them know.")
        body = "\n".join(lines)
        subject = f"Pass count reduced: {show.event_name}"

        effective_promoter = show.effective_promoter
        owners = effective_promoter.owners if effective_promoter else show.venue.owners
        for owner in owners:
            if not owner.staff:
                continue
            prefs = (
                db.query(NotificationPreferences)
                .filter(NotificationPreferences.staff_id == owner.staff.id)
                .first()
            )
            email_enabled = prefs.email_enabled if prefs else True
            if email_enabled:
                notification_service.send_email(
                    to_email=owner.staff.email,
                    subject=subject,
                    body_text=body,
                    db=db,
                )

    @staticmethod
    def record_attempt(db: Session, show_id: int, dj_name: str) -> ShowAttempt:
        """
        Record a failed giveaway attempt for a show.

        Args:
            db: Database session
            show_id: Show ID
            dj_name: Name of the DJ who attempted the giveaway

        Returns:
            Created ShowAttempt record

        Raises:
            HTTPException: If show not found or show is closed
        """
        show = ShowService.get_show(db, show_id)

        if show.status == "closed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot record attempts for closed shows",
            )

        attempt = ShowAttempt(show_id=show_id, dj_name=dj_name)
        db.add(attempt)
        try:
            db.commit()
            db.refresh(attempt)
            return attempt
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error recording attempt for show {show_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while recording attempt",
            )

    @staticmethod
    def search_shows(
        db: Session,
        user_role: str | None = None,
        freetext: str | None = None,
        venue_id: int | None = None,
        artist: str | None = None,
        genre: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Show]:
        """
        Search shows with freetext and filters, applying role-based visibility.

        Freetext search covers: event name, genre, venue name, special instructions
        Filters: venue, artist (in event name or genre), genre

        Args:
            db: Database session
            user_role: User role ("promotions", "staff", "dj", or None for no filtering)
            freetext: Freetext search term
            venue_id: Filter by venue ID
            artist: Filter by artist (searches in event name and genre)
            genre: Filter by genre

        Returns:
            List of shows matching search criteria, ordered by show date descending

        Raises:
            HTTPException: If database error occurs
        """
        try:
            query = db.query(Show).join(Venue)

            # Apply role-based filtering; deleted shows are always excluded here
            if user_role == "promotions":
                query = query.filter(Show.status != "deleted")
            elif user_role in ["staff", "dj"]:
                query = query.filter(Show.status.in_(["published", "closed"]))

            # Apply freetext search
            if freetext:
                search_term = f"%{freetext}%"
                query = query.filter(
                    (Show.event_name.ilike(search_term))
                    | (cast(Show.genre, String).ilike(search_term))
                    | (Venue.name.ilike(search_term))
                    | (Show.caller_special_instructions.ilike(search_term))
                )

            # Apply venue filter
            if venue_id is not None:
                query = query.filter(Show.venue_id == venue_id)

            # Apply artist filter (searches in event name and genre)
            if artist:
                artist_term = f"%{artist}%"
                query = query.filter(
                    (Show.event_name.ilike(artist_term))
                    | (cast(Show.genre, String).ilike(artist_term))
                )

            # Apply genre filter
            if genre:
                genre_term = f"%{genre}%"
                query = query.filter(cast(Show.genre, String).ilike(genre_term))

            if date_from is not None:
                query = query.filter(Show.show_date >= date_from)
            if date_to is not None:
                query = query.filter(Show.show_date <= date_to)

            return query.order_by(Show.show_date.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error searching shows: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while searching shows",
            )

    @staticmethod
    def _build_guest_list_text(show) -> str:
        """Build plain-text guest list for venue owners, mirroring ShowDetail guest list UI."""
        if show.show_start_date:
            date_str = f"{show.show_start_date} – {show.show_date}"
        elif show.show_time:
            t = show.show_time
            formatted = t.strftime("%I:%M%p").lstrip("0").lower()
            date_str = f"{show.show_date} at {formatted}"
        else:
            date_str = str(show.show_date)

        lines = [f"Here are the pass winners for {show.event_name} on {date_str}:"]

        given_away = [
            p
            for p in show.passes
            if p.pass_type == "pair" and p.status == "given_away" and p.on_air_winner
        ]
        claimed = [
            p for p in show.passes if p.pass_type == "staff" and p.status == "claimed"
        ]

        req_phone = show.venue.requires_phone_number
        req_email = show.venue.requires_email_address

        for p in given_away:
            w = p.on_air_winner
            entry = f"1 pair of passes for {w.recipient_name} and a guest"
            extras = []
            if req_phone:
                extras.append(format_phone(w.recipient_phone))
            if req_email and w.recipient_email:
                extras.append(w.recipient_email)
            if extras:
                entry += f" ({', '.join(extras)})"
            lines.append(entry)
        for p in claimed:
            entry = f"1 pass for {p.staff_name}"
            extras = []
            if req_phone and p.staff_phone:
                extras.append(format_phone(p.staff_phone))
            if req_email and p.staff_email:
                extras.append(p.staff_email)
            if extras:
                entry += f" ({', '.join(extras)})"
            lines.append(entry)

        if not given_away and not claimed:
            lines.append("No passes were given away for this show.")

        failed = list(show.attempts or [])
        if failed:
            lines.append("")
            lines.append("We also announced the show on-air but didn't get any callers:")
            for a in failed:
                lines.append(f"  DJ {a.dj_name} announced the show on {a.attempted_at}")

        return "\n".join(lines)

    @staticmethod
    def _notify_venue_owners_of_auto_close(db: Session, show) -> None:
        """Send guest list email to responsible owners when the show is auto-closed."""
        subject = f"Show auto-closed: {show.event_name} — guest list"
        show_url = f"{settings.frontend_base_url}/pass-giveaway/promotions/shows/{show.id}"
        body = ShowService._build_guest_list_text(show) + f"\n\nView this show: {show_url}"

        effective_promoter = show.effective_promoter
        owners = effective_promoter.owners if effective_promoter else show.venue.owners
        for owner in owners:
            if not owner.staff:
                continue
            prefs = (
                db.query(NotificationPreferences)
                .filter(NotificationPreferences.staff_id == owner.staff.id)
                .first()
            )
            email_enabled = prefs.email_enabled if prefs else True
            if email_enabled:
                notification_service.send_email(
                    to_email=owner.staff.email,
                    subject=subject,
                    body_text=body,
                    db=db,
                )

    @staticmethod
    def notify_unclosed_past_shows(db: Session, trigger: str = "scheduled") -> int:
        """
        Find published shows whose date has elapsed and notify venue owners.

        :param db: Database session.
        :param trigger: "manual" or "scheduled" — recorded in the job log.
        :returns: Number of shows for which notifications were sent.
        """
        today = datetime.now(_LA).date()
        past_published = (
            db.query(Show).filter(Show.status == "published", Show.show_date < today).all()
        )

        notified_count = 0
        for show in past_published:
            subject = f"Open show not yet closed: {show.event_name}"
            body = (
                f'The show "{show.event_name}" at {show.venue.name} was scheduled for'
                f" {show.show_date} but has not been closed in the system.\n\n"
                "Please close this show when you are done with it."
            )
            sent_to_anyone = False
            effective_promoter = show.effective_promoter
            owners = effective_promoter.owners if effective_promoter else show.venue.owners
            for owner in owners:
                if not owner.staff:
                    continue
                prefs = (
                    db.query(NotificationPreferences)
                    .filter(NotificationPreferences.staff_id == owner.staff.id)
                    .first()
                )
                email_enabled = prefs.email_enabled if prefs else True
                if email_enabled:
                    notification_service.send_email(
                        to_email=owner.staff.email,
                        subject=subject,
                        body_text=body,
                        db=db,
                    )
                    sent_to_anyone = True
            if sent_to_anyone:
                notified_count += 1

        db.add(JobLog(job_id="notify_unclosed_past_shows", trigger=trigger))
        db.commit()
        return notified_count
