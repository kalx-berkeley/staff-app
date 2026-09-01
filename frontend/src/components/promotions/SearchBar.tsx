import { useState, useEffect, useRef } from 'react';
import { venuesAPI } from '../../services/api';
import type { ShowSummary, VenueResponse } from '../../types';

interface SearchBarProps {
  shows: ShowSummary[];
  onSearch: (results: ShowSummary[]) => void;
  externalGenre?: string;
  onGenreChange?: (genre: string) => void;
}

const SearchBar = ({ shows, onSearch, externalGenre, onGenreChange }: SearchBarProps) => {
  const [query, setQuery] = useState('');
  const [venueId, setVenueId] = useState<number | ''>('');
  const [genre, setGenre] = useState(externalGenre || '');
  const [venues, setVenues] = useState<VenueResponse[]>([]);
  const [filtersExpanded, setFiltersExpanded] = useState(false);

  const onSearchRef = useRef(onSearch);
  onSearchRef.current = onSearch;

  const onGenreChangeRef = useRef(onGenreChange);
  onGenreChangeRef.current = onGenreChange;

  const prevExternalGenreRef = useRef(externalGenre);

  useEffect(() => {
    if (externalGenre !== prevExternalGenreRef.current) {
      prevExternalGenreRef.current = externalGenre;
      setGenre(externalGenre || '');
    }
  }, [externalGenre]);

  useEffect(() => {
    onGenreChangeRef.current?.(genre);
  }, [genre]);

  useEffect(() => {
    venuesAPI.list().then(setVenues).catch(() => {});
  }, []);

  // Filter shows client-side whenever shows or filters change
  useEffect(() => {
    const q = query.trim().toLowerCase();
    const genreTerms = genre.split(',').map((t) => t.trim().toLowerCase()).filter(Boolean);

    const filtered = shows.filter((show) => {
      if (venueId !== '' && show.venue.id !== venueId) return false;
      if (genreTerms.length > 0 && !genreTerms.some((term) => (show.genre ?? []).some((sg) => sg.toLowerCase().includes(term)))) return false;
      if (q) {
        const searchable = [
          show.event_name,
          ...(show.genre ?? []),
          show.venue.name,
          show.caller_special_instructions ?? '',
        ]
          .join(' ')
          .toLowerCase();
        if (!searchable.includes(q)) return false;
      }
      return true;
    });

    onSearchRef.current(filtered);
  }, [shows, query, genre, venueId]);

  const handleClear = () => {
    setQuery('');
    setVenueId('');
    setGenre('');
  };

  const hasFilters = query.trim() || venueId !== '' || genre.trim();
  const activeExtraFilterCount = (venueId !== '' ? 1 : 0) + (genre.trim() ? 1 : 0);


  return (
    <div className={`search-bar${filtersExpanded ? ' search-bar--expanded' : ''}`}>
      <div className="search-inputs">
        <div className="search-group search-group-wide">
          <label htmlFor="search-query">Search</label>
          <input
            type="text"
            id="search-query"
            placeholder="Search by event name, genre, or venue..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            type="button"
            className="search-filters-toggle"
            onClick={() => setFiltersExpanded((v) => !v)}
            aria-expanded={filtersExpanded}
          >
            Filters{activeExtraFilterCount > 0 ? ` (${activeExtraFilterCount})` : ''}{' '}
            {filtersExpanded ? '▲' : '▼'}
          </button>
        </div>

        <div className="search-group">
          <label htmlFor="search-venue">Venue</label>
          <select
            id="search-venue"
            value={venueId}
            onChange={(e) => setVenueId(e.target.value ? parseInt(e.target.value) : '')}
          >
            <option value="">All Venues</option>
            {venues.map((venue) => (
              <option key={venue.id} value={venue.id}>
                {venue.name}
              </option>
            ))}
          </select>
        </div>

        <div className="search-group">
          <label htmlFor="search-genre">Genre</label>
          <input
            type="text"
            id="search-genre"
            placeholder="Filter by genre..."
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
          />
        </div>
      </div>

      <div className="search-actions">
        {hasFilters && (
          <button onClick={handleClear} className="btn-secondary">
            Clear Filters
          </button>
        )}
      </div>
    </div>
  );
};

export default SearchBar;
