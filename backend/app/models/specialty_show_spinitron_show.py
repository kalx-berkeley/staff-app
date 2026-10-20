"""SpecialtyShowSpinitronShow model — maps specialty shows to their Spinitron shows."""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class SpecialtyShowSpinitronShow(Base):
    """
    One of a specialty show's Spinitron show identities.

    A Spinitron playlist whose show_id is one of these is that specialty show,
    which is how the directory tells specialty shows from regular DJ shifts.
    """

    __tablename__ = "specialty_show_spinitron_shows"

    id = Column(Integer, primary_key=True, index=True)
    specialty_show_id = Column(
        Integer, ForeignKey("specialty_shows.id", ondelete="CASCADE"), nullable=False
    )
    spinitron_show_id = Column(Integer, nullable=False, unique=True)
    # The Spinitron show's title when it was added, for display
    title = Column(String, nullable=True)

    specialty_show = relationship("SpecialtyShow", back_populates="spinitron_show_rows")
