import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { promotersAPI } from '../../services/api';
import type { PromoterResponse, APIError } from '../../types';

const PromoterList = () => {
  const navigate = useNavigate();
  const [promoters, setPromoters] = useState<PromoterResponse[]>([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPromoters = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await promotersAPI.list();
      setPromoters(data);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load promoters'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPromoters();
  }, [loadPromoters]);

  if (loading) {
    return <div className="loading">Loading promoters...</div>;
  }

  if (error) {
    return (
      <div className="error">
        <p>Error: {error}</p>
        <button onClick={loadPromoters}>Retry</button>
      </div>
    );
  }

  const filtered = filter.trim()
    ? promoters.filter((p) => p.name.toLowerCase().includes(filter.toLowerCase()))
    : promoters;

  return (
    <div className="venue-list">
      <div className="venue-list-header">
        <h2>Promoters</h2>
        <button onClick={() => navigate('/promotions/promoters/new')} className="btn-primary">
          Create New Promoter
        </button>
      </div>

      <div className="venue-filter">
        <input
          type="text"
          placeholder="Filter promoters by name..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="venue-filter-input"
        />
        {filter && (
          <button onClick={() => setFilter('')} className="btn-secondary btn-small">
            Clear
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <p className="empty-message">
          {filter ? 'No promoters match your filter.' : 'No promoters found. Create your first promoter!'}
        </p>
      ) : (
        <div className="venue-grid">
          {filtered.map((promoter) => (
            <div key={promoter.id} className="venue-card">
              <h3>{promoter.name}</h3>
              {promoter.owner_emails.length > 0 && (
                <p className="venue-address">
                  {promoter.owner_emails.length === 1
                    ? '1 owner'
                    : `${promoter.owner_emails.length} owners`}
                </p>
              )}
              <button
                onClick={() => navigate(`/promotions/promoters/${promoter.id}/edit`)}
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

export default PromoterList;
