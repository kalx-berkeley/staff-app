"""Venue service for business logic."""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException, status
import logging

from app.models.venue import Venue
from app.models.venue_owner import VenueOwner
from app.models.venue_contact import VenueContact
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.show import Show
from app.schemas.venue import VenueCreate, VenueUpdate

logger = logging.getLogger(__name__)


def _resolve_promotions_staff_id(db: Session, email: str) -> int | None:
    """Return the Staff.id for a promotions department member with the given email, or None."""
    staff = (
        db.query(Staff)
        .join(StaffDepartment, Staff.id == StaffDepartment.staff_id)
        .filter(Staff.email == email, StaffDepartment.department == "Promotions")
        .first()
    )
    return staff.id if staff else None


class VenueService:
    """Service for managing venue operations."""

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

            venue = Venue(
                name=venue_data.name,
                address=venue_data.address,
                pass_call_instructions=venue_data.pass_call_instructions,
                win_frequency_days=venue_data.win_frequency_days,
                default_wheelchair_accessible=venue_data.default_wheelchair_accessible,
                default_age_restriction=venue_data.default_age_restriction,
                default_num_pass_pairs=venue_data.default_num_pass_pairs,
                requires_phone_number=venue_data.requires_phone_number,
                requires_email_address=venue_data.requires_email_address,
                staff_guest_requires_name=venue_data.staff_guest_requires_name,
                default_lottery_enabled=venue_data.default_lottery_enabled,
                default_lottery_window_hours=venue_data.default_lottery_window_hours,
                default_dj_preassign_prohibition_days=venue_data.default_dj_preassign_prohibition_days,
                default_close_hours_before_show=venue_data.default_close_hours_before_show,
                promoter_id=venue_data.promoter_id,
                shows_have_external_promoter=venue_data.shows_have_external_promoter,
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

            if venue_data.name is not None:
                venue.name = venue_data.name
            if venue_data.address is not None:
                venue.address = venue_data.address
            if venue_data.pass_call_instructions is not None:
                venue.pass_call_instructions = venue_data.pass_call_instructions
            if venue_data.win_frequency_days is not None:
                venue.win_frequency_days = venue_data.win_frequency_days
            if "default_wheelchair_accessible" in venue_data.model_fields_set:
                venue.default_wheelchair_accessible = (
                    venue_data.default_wheelchair_accessible
                )
            if "default_age_restriction" in venue_data.model_fields_set:
                venue.default_age_restriction = venue_data.default_age_restriction
            if "default_num_pass_pairs" in venue_data.model_fields_set:
                venue.default_num_pass_pairs = venue_data.default_num_pass_pairs
            if "requires_phone_number" in venue_data.model_fields_set:
                venue.requires_phone_number = venue_data.requires_phone_number
            if "requires_email_address" in venue_data.model_fields_set:
                venue.requires_email_address = venue_data.requires_email_address
            if "staff_guest_requires_name" in venue_data.model_fields_set:
                venue.staff_guest_requires_name = venue_data.staff_guest_requires_name
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
            if "promoter_id" in venue_data.model_fields_set:
                venue.promoter_id = venue_data.promoter_id
            if "shows_have_external_promoter" in venue_data.model_fields_set:
                venue.shows_have_external_promoter = venue_data.shows_have_external_promoter

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
            query = (
                db.query(Venue).filter(Venue.deleted == False).order_by(Venue.name)
            )  # noqa: E712
            if owner_staff_id is not None:
                query = query.join(VenueOwner).filter(VenueOwner.staff_id == owner_staff_id)
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Database error listing venues: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while listing venues",
            )

    @staticmethod
    def delete_venue(db: Session, venue_id: int) -> None:
        try:
            venue = VenueService.get_venue(db, venue_id)

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

            venue.deleted = True
            venue.updated_at = datetime.now(timezone.utc)
            db.commit()
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
            return (
                db.query(Venue)
                .filter(Venue.deleted == True)  # noqa: E712
                .order_by(Venue.name)
                .all()
            )
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
