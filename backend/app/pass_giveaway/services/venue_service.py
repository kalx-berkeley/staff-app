"""Venue service for business logic."""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException, status
import logging

from app.models.venue import Venue, venue_sort_key
from app.models.venue_owner import VenueOwner
from app.models.venue_contact import VenueContact
from app.auth import current_staff_filter
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.show import Show
from app.pass_giveaway.schemas.venue import VenueCreate, VenueUpdate

logger = logging.getLogger(__name__)


def _resolve_promotions_staff_id(db: Session, email: str) -> int | None:
    """
    Return the Staff.id for a current (Active or 🆕) promotions department
    member with the given email, or None.
    """
    staff = (
        db.query(Staff)
        .join(StaffDepartment, Staff.id == StaffDepartment.staff_id)
        .filter(
            Staff.email == email,
            StaffDepartment.department == "Promotions",
            current_staff_filter(),
        )
        .first()
    )
    return staff.id if staff else None


def _check_win_limit_parent(
    db: Session,
    venue: Venue | None,
    parent_venue_id: int | None,
    win_frequency_days: int | None,
) -> None:
    """
    Refuse an invalid shared win frequency limit.

    A venue can share the limit of one parent venue, one level deep: the parent
    must be a live venue other than this one, with no parent of its own, and a
    venue with children can't become a child. A child has no limit of its own.

    Args:
        db: Database session
        venue: The venue being updated, or None when creating one
        parent_venue_id: The parent the venue will have after the change
        win_frequency_days: The venue's own limit after the change

    Raises:
        HTTPException: 400 explaining which rule the change breaks
    """
    if parent_venue_id is None:
        return
    if win_frequency_days is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A venue that shares another venue's win frequency limit can't have"
                " its own limit"
            ),
        )
    if venue is not None and parent_venue_id == venue.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A venue can't share its own win frequency limit",
        )
    parent = db.query(Venue).filter(Venue.id == parent_venue_id).first()
    if parent is None or parent.deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The venue to share a win frequency limit with wasn't found",
        )
    if parent.parent_venue_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{parent.name} already shares {parent.parent.name}'s win frequency"
                f" limit. Choose {parent.parent.name} instead."
            ),
        )
    if venue is not None and venue.children:
        names = ", ".join(c.name for c in venue.children)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{venue.name} can't share another venue's win frequency limit"
                f" because these venues share its limit: {names}"
            ),
        )


