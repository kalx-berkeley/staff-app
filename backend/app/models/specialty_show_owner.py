"""SpecialtyShowOwner model — maps specialty shows to staff owners."""

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class SpecialtyShowOwner(Base):
    """Associates a specialty show with one or more staff members as owners."""

    __tablename__ = "specialty_show_owners"

    id = Column(Integer, primary_key=True, index=True)
    specialty_show_id = Column(Integer, ForeignKey("specialty_shows.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)

    specialty_show = relationship("SpecialtyShow", back_populates="owners")
    staff = relationship("Staff")

    @property
    def staff_email(self) -> str | None:
        return self.staff.email if self.staff else None
