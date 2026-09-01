"""Staff model."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, JSON, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Staff(Base):
    """Staff model representing radio station staff members eligible for pass_item claims."""

    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    spinitron_ids = Column(JSON, nullable=True)
    dj_name = Column(String, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    claimed_passes = relationship(
        "Pass", foreign_keys="[Pass.staff_id]", back_populates="staff"
    )
    departments = relationship(
        "StaffDepartment", back_populates="staff", cascade="all, delete-orphan"
    )
    statuses = relationship(
        "StaffStatus", back_populates="staff", cascade="all, delete-orphan"
    )
