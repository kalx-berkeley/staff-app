import { useState } from 'react';

interface DjNameAutocompleteProps {
  id: string;
  value: string;
  onChange: (name: string) => void;
  /** Every DJ and specialty show name to suggest (from `autocompleteAPI.getDJNames`). */
  djNames: string[];
  /** Lowercased specialty show names, so their suggestions get a "Specialty Show" badge. */
  specialtyShowNames: Set<string>;
  disabled?: boolean;
  placeholder?: string;
}

/**
 * A text input that suggests DJ and specialty show names as you type. Unlike
 * `DjNameInput`, it doesn't remember the name or follow the on-air schedule,
 * so it suits forms that record someone else's DJ name. The caller loads the
 * names once, so a form with several of these makes one request.
 */
const DjNameAutocomplete = ({
  id,
  value,
  onChange,
  djNames,
  specialtyShowNames,
  disabled,
  placeholder = 'DJ Name',
}: DjNameAutocompleteProps) => {
  const [matches, setMatches] = useState<string[]>([]);
  const [open, setOpen] = useState(false);

  const handleChange = (newValue: string) => {
    onChange(newValue);
    const query = newValue.trim().toLowerCase();
    const filtered = query ? djNames.filter((name) => name.toLowerCase().includes(query)) : [];
    setMatches(filtered);
    setOpen(filtered.length > 0);
  };

  const select = (name: string) => {
    onChange(name);
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === 'Escape') {
      setOpen(false);
    } else if (e.key === 'Tab' && open && matches.length === 1) {
      e.preventDefault();
      select(matches[0]);
    }
  };

  return (
    <div className="autocomplete-wrapper">
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => setOpen(false)}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete="off"
      />
      {open && (
        <ul className="autocomplete-list">
          {matches.map((name) => {
            const isSpecialty = specialtyShowNames.has(name.toLowerCase());
            return (
              <li
                key={name}
                // mousedown, not click, so it lands before the input's blur closes the list.
                onMouseDown={(e) => {
                  e.preventDefault();
                  select(name);
                }}
                className="autocomplete-item"
              >
                <span>{name}</span>
                <span className={isSpecialty ? 'specialty-show-badge' : 'dj-name-badge'}>
                  {isSpecialty ? 'Specialty Show' : 'DJ'}
                </span>
              </li>
            );
          })}
          {matches.length === 1 && <li className="autocomplete-hint">Press Tab to complete</li>}
        </ul>
      )}
    </div>
  );
};

export default DjNameAutocomplete;
