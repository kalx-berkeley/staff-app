"""SpecialtyShowDJ model — maps specialty shows to DJ name members."""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class SpecialtyShowDJ(Base):
    """Associates a specialty show with one or more DJ names."""

    __tablename__ = "specialty_show_djs"

    id = Column(Integer, primary_key=True, index=True)
    specialty_show_id = Column(Integer, ForeignKey("specialty_shows.id"), nullable=False)
    dj_name = Column(String, nullable=False, index=True)

    specialty_show = relationship("SpecialtyShow", back_populates="djs")
