"""Venue API endpoints."""

import io
import os
import pathlib

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas.venue import VenueCreate, VenueResponse, VenueUpdate
from app.services.venue_service import VenueService
from app.services import audit_service
from app.auth import get_promotions_staff
from app.models.staff import Staff
from app.models.venue import Venue

_LOGO_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_LOGO_MAX_PX = (800, 400)
_ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}

router = APIRouter(prefix="/api/venues", tags=["venues"])


def _venue_response(venue) -> VenueResponse:
    return VenueResponse.from_orm_venue(venue)


class PromotionsStaffOption(BaseModel):
    id: int
    name: str
    email: str


@router.get("/promotions-staff", response_model=list[PromotionsStaffOption])
def list_promotions_staff(
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """List promotions department staff, for owner-picker autocompletes."""
    return [
        PromotionsStaffOption(id=s.id, name=s.name, email=s.email)
        for s in VenueService.list_promotions_staff(db)
    ]


@router.get("/deleted", response_model=list[VenueResponse])
def list_deleted_venues(
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """List all soft-deleted venues (promotions staff only)."""
    return [_venue_response(v) for v in VenueService.list_deleted_venues(db)]


@router.get("", response_model=list[VenueResponse])
def list_venues(db: Session = Depends(get_db)):
    """List all active (non-deleted) venues (used for dropdowns and show filtering)."""
    return [_venue_response(v) for v in VenueService.list_venues(db)]


@router.get("/my", response_model=list[VenueResponse])
def list_my_venues(
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """List venues owned by the current promotions user."""
    return [
        _venue_response(v)
        for v in VenueService.list_venues(db, owner_staff_id=promotions.id)
    ]


@router.post("", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
def create_venue(
    venue_data: VenueCreate,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Create a new venue. The creating user is automatically added as an owner."""
    venue = VenueService.create_venue(db, venue_data, owner_email=promotions.email)
    audit_service.log_event(
        db,
        event_type="venue_created",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="venue",
        entity_id=venue.id,
        details={"name": venue.name, "address": venue.address},
    )
    return _venue_response(venue)


@router.get("/{venue_id}", response_model=VenueResponse)
def get_venue(venue_id: int, db: Session = Depends(get_db)):
    """Get a venue by ID."""
    return _venue_response(VenueService.get_venue(db, venue_id))


@router.delete("/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_venue(
    venue_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Soft-delete a venue by marking it deleted (promotions staff only)."""
    venue = VenueService.get_venue(db, venue_id)
    venue_name = venue.name
    VenueService.delete_venue(db, venue_id)
    audit_service.log_event(
        db,
        event_type="venue_deleted",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="venue",
        entity_id=venue_id,
        details={"name": venue_name},
    )


@router.post("/{venue_id}/undelete", response_model=VenueResponse)
def undelete_venue(
    venue_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Restore a soft-deleted venue (promotions staff only)."""
    venue = VenueService.undelete_venue(db, venue_id)
    audit_service.log_event(
        db,
        event_type="venue_undeleted",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="venue",
        entity_id=venue_id,
        details={"name": venue.name},
    )
    return _venue_response(venue)


@router.get("/{venue_id}/logo")
def get_venue_logo(venue_id: int, db: Session = Depends(get_db)):
    """Return the venue's logo image file."""
    venue = VenueService.get_venue(db, venue_id)
    if not venue.logo_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No logo for this venue"
        )
    logo_path = pathlib.Path(settings.venue_logo_dir) / venue.logo_filename
    if not logo_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Logo file not found"
        )
    return FileResponse(
        str(logo_path), media_type="image/png", headers={"Cache-Control": "max-age=3600"}
    )


@router.post("/{venue_id}/logo", response_model=VenueResponse)
def upload_venue_logo(
    venue_id: int,
    file: UploadFile = File(...),
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Upload or replace a venue logo image (promotions staff only)."""
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image type '{file.content_type}'. Use PNG, JPEG, GIF, or"
                " WebP."
            ),
        )

    raw = file.file.read()
    if len(raw) > _LOGO_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logo file too large (max {_LOGO_MAX_BYTES // (1024 * 1024)} MB).",
        )

    try:
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGBA")
        img.thumbnail(_LOGO_MAX_PX, Image.LANCZOS)
        output = io.BytesIO()
        img.save(output, format="PNG", optimize=True)
        output.seek(0)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not process image. Please upload a valid image file.",
        )

    logo_dir = pathlib.Path(settings.venue_logo_dir)
    logo_dir.mkdir(parents=True, exist_ok=True)
    filename = f"venue_{venue_id}.png"
    logo_path = logo_dir / filename
    logo_path.write_bytes(output.read())

    venue = VenueService.get_venue(db, venue_id)
    venue.logo_filename = filename
    db.commit()
    db.refresh(venue)

    audit_service.log_event(
        db,
        event_type="venue_logo_uploaded",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="venue",
        entity_id=venue_id,
        details={"name": venue.name},
    )
    return _venue_response(venue)


@router.delete("/{venue_id}/logo", response_model=VenueResponse)
def delete_venue_logo(
    venue_id: int,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Remove a venue's logo image (promotions staff only)."""
    venue = VenueService.get_venue(db, venue_id)
    if not venue.logo_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No logo for this venue"
        )

    logo_path = pathlib.Path(settings.venue_logo_dir) / venue.logo_filename
    if logo_path.exists():
        os.remove(logo_path)

    venue.logo_filename = None
    db.commit()
    db.refresh(venue)

    audit_service.log_event(
        db,
        event_type="venue_logo_deleted",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="venue",
        entity_id=venue_id,
        details={"name": venue.name},
    )
    return _venue_response(venue)


@router.put("/{venue_id}", response_model=VenueResponse)
def update_venue(
    venue_id: int,
    venue_data: VenueUpdate,
    promotions: Staff = Depends(get_promotions_staff),
    db: Session = Depends(get_db),
):
    """Update a venue."""
    # Snapshot before-state for the audit log.
    existing = db.query(Venue).filter(Venue.id == venue_id).first()
    before: dict = {}
    if existing:
        before = {
            "name": existing.name,
            "address": existing.address,
            "pass_call_instructions": existing.pass_call_instructions,
            "win_frequency_days": existing.win_frequency_days,
        }

    venue = VenueService.update_venue(db, venue_id, venue_data)

    after = {
        "name": venue.name,
        "address": venue.address,
        "pass_call_instructions": venue.pass_call_instructions,
        "win_frequency_days": venue.win_frequency_days,
    }
    changed_fields = {
        k: {"before": before[k], "after": after[k]}
        for k in after
        if before.get(k) != after[k]
    }
    audit_service.log_event(
        db,
        event_type="venue_updated",
        actor_email=promotions.email,
        actor_role="promotions",
        entity_type="venue",
        entity_id=venue.id,
        details={"name": venue.name, "changed_fields": changed_fields},
    )
    return _venue_response(venue)
