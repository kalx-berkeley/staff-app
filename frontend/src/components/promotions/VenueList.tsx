import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { venuesAPI, venuesMyAPI } from '../../services/api';
import type { VenueResponse, APIError } from '../../types';

const VenueList = () => {
  const navigate = useNavigate();
  const [venues, setVenues] = useState<VenueResponse[]>([]);
  const [venueFilter, setVenueFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMineOnly, setShowMineOnly] = useState(true);

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

  if (loading) {
    return <div className="loading">Loading venues...</div>;
  }

  if (error) {
    return (
      <div className="error">
        <p>Error: {error}</p>
        <button onClick={loadVenues}>Retry</button>
      </div>
    );
  }

  const filteredVenues = venueFilter.trim()
    ? venues.filter(
        (v) =>
          v.name.toLowerCase().includes(venueFilter.toLowerCase()) ||
          v.address.toLowerCase().includes(venueFilter.toLowerCase())
      )
    : venues;

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
          Create New Venue
        </button>
      </div>

      <div className="venue-filter">
        <input
          type="text"
          placeholder="Filter venues by name or address..."
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
      </div>

      {filteredVenues.length === 0 ? (
        <p className="empty-message">
          {venueFilter ? 'No venues match your filter.' : 'No venues found. Create your first venue!'}
        </p>
      ) : (
        <div className="venue-grid">
          {filteredVenues.map((venue) => (
            <div key={venue.id} className="venue-card">
              <h3>{venue.name}</h3>
              <p className="venue-address">{venue.address}</p>
              <button
                onClick={() => handleEditClick(venue)}
                className="btn-secondary"
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
