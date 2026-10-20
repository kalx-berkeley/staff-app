import { useEffect, useId, useState } from 'react';
import type { ClipboardEvent, KeyboardEvent } from 'react';
import { directoryAPI } from './api';
import { spinitronUrl } from './directorySearch';
import { looksLikeUrl } from './profileFormat';
import { errorMessage } from '../common/utils';
import type { DjPersona } from './types';

interface DjPersonaEditorProps {
  personas: DjPersona[];
  onChange: (personas: DjPersona[]) => void;
  disabled?: boolean;
}

// The DJ Name field: the staff member's Spinitron personas as chips. Add one
// by typing its name and choosing it, or by pasting its Spinitron link.
const DjPersonaEditor = ({ personas, onChange, disabled = false }: DjPersonaEditorProps) => {
  const inputId = useId();
  const listId = useId();
  const [text, setText] = useState('');
  const [matches, setMatches] = useState<DjPersona[]>([]);
  const [error, setError] = useState<string | null>(null);

  const query = text.trim();
  useEffect(() => {
    if (disabled || query.length < 2 || looksLikeUrl(query)) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      directoryAPI
        .searchPersonas(query)
        .then((found) => {
          if (!cancelled) setMatches(found);
        })
        .catch((err) => {
          if (!cancelled) setError(errorMessage(err));
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, disabled]);

  const shownMatches = query.length >= 2 && !looksLikeUrl(query) ? matches : [];

  const add = (persona: DjPersona) => {
    if (!personas.some((p) => p.id === persona.id)) onChange([...personas, persona]);
    setText('');
    setMatches([]);
    setError(null);
  };

  const resolve = async (url: string) => {
    setError(null);
    try {
      add(await directoryAPI.resolvePersona(url.trim()));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    const pasted = event.clipboardData.getData('text');
    if (looksLikeUrl(pasted)) {
      event.preventDefault();
      setText(pasted.trim());
      void resolve(pasted);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    if (looksLikeUrl(text)) void resolve(text);
    else if (shownMatches.length > 0) add(shownMatches[0]);
  };

  return (
    <div className="persona-editor">
      {personas.length > 0 ? (
        <ul className="persona-chips" aria-label="Your DJ names">
          {personas.map((persona) => (
            <li key={persona.id} className="persona-chip">
              <a href={spinitronUrl(persona.id)} target="_blank" rel="noreferrer">
                {persona.name}
              </a>
              <button
                type="button"
                aria-label={`Remove ${persona.name}`}
                onClick={() => onChange(personas.filter((p) => p.id !== persona.id))}
                disabled={disabled}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="persona-none">No DJ names</p>
      )}
      <label htmlFor={inputId} className="visually-hidden">
        Add a DJ name
      </label>
      <input
        id={inputId}
        type="text"
        aria-describedby={shownMatches.length > 0 ? listId : undefined}
        autoComplete="off"
        placeholder="Type a DJ name, or paste a Spinitron DJ link"
        value={text}
        disabled={disabled}
        onChange={(event) => {
          setText(event.target.value);
          setError(null);
        }}
        onPaste={handlePaste}
        onKeyDown={handleKeyDown}
      />
      {shownMatches.length > 0 && (
        <ul id={listId} className="persona-matches" aria-label="Matching DJ names">
          {shownMatches.map((persona) => (
            <li key={persona.id}>
              <button type="button" onClick={() => add(persona)}>
                {persona.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="field-warning">{error}</p>}
    </div>
  );
};

export default DjPersonaEditor;
