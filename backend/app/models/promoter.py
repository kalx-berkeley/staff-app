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
    show_sourcing_instructions = Column(Text, nullable=True)
    pass_call_instructions = Column(Text, nullable=True)
    requires_phone_number = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Which winners' email addresses the guest list needs: "none", "staff_passes"
    # (staff claimants only, whose addresses we already have) or "all" (DJs
    # must also collect one from every on-air winner)
    email_address_requirement = Column(
        String, nullable=False, default="none", server_default="none"
    )
    staff_guest_requires_name = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Hold the emails telling staff and alternates the outcome when a show closes
    # until a promotions rep clicks the button on the show page
    hold_close_notifications = Column(
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
    def requires_email_address(self) -> bool:
        """Whether DJs must collect an email address from on-air winners."""
        return self.email_address_requirement == "all"

    @property
    def includes_staff_email_address(self) -> bool:
        """Whether the guest list includes staff claimants' email addresses."""
        return self.email_address_requirement in ("staff_passes", "all")

    @property
    def owner_emails(self) -> list[str]:
        return [o.promotions_staff_email for o in self.owners]
