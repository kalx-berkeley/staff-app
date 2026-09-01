"""VenueOwner model — maps venues to promotions staff owners."""

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class VenueOwner(Base):
    """Associates a venue with one or more promotions staff members."""

    __tablename__ = "venue_owners"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)

    venue = relationship("Venue", back_populates="owners")
    staff = relationship("Staff")

    @property
    def promotions_staff_email(self) -> str | None:
        return self.staff.email if self.staff else None
