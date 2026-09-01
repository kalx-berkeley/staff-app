"""VenueContact model — contact people at a venue."""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class VenueContact(Base):
    """A contact person at a venue (optional fields)."""

    __tablename__ = "venue_contacts"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    name = Column(String, nullable=True)
    title = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    venue = relationship("Venue", back_populates="contacts")
