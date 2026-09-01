"""Promoter API endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.promoter import PromoterCreate, PromoterResponse, PromoterUpdate
from app.services.promoter_service import PromoterService
from app.services import audit_service
from app.auth import get_promotions_staff
from app.models.staff import Staff

router = APIRouter(prefix="/api/promoters", tags=["promoters"])


def _promoter_response(promoter) -> PromoterResponse:
    return PromoterResponse.from_orm_promoter(promoter)


@router.get("", response_model=list[PromoterResponse])
def list_promoters(db: Session = Depends(get_db)):
    """List all active (non-deleted) promoters."""
    return [_promoter_response(p) for p in PromoterService.list_promoters(db)]


@router.get("/deleted", response_model=list[PromoterResponse])
def list_deleted_promoters(
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """List all soft-deleted promoters (promotions staff only)."""
    return [_promoter_response(p) for p in PromoterService.list_deleted_promoters(db)]


@router.post("", response_model=PromoterResponse, status_code=status.HTTP_201_CREATED)
def create_promoter(
    promoter_data: PromoterCreate,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Create a new promoter. The creating user is automatically added as an owner."""
    promoter = PromoterService.create_promoter(
        db, promoter_data, owner_email=promotions.email
    )
    audit_service.log_event(
        db,
        event_type="promoter_created",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="promoter",
        entity_id=promoter.id,
        details={"name": promoter.name},
    )
    return _promoter_response(promoter)


@router.get("/{promoter_id}", response_model=PromoterResponse)
def get_promoter(promoter_id: int, db: Session = Depends(get_db)):
    """Get a promoter by ID."""
    return _promoter_response(PromoterService.get_promoter(db, promoter_id))


@router.put("/{promoter_id}", response_model=PromoterResponse)
def update_promoter(
    promoter_id: int,
    promoter_data: PromoterUpdate,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Update a promoter (promotions staff only)."""
    promoter = PromoterService.update_promoter(db, promoter_id, promoter_data)
    audit_service.log_event(
        db,
        event_type="promoter_updated",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="promoter",
        entity_id=promoter.id,
        details={"name": promoter.name},
    )
    return _promoter_response(promoter)


@router.delete("/{promoter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promoter(
    promoter_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Soft-delete a promoter (promotions staff only)."""
    promoter = PromoterService.get_promoter(db, promoter_id)
    promoter_name = promoter.name
    PromoterService.delete_promoter(db, promoter_id)
    audit_service.log_event(
        db,
        event_type="promoter_deleted",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="promoter",
        entity_id=promoter_id,
        details={"name": promoter_name},
    )


@router.post("/{promoter_id}/undelete", response_model=PromoterResponse)
def undelete_promoter(
    promoter_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Restore a soft-deleted promoter (promotions staff only)."""
    promoter = PromoterService.undelete_promoter(db, promoter_id)
    audit_service.log_event(
        db,
        event_type="promoter_undeleted",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="promoter",
        entity_id=promoter_id,
        details={"name": promoter.name},
    )
    return _promoter_response(promoter)
