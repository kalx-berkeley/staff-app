import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { venuesAPI, venuesMyAPI } from '../api';
import type { VenueResponse } from '../types';
import { VenueRepList } from '../components';
import { filterVenues } from '../venueSearch';
import type { APIError } from '../../common/types';
import { usePageTitle } from '../../common/hooks/usePageTitle';

const VIEW_MODE_KEY = 'kalx_venue_view_mode';

const VenueList = () => {
  usePageTitle('Venues · Promotions');
  const navigate = useNavigate();
  const [venues, setVenues] = useState<VenueResponse[]>([]);
  const [venueFilter, setVenueFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMineOnly, setShowMineOnly] = useState(true);
  const [viewMode, setViewMode] = useState<'card' | 'compact'>(
    (localStorage.getItem(VIEW_MODE_KEY) as 'card' | 'compact') || 'card'
  );

  const loadVenues = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = showMineOnly ? await venuesMyAPI.listMy() : await venuesAPI.list();
      setVenues(data);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load venues'
      );
    } finally {
      setLoading(false);
    }
  }, [showMineOnly]);

  useEffect(() => {
    loadVenues();
  }, [loadVenues]);

  const handleCreateClick = () => {
    navigate('/promotions/venues/new');
  };

  const handleEditClick = (venue: VenueResponse) => {
    navigate(`/promotions/venues/${venue.id}/edit`);
  };

  const handleViewMode = (mode: 'card' | 'compact') => {
    setViewMode(mode);
    localStorage.setItem(VIEW_MODE_KEY, mode);
  };

  if (loading) {
    return <div className="loading">Loading venues...</div>;
  }

  if (error) {
    return (
      <div className="error">
        <p>Error: {error}</p>
        <button onClick={loadVenues} className="btn-primary">Retry</button>
      </div>
    );
  }

  const filteredVenues = filterVenues(venues, venueFilter, { includeAddress: true });

  return (
    <div className="venue-list">
      <div className="venue-list-header">
        <h2>Venues</h2>
        <div className="mine-toggle">
          <button
            className={showMineOnly ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setShowMineOnly(true)}
          >
            My Venues
          </button>
          <button
            className={!showMineOnly ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setShowMineOnly(false)}
          >
            All Venues
          </button>
        </div>
        <button onClick={handleCreateClick} className="btn-primary">
          New Venue
        </button>
      </div>

      <div className="venue-filter">
        <input
          type="text"
          placeholder="Filter by venue, address, rep name or rep email..."
          value={venueFilter}
          onChange={(e) => setVenueFilter(e.target.value)}
          className="venue-filter-input"
        />
        {venueFilter && (
          <button
            onClick={() => setVenueFilter('')}
            className="btn-secondary btn-small"
          >
            Clear
          </button>
        )}

        <div className="view-toggle">
          <button
            className={viewMode === 'card' ? 'active' : ''}
            onClick={() => handleViewMode('card')}
            title="Card view"
          >
            Cards
          </button>
          <button
            className={viewMode === 'compact' ? 'active' : ''}
            onClick={() => handleViewMode('compact')}
            title="Compact list view"
          >
            List
          </button>
        </div>
      </div>

      {filteredVenues.length === 0 ? (
        <p className="empty-message">
          {venueFilter ? 'No venues match your filter.' : 'No venues found. Create your first venue!'}
        </p>
      ) : viewMode === 'compact' ? (
        <div className="venues-list">
          <table className="venues-list-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Address</th>
                <th>KALX Promotions Reps</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filteredVenues.map((venue) => (
                <tr key={venue.id}>
                  <td>{venue.name}</td>
                  <td>{venue.address}</td>
                  <td>
                    <VenueRepList reps={venue.owner_details} />
                  </td>
                  <td>
                    <button
                      onClick={() => handleEditClick(venue)}
                      className="btn-primary btn-small"
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="venue-grid">
          {filteredVenues.map((venue) => (
            <div key={venue.id} className="venue-card">
              <h3>{venue.name}</h3>
              <p className="venue-address">{venue.address}</p>
              <div className="venue-card-reps">
                <span className="venue-card-reps-label">
                  KALX Promotions Rep{venue.owner_details.length === 1 ? '' : 's'}
                </span>
                <VenueRepList reps={venue.owner_details} />
              </div>
              <button
                onClick={() => handleEditClick(venue)}
                className="btn-primary"
              >
                Edit
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default VenueList;