class VenueService:
    """Service for managing venue operations."""

    @staticmethod
    def list_promotions_staff(db: Session) -> list[Staff]:
        """
        List current (Active or 🆕) promotions department staff, ordered by
        name (for owner pickers).
        """
        return (
            db.query(Staff)
            .join(StaffDepartment, Staff.id == StaffDepartment.staff_id)
            .filter(
                StaffDepartment.department == "Promotions",
                current_staff_filter(),
            )
            .order_by(Staff.name)
            .all()
        )

    @staticmethod
    def create_venue(
        db: Session, venue_data: VenueCreate, owner_email: str | None = None
    ) -> Venue:
        try:
            existing_venue = VenueService.get_venue_by_name(db, venue_data.name)
            if existing_venue:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Venue with name '{venue_data.name}' already exists",
                )

            _check_win_limit_parent(
                db, None, venue_data.parent_venue_id, venue_data.win_frequency_days
            )

            venue = Venue(
                name=venue_data.name,
                address=venue_data.address,
                show_sourcing_instructions=venue_data.show_sourcing_instructions,
                pass_call_instructions=venue_data.pass_call_instructions,
                win_frequency_days=venue_data.win_frequency_days,
                parent_venue_id=venue_data.parent_venue_id,
                venue_type=venue_data.venue_type,
                default_wheelchair_accessible=venue_data.default_wheelchair_accessible,
                default_age_restriction=venue_data.default_age_restriction,
                default_movie_rating=venue_data.default_movie_rating,
                default_num_pass_pairs=venue_data.default_num_pass_pairs,
                requires_phone_number=venue_data.requires_phone_number,
                email_address_requirement=venue_data.email_address_requirement,
                staff_guest_requires_name=venue_data.staff_guest_requires_name,
                hold_close_notifications=venue_data.hold_close_notifications,
                default_lottery_enabled=venue_data.default_lottery_enabled,
                default_lottery_window_hours=venue_data.default_lottery_window_hours,
                default_dj_preassign_prohibition_days=venue_data.default_dj_preassign_prohibition_days,
                default_close_hours_before_show=venue_data.default_close_hours_before_show,
                default_on_air_description=venue_data.default_on_air_description,
                default_caller_special_instructions=venue_data.default_caller_special_instructions,
                default_staff_instructions=venue_data.default_staff_instructions,
                promoter_id=venue_data.promoter_id,
                shows_have_external_promoter=venue_data.shows_have_external_promoter,
                show_name_with_logo=venue_data.show_name_with_logo,
            )
            db.add(venue)
            db.flush()  # get venue.id

            # Set owners — use provided list, falling back to the creating user
            emails = venue_data.owner_emails or ([owner_email] if owner_email else [])
            for email in emails:
                promo_id = _resolve_promotions_staff_id(db, email)
                if promo_id:
                    db.add(VenueOwner(venue_id=venue.id, staff_id=promo_id))

            # Add contacts
            for contact in venue_data.contacts:
                db.add(
                    VenueContact(
                        venue_id=venue.id,
                        name=contact.name,
                        title=contact.title,
                        email=contact.email,
                        phone=contact.phone,
                    )
                )

            db.commit()
            db.refresh(venue)
            return venue
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error creating venue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Venue with name '{venue_data.name}' already exists",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating venue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while creating venue",
            )

    @staticmethod
    def get_venue(db: Session, venue_id: int) -> Venue:
        try:
            venue = db.query(Venue).filter(Venue.id == venue_id).first()
            if not venue:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Venue with id {venue_id} not found",
                )
            return venue
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching venue {venue_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while fetching venue",
            )

    @staticmethod
    def update_venue(db: Session, venue_id: int, venue_data: VenueUpdate) -> Venue:
        try:
            venue = VenueService.get_venue(db, venue_id)

            if venue_data.name and venue_data.name != venue.name:
                existing_venue = VenueService.get_venue_by_name(db, venue_data.name)
                if existing_venue:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Venue with name '{venue_data.name}' already exists",
                    )

            fields = venue_data.model_fields_set
            new_parent_id = (
                venue_data.parent_venue_id
                if "parent_venue_id" in fields
                else venue.parent_venue_id
            )
            if "win_frequency_days" in fields:
                new_win_days = venue_data.win_frequency_days
            elif "parent_venue_id" in fields:
                # Choosing a parent clears the venue's own limit
                new_win_days = None
            else:
                new_win_days = venue.win_frequency_days
            _check_win_limit_parent(db, venue, new_parent_id, new_win_days)
            venue.parent_venue_id = new_parent_id
            venue.win_frequency_days = new_win_days

            if venue_data.name is not None:
                venue.name = venue_data.name
            if venue_data.address is not None:
                venue.address = venue_data.address
            if "show_sourcing_instructions" in venue_data.model_fields_set:
                venue.show_sourcing_instructions = venue_data.show_sourcing_instructions
            if "pass_call_instructions" in venue_data.model_fields_set:
                venue.pass_call_instructions = venue_data.pass_call_instructions
            if venue_data.venue_type is not None:
                venue.venue_type = venue_data.venue_type
            if "default_wheelchair_accessible" in venue_data.model_fields_set:
                venue.default_wheelchair_accessible = (
                    venue_data.default_wheelchair_accessible
                )
            if "default_age_restriction" in venue_data.model_fields_set:
                venue.default_age_restriction = venue_data.default_age_restriction
            if "default_movie_rating" in venue_data.model_fields_set:
                venue.default_movie_rating = venue_data.default_movie_rating
            if "default_num_pass_pairs" in venue_data.model_fields_set:
                venue.default_num_pass_pairs = venue_data.default_num_pass_pairs
            if "requires_phone_number" in venue_data.model_fields_set:
                venue.requires_phone_number = venue_data.requires_phone_number
            if venue_data.email_address_requirement is not None:
                venue.email_address_requirement = venue_data.email_address_requirement
            if "staff_guest_requires_name" in venue_data.model_fields_set:
                venue.staff_guest_requires_name = venue_data.staff_guest_requires_name
            if venue_data.hold_close_notifications is not None:
                venue.hold_close_notifications = venue_data.hold_close_notifications
            if "default_lottery_enabled" in venue_data.model_fields_set:
                venue.default_lottery_enabled = venue_data.default_lottery_enabled
            if "default_lottery_window_hours" in venue_data.model_fields_set:
                venue.default_lottery_window_hours = venue_data.default_lottery_window_hours
            if "default_dj_preassign_prohibition_days" in venue_data.model_fields_set:
                venue.default_dj_preassign_prohibition_days = (
                    venue_data.default_dj_preassign_prohibition_days
                )
            if "default_close_hours_before_show" in venue_data.model_fields_set:
                venue.default_close_hours_before_show = (
                    venue_data.default_close_hours_before_show
                )
            if "default_on_air_description" in venue_data.model_fields_set:
                venue.default_on_air_description = venue_data.default_on_air_description
            if "default_caller_special_instructions" in venue_data.model_fields_set:
                venue.default_caller_special_instructions = (
                    venue_data.default_caller_special_instructions
                )
            if "default_staff_instructions" in venue_data.model_fields_set:
                venue.default_staff_instructions = venue_data.default_staff_instructions
            if "promoter_id" in venue_data.model_fields_set:
                venue.promoter_id = venue_data.promoter_id
            if "shows_have_external_promoter" in venue_data.model_fields_set:
                venue.shows_have_external_promoter = venue_data.shows_have_external_promoter
            if venue_data.show_name_with_logo is not None:
                venue.show_name_with_logo = venue_data.show_name_with_logo

            # Replace owners if provided
            if venue_data.owner_emails is not None:
                for owner in venue.owners:
                    db.delete(owner)
                db.flush()
                for email in venue_data.owner_emails:
                    promo_id = _resolve_promotions_staff_id(db, email)
                    if promo_id:
                        db.add(VenueOwner(venue_id=venue.id, staff_id=promo_id))

            # Replace contacts if provided
            if venue_data.contacts is not None:
                for contact in venue.contacts:
                    db.delete(contact)
                db.flush()
                for c in venue_data.contacts:
                    db.add(
                        VenueContact(
                            venue_id=venue.id,
                            name=c.name,
                            title=c.title,
                            email=c.email,
                            phone=c.phone,
                        )
                    )

            venue.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(venue)
            return venue
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error updating venue {venue_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update venue due to constraint violation",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating venue {venue_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while updating venue",
            )

    @staticmethod
    def list_venues(db: Session, owner_staff_id: int | None = None) -> list[Venue]:
        try:
            query = db.query(Venue).filter(Venue.deleted == False)  # noqa: E712
            if owner_staff_id is not None:
                query = query.join(VenueOwner).filter(VenueOwner.staff_id == owner_staff_id)
            return sorted(query.all(), key=lambda v: venue_sort_key(v.name))
        except SQLAlchemyError as e:
            logger.error(f"Database error listing venues: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while listing venues",
            )

    @staticmethod
    def delete_venue(db: Session, venue_id: int) -> Venue | None:
        """
        Soft-delete a venue.

        A venue that other venues share a win frequency limit with can't be
        deleted. A venue that shares another venue's limit is unlinked from it,
        so its past wins stop counting against that venue's limit.

        Args:
            db: Database session
            venue_id: Venue ID

        Returns:
            The venue it was unlinked from, or None
        """
        try:
            venue = VenueService.get_venue(db, venue_id)

            if venue.children:
                names = ", ".join(c.name for c in venue.children)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cannot delete venue: these venues share its win frequency"
                        f" limit and must be changed first: {names}"
                    ),
                )

            blocking_shows = (
                db.query(Show)
                .filter(
                    Show.venue_id == venue_id,
                    Show.status == "published",
                )
                .all()
            )
            if blocking_shows:
                names = ", ".join(f'"{s.event_name}"' for s in blocking_shows)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cannot delete venue: the following published shows must be closed"
                        f" first: {names}"
                    ),
                )

            former_parent = venue.parent
            venue.parent_venue_id = None
            venue.deleted = True
            venue.updated_at = datetime.now(timezone.utc)
            db.commit()
            return former_parent
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting venue {venue_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while deleting venue",
            )

    @staticmethod
    def list_deleted_venues(db: Session) -> list[Venue]:
        try:
            venues = db.query(Venue).filter(Venue.deleted == True).all()  # noqa: E712
            return sorted(venues, key=lambda v: venue_sort_key(v.name))
        except SQLAlchemyError as e:
            logger.error(f"Database error listing deleted venues: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while listing deleted venues",
            )

    @staticmethod
    def undelete_venue(db: Session, venue_id: int) -> Venue:
        try:
            venue = db.query(Venue).filter(Venue.id == venue_id).first()
            if not venue:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Venue with id {venue_id} not found",
                )
            if not venue.deleted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Venue is not deleted",
                )
            venue.deleted = False
            venue.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(venue)
            return venue
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error restoring venue {venue_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while restoring venue",
            )

    @staticmethod
    def get_venue_by_name(db: Session, name: str) -> Venue | None:
        try:
            return db.query(Venue).filter(Venue.name == name).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching venue by name '{name}': {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while fetching venue",
            )
