import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { APIError } from '../../../common/types';
import { useReturnToList } from '../../listUrlState';
import { usePageTitle } from '../../../common/hooks/usePageTitle';

interface EntityEditPageProps<T extends { name: string }> {
  /** What is being edited, such as "Venue". */
  noun: string;
  listPath: string;
  load: (id: number) => Promise<T>;
  /** Renders the form for the loaded one. `done` goes back to the list. */
  renderForm: (entity: T, done: () => void) => ReactNode;
}

/** Loads the venue or promoter in the URL and shows its edit form. */
const EntityEditPage = <T extends { name: string }>({
  noun,
  listPath,
  load,
  renderForm,
}: EntityEditPageProps<T>) => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const returnTo = useReturnToList(listPath);
  const [entity, setEntity] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  usePageTitle(`Edit ${entity?.name ?? noun} · Promotions`);
  const lowerNoun = noun.toLowerCase();

  useEffect(() => {
    const loadEntity = async () => {
      try {
        setLoading(true);
        setError(null);
        setEntity(await load(Number(id)));
      } catch (err) {
        const apiError = err as APIError;
        setError(typeof apiError.detail === 'string' ? apiError.detail : `Failed to load ${lowerNoun}`);
      } finally {
        setLoading(false);
      }
    };

    loadEntity();
  }, [id, load, lowerNoun]);

  const done = () => navigate(returnTo);

  if (loading) {
    return <div className="loading">Loading {lowerNoun}...</div>;
  }

  if (error || !entity) {
    return (
      <div className="error">
        <p>Error: {error ?? `${noun} not found`}</p>
        <button onClick={done}>Back to {noun}s</button>
      </div>
    );
  }

  return <>{renderForm(entity, done)}</>;
};

export default EntityEditPage;
