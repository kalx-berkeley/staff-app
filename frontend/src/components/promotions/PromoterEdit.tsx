import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { promotersAPI } from '../../services/api';
import type { PromoterResponse, APIError } from '../../types';
import PromoterForm from './PromoterForm';

const PromoterEdit = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [promoter, setPromoter] = useState<PromoterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadPromoter = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await promotersAPI.get(Number(id));
        setPromoter(data);
      } catch (err) {
        const apiError = err as APIError;
        setError(
          typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load promoter'
        );
      } finally {
        setLoading(false);
      }
    };

    loadPromoter();
  }, [id]);

  const handleDone = () => navigate('/promotions/promoters');

  if (loading) {
    return <div className="loading">Loading promoter...</div>;
  }

  if (error || !promoter) {
    return (
      <div className="error">
        <p>Error: {error ?? 'Promoter not found'}</p>
        <button onClick={handleDone}>Back to Promoters</button>
      </div>
    );
  }

  return (
    <PromoterForm
      promoter={promoter}
      asPage={true}
      onClose={handleDone}
      onSuccess={handleDone}
      onDelete={handleDone}
    />
  );
};

export default PromoterEdit;
