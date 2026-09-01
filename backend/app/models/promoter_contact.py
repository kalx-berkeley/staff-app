"""PromoterContact model — contact people at a promoter."""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class PromoterContact(Base):
    """A contact person at a promoter (optional fields)."""

    __tablename__ = "promoter_contacts"

    id = Column(Integer, primary_key=True, index=True)
    promoter_id = Column(Integer, ForeignKey("promoters.id"), nullable=False)
    name = Column(String, nullable=True)
    title = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    promoter = relationship("Promoter", back_populates="contacts")
