"""Promoter service for business logic."""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException, status
import logging

from app.models.promoter import Promoter
from app.models.promoter_owner import PromoterOwner
from app.models.promoter_contact import PromoterContact
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.schemas.promoter import PromoterCreate, PromoterUpdate

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


class PromoterService:
    """Service for managing promoter operations."""

    @staticmethod
    def create_promoter(
        db: Session, promoter_data: PromoterCreate, owner_email: str | None = None
    ) -> Promoter:
        try:
            existing = (
                db.query(Promoter).filter(Promoter.name == promoter_data.name).first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Promoter with name '{promoter_data.name}' already exists",
                )

            promoter = Promoter(
                name=promoter_data.name,
                pass_call_instructions=promoter_data.pass_call_instructions,
                requires_phone_number=promoter_data.requires_phone_number,
                requires_email_address=promoter_data.requires_email_address,
                staff_guest_requires_name=promoter_data.staff_guest_requires_name,
            )
            db.add(promoter)
            db.flush()

            emails = promoter_data.owner_emails or ([owner_email] if owner_email else [])
            for email in emails:
                promo_id = _resolve_promotions_staff_id(db, email)
                if promo_id:
                    db.add(PromoterOwner(promoter_id=promoter.id, staff_id=promo_id))

            for contact in promoter_data.contacts:
                db.add(
                    PromoterContact(
                        promoter_id=promoter.id,
                        name=contact.name,
                        title=contact.title,
                        email=contact.email,
                        phone=contact.phone,
                    )
                )

            db.commit()
            db.refresh(promoter)
            return promoter
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error creating promoter: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Promoter with name '{promoter_data.name}' already exists",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating promoter: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while creating promoter",
            )

    @staticmethod
    def get_promoter(db: Session, promoter_id: int) -> Promoter:
        try:
            promoter = db.query(Promoter).filter(Promoter.id == promoter_id).first()
            if not promoter:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Promoter with id {promoter_id} not found",
                )
            return promoter
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching promoter {promoter_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while fetching promoter",
            )

    @staticmethod
    def update_promoter(
        db: Session, promoter_id: int, promoter_data: PromoterUpdate
    ) -> Promoter:
        try:
            promoter = PromoterService.get_promoter(db, promoter_id)

            if promoter_data.name and promoter_data.name != promoter.name:
                existing = (
                    db.query(Promoter).filter(Promoter.name == promoter_data.name).first()
                )
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Promoter with name '{promoter_data.name}' already exists",
                    )

            if promoter_data.name is not None:
                promoter.name = promoter_data.name

            if promoter_data.pass_call_instructions is not None:
                promoter.pass_call_instructions = promoter_data.pass_call_instructions
            if promoter_data.requires_phone_number is not None:
                promoter.requires_phone_number = promoter_data.requires_phone_number
            if promoter_data.requires_email_address is not None:
                promoter.requires_email_address = promoter_data.requires_email_address
            if promoter_data.staff_guest_requires_name is not None:
                promoter.staff_guest_requires_name = promoter_data.staff_guest_requires_name

            if promoter_data.owner_emails is not None:
                for owner in promoter.owners:
                    db.delete(owner)
                db.flush()
                for email in promoter_data.owner_emails:
                    promo_id = _resolve_promotions_staff_id(db, email)
                    if promo_id:
                        db.add(PromoterOwner(promoter_id=promoter.id, staff_id=promo_id))

            if promoter_data.contacts is not None:
                for contact in promoter.contacts:
                    db.delete(contact)
                db.flush()
                for c in promoter_data.contacts:
                    db.add(
                        PromoterContact(
                            promoter_id=promoter.id,
                            name=c.name,
                            title=c.title,
                            email=c.email,
                            phone=c.phone,
                        )
                    )

            promoter.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(promoter)
            return promoter
        except HTTPException:
            raise
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error updating promoter {promoter_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update promoter due to constraint violation",
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating promoter {promoter_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while updating promoter",
            )

    @staticmethod
    def list_promoters(db: Session) -> list[Promoter]:
        try:
            return (
                db.query(Promoter)
                .filter(Promoter.deleted == False)  # noqa: E712
                .order_by(Promoter.name)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error listing promoters: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while listing promoters",
            )

    @staticmethod
    def delete_promoter(db: Session, promoter_id: int) -> None:
        try:
            promoter = PromoterService.get_promoter(db, promoter_id)
            promoter.deleted = True
            promoter.updated_at = datetime.now(timezone.utc)
            db.commit()
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting promoter {promoter_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while deleting promoter",
            )

    @staticmethod
    def undelete_promoter(db: Session, promoter_id: int) -> Promoter:
        try:
            promoter = db.query(Promoter).filter(Promoter.id == promoter_id).first()
            if not promoter:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Promoter with id {promoter_id} not found",
                )
            if not promoter.deleted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Promoter is not deleted",
                )
            promoter.deleted = False
            promoter.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(promoter)
            return promoter
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error restoring promoter {promoter_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while restoring promoter",
            )

    @staticmethod
    def list_deleted_promoters(db: Session) -> list[Promoter]:
        try:
            return (
                db.query(Promoter)
                .filter(Promoter.deleted == True)  # noqa: E712
                .order_by(Promoter.name)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error listing deleted promoters: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while listing deleted promoters",
            )
