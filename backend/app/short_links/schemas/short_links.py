"""Short Links request and response schemas."""

from pydantic import BaseModel

from app.common.schemas.types import UtcDatetime


class ShortLinkRequest(BaseModel):
    slug: str
    target_url: str
    note: str | None = None


class ShortLinkResponse(BaseModel):
    id: int
    # Lowercase, as stored
    slug: str
    target_url: str
    note: str | None
    created_by_email: str
    created_at: UtcDatetime
    updated_at: UtcDatetime
