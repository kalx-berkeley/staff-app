"""SpecialtyShow model — on-air DJ specialty shows that can receive pre-assigned passes."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class SpecialtyShow(Base):
    """A named specialty show (on-air DJ shift) that can be pre-assigned pass pairs."""

    __tablename__ = "specialty_shows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
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
        "SpecialtyShowOwner", back_populates="specialty_show", cascade="all, delete-orphan"
    )
    djs = relationship(
        "SpecialtyShowDJ", back_populates="specialty_show", cascade="all, delete-orphan"
    )

    @property
    def owner_emails(self) -> list[str]:
        return [o.staff_email for o in self.owners if o.staff_email]

    @property
    def dj_names(self) -> list[str]:
        return [d.dj_name for d in self.djs]
