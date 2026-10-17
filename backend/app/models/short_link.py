"""ShortLink model — a /go/<slug> redirect managed in KALX Staff Admin."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database import Base


class ShortLink(Base):
    """A short link: /go/<slug> redirects (302) to target_url."""

    __tablename__ = "short_link"

    id = Column(Integer, primary_key=True, index=True)
    # Always stored lowercase, so lookups ignore case
    slug = Column(String(64), nullable=False, unique=True, index=True)
    target_url = Column(String(2048), nullable=False)
    note = Column(Text, nullable=True)
    created_by_email = Column(String, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
