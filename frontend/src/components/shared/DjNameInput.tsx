import { useState, useEffect, useRef } from 'react';
import { autocompleteAPI } from '../../services/api';

export const DJ_NAME_KEY = 'kalx_dj_name';

interface DjNameInputProps {
  value: string;
  onChange: (name: string) => void;
  id?: string;
}

const DjNameInput = ({ value, onChange, id = 'dj-name-input' }: DjNameInputProps) => {
  const [djNames, setDjNames] = useState<string[]>([]);
  const [filteredDjNames, setFilteredDjNames] = useState<string[]>([]);
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const autocompleteRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    autocompleteAPI.getDJNames().then(setDjNames).catch(() => {});
  }, []);

  const handleChange = (newValue: string) => {
    localStorage.setItem(DJ_NAME_KEY, newValue.trim());
    onChange(newValue);
    if (newValue.trim()) {
      const filtered = djNames.filter((name) =>
        name.toLowerCase().includes(newValue.toLowerCase())
      );
      setFilteredDjNames(filtered);
      setShowAutocomplete(filtered.length > 0);
    } else {
      setShowAutocomplete(false);
    }
  };

  const selectName = (name: string) => {
    localStorage.setItem(DJ_NAME_KEY, name);
    onChange(name);
    setShowAutocomplete(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === 'Escape') {
      setShowAutocomplete(false);
    } else if (e.key === 'Tab' && filteredDjNames.length === 1) {
      e.preventDefault();
      selectName(filteredDjNames[0]);
    }
  };

  return (
    <div className="dj-name-section">
      <div className="form-group-inline">
        <label htmlFor={id}>DJ Name:</label>
        <div className="autocomplete-wrapper" style={{ flex: 1, minWidth: 150, maxWidth: 320 }}>
          <input
            id={id}
            type="text"
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => setTimeout(() => setShowAutocomplete(false), 200)}
            placeholder="Enter your DJ name"
            autoComplete="off"
          />
          {showAutocomplete && (
            <ul className="autocomplete-list" ref={autocompleteRef}>
              {filteredDjNames.map((name) => (
                <li
                  key={name}
                  onMouseDown={() => selectName(name)}
                  className="autocomplete-item"
                >
                  {name}
                </li>
              ))}
              {filteredDjNames.length === 1 && (
                <li className="autocomplete-hint">Press Tab to complete</li>
              )}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

export default DjNameInput;
