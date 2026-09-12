import { useEffect, useRef, useState } from 'react';

interface GenreTagInputProps {
  genres: string[];
  onChange: (genres: string[]) => void;
  knownGenres?: string[];
  disabled?: boolean;
  id?: string;
  placeholder?: string;
}

/**
 * A tag-style multi-value genre picker: type a genre and press Enter (or ",")
 * to add it, click × to remove one, backspace on an empty input to pop the
 * last one. `knownGenres` populates a datalist of suggestions to autocomplete
 * from, but any typed value is accepted.
 */
const GenreTagInput = ({
  genres,
  onChange,
  knownGenres = [],
  disabled,
  id = 'genre-input',
  placeholder,
}: GenreTagInputProps) => {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const wasDisabled = useRef(disabled);

  useEffect(() => {
    // A caller (e.g. auto-save on each change) commonly disables the field
    // for the duration of a save — a disabled input can't hold focus, so the
    // browser blurs it out from under the user. Re-focus it once re-enabled
    // so the cursor stays put instead of the user having to click back in.
    if (wasDisabled.current && !disabled) {
      inputRef.current?.focus();
    }
    wasDisabled.current = disabled;
  }, [disabled]);

  const addGenre = (value: string) => {
    const normalized = value.trim().toLowerCase();
    if (normalized && !genres.includes(normalized)) {
      onChange([...genres, normalized]);
    }
    setInput('');
  };

  const removeGenre = (index: number) => {
    onChange(genres.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addGenre(input);
    } else if (e.key === 'Backspace' && !input && genres.length > 0) {
      onChange(genres.slice(0, -1));
    }
  };

  const datalistId = `${id}-suggestions`;

  return (
    <div className="genre-tag-input">
      {genres.map((g, i) => (
        <span key={i} className="genre-tag">
          {g}
          <button
            type="button"
            className="genre-tag-remove"
            onClick={() => removeGenre(i)}
            disabled={disabled}
            aria-label={`Remove ${g}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        type="text"
        id={id}
        list={datalistId}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => {
          if (input.trim()) addGenre(input);
        }}
        placeholder={
          genres.length === 0 ? (placeholder ?? 'Type a genre, then Enter or comma…') : ''
        }
        disabled={disabled}
        className="genre-text-input"
      />
      <datalist id={datalistId}>
        {knownGenres
          .filter((g) => !genres.includes(g))
          .map((g) => (
            <option key={g} value={g} />
          ))}
      </datalist>
    </div>
  );
};

export default GenreTagInput;
