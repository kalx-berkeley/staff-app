"""Promoter model — an entity (company) that promotes shows and holds venue relationships."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Promoter(Base):
    """A promoter is a company or entity that promotes shows at one or more venues."""

    __tablename__ = "promoters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    pass_call_instructions = Column(Text, nullable=True)
    requires_phone_number = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    requires_email_address = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    staff_guest_requires_name = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    owners = relationship(
        "PromoterOwner", back_populates="promoter", cascade="all, delete-orphan"
    )
    contacts = relationship(
        "PromoterContact", back_populates="promoter", cascade="all, delete-orphan"
    )

    @property
    def owner_emails(self) -> list[str]:
        return [o.promotions_staff_email for o in self.owners]
