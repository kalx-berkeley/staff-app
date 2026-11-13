import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { venuesAPI } from '../api';
import { VenueRepList } from '../components';
import { filterVenues } from '../venueSearch';
import { usePageTitle } from '../../common/hooks/usePageTitle';
import type { VenueResponse } from '../types';
import type { APIError } from '../../common/types';

/**
 * Every venue with its KALX promotions reps, searchable by venue or rep. Each
 * venue's name links to the shows page filtered to that venue.
 */
const VenueList = () => {
  usePageTitle('Venues · Staff');
  const [venues, setVenues] = useState<VenueResponse[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadVenues = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setVenues(await venuesAPI.list());
    } catch (err) {
      const apiError = err as APIError;
      setError(typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load venues');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadVenues();
  }, [loadVenues]);

  if (loading) return <div className="loading">Loading venues...</div>;

  if (error) {
    return (
      <div className="error">
        <p>Error: {error}</p>
        <button onClick={loadVenues} className="btn-primary">Retry</button>
      </div>
    );
  }

  const filteredVenues = filterVenues(venues, query);

  return (
    <div className="venue-list">
      <div className="venue-list-header">
        <h2>Venues</h2>
      </div>

      <div className="venue-filter">
        <input
          type="text"
          aria-label="Search venues"
          placeholder="Search by venue, rep name or rep email..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="venue-filter-input"
        />
        {query && (
          <button onClick={() => setQuery('')} className="btn-secondary btn-small">
            Clear
          </button>
        )}
      </div>

      {filteredVenues.length === 0 ? (
        <p className="empty-message">
          {query ? 'No venues match your search.' : 'No venues found.'}
        </p>
      ) : (
        <div className="venues-list">
          <table className="venues-list-table venues-reps-table">
            <thead>
              <tr>
                <th>Venue</th>
                <th>KALX Promotions Reps</th>
              </tr>
            </thead>
            <tbody>
              {filteredVenues.map((venue) => (
                <tr key={venue.id}>
                  <td>
                    <div className="venue-reps-table-name">
                      <Link to={`/staff/shows?venue=${venue.id}`}>{venue.name}</Link>
                    </div>
                    <div className="venue-reps-table-address">{venue.address}</div>
                  </td>
                  <td>
                    <VenueRepList reps={venue.owner_details} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default VenueList;
