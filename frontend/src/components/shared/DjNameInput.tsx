import { useState, useEffect, useRef } from 'react';
import { autocompleteAPI, specialtyShowsAPI } from '../../services/api';
import { useOnAirDj } from './useOnAirDj';

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
  const [specialtyShowNames, setSpecialtyShowNames] = useState<Set<string>>(new Set());
  const autocompleteRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    autocompleteAPI.getDJNames().then(setDjNames).catch(() => {});
    specialtyShowsAPI.list()
      .then((shows) => setSpecialtyShowNames(new Set(shows.map((s) => s.name.toLowerCase()))))
      .catch(() => {});
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

  const { currentDjName, mismatch, transitionNotice, dismissTransitionNotice } = useOnAirDj(
    value,
    selectName
  );

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
              {filteredDjNames.map((name) => {
                const isSpecialty = specialtyShowNames.has(name.toLowerCase());
                return (
                  <li
                    key={name}
                    onMouseDown={() => selectName(name)}
                    className="autocomplete-item"
                  >
                    <span>{name}</span>
                    <span className={isSpecialty ? 'specialty-show-badge' : 'dj-name-badge'}>
                      {isSpecialty ? 'Specialty Show' : 'DJ'}
                    </span>
                  </li>
                );
              })}
              {filteredDjNames.length === 1 && (
                <li className="autocomplete-hint">Press Tab to complete</li>
              )}
            </ul>
          )}
        </div>
      </div>
      {mismatch && currentDjName && (
        <div className="dj-name-mismatch-warning">
          This doesn't match the scheduled on-air DJ ({currentDjName}).{' '}
          <button
            type="button"
            className="btn-secondary"
            onClick={() => selectName(currentDjName)}
          >
            Use {currentDjName}
          </button>
        </div>
      )}
      {transitionNotice && (
        <div className="dj-name-transition-notice">
          {transitionNotice}
          <button
            type="button"
            className="dj-name-notice-dismiss"
            aria-label="Dismiss"
            onClick={dismissTransitionNotice}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
};

export default DjNameInput;
