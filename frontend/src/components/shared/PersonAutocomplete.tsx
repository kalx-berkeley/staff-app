import { useState } from 'react';

export interface PersonOption {
  email: string;
  name: string | null;
}

interface PersonAutocompleteProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  /** Called with the raw committed text (Enter) or a suggestion's email (click/Tab). Apply `extractPersonEmail` to normalize it. */
  onSubmit: (rawValue: string) => void;
  options: PersonOption[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

/** Type-ahead input for picking a person by name or email from a known list (e.g. owner pickers). */
const PersonAutocomplete = ({
  id,
  value,
  onChange,
  onSubmit,
  options,
  placeholder = 'Add by name or email...',
  disabled = false,
  className,
  style,
}: PersonAutocompleteProps) => {
  const [suggestions, setSuggestions] = useState<PersonOption[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const filterOptions = (query: string): PersonOption[] => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return options.filter(
      (o) => o.name?.toLowerCase().includes(q) || o.email.toLowerCase().includes(q)
    );
  };

  const handleChange = (newValue: string) => {
    onChange(newValue);
    const filtered = filterOptions(newValue);
    setSuggestions(filtered);
    setShowSuggestions(filtered.length > 0);
  };

  const commit = (rawValue: string) => {
    setShowSuggestions(false);
    onSubmit(rawValue);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commit(value);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    } else if (e.key === 'Tab' && suggestions.length === 1) {
      e.preventDefault();
      onChange(suggestions[0].email);
      setShowSuggestions(false);
    }
  };

  return (
    <div className={`autocomplete-wrapper${className ? ` ${className}` : ''}`} style={style}>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => setShowSuggestions(filterOptions(value).length > 0)}
        onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
      />
      {showSuggestions && suggestions.length > 0 && (
        <ul className="autocomplete-list">
          {suggestions.map((s) => (
            <li key={s.email} onMouseDown={() => commit(s.email)} className="autocomplete-item">
              {s.name ? `${s.name} (${s.email})` : s.email}
            </li>
          ))}
          {suggestions.length === 1 && (
            <li className="autocomplete-hint">Press Tab to complete</li>
          )}
        </ul>
      )}
    </div>
  );
};

export default PersonAutocomplete;
