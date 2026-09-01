"""ShowBand model — links a character range in a show's event_name to a MusicBrainz artist."""

from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class ShowBand(Base):
    """Maps a substring of a show's event_name to a MusicBrainz artist record."""

    __tablename__ = "show_bands"

    id = Column(Integer, primary_key=True, index=True)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False, index=True)
    musicbrainz_id = Column(String, nullable=False)
    band_name = Column(String, nullable=False)
    start_pos = Column(Integer, nullable=False)
    end_pos = Column(Integer, nullable=False)
    artist_type = Column(String, nullable=True)
    artist_country = Column(String, nullable=True)
    artist_disambiguation = Column(String, nullable=True)
    artist_tags = Column(JSON, nullable=True)

    show = relationship("Show", back_populates="bands")
