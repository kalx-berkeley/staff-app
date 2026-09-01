import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { venuesAPI } from '../../services/api';
import type { VenueResponse, APIError } from '../../types';
import VenueForm from './VenueForm';

const VenueEdit = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [venue, setVenue] = useState<VenueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadVenue = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await venuesAPI.get(Number(id));
        setVenue(data);
      } catch (err) {
        const apiError = err as APIError;
        setError(
          typeof apiError.detail === 'string'
            ? apiError.detail
            : 'Failed to load venue'
        );
      } finally {
        setLoading(false);
      }
    };

    loadVenue();
  }, [id]);

  const handleDone = () => navigate('/promotions/venues');

  if (loading) {
    return <div className="loading">Loading venue...</div>;
  }

  if (error || !venue) {
    return (
      <div className="error">
        <p>Error: {error ?? 'Venue not found'}</p>
        <button onClick={handleDone}>Back to Venues</button>
      </div>
    );
  }

  return (
    <VenueForm
      venue={venue}
      asPage={true}
      onClose={handleDone}
      onSuccess={handleDone}
      onDelete={handleDone}
    />
  );
};

export default VenueEdit;
