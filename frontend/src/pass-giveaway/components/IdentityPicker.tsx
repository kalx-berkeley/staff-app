import { useEffect, useRef, useState } from 'react';
import { specialtyShowLabel } from '../utils';
import type { Identity } from '../types';

/** "DJ", "Specialty Music Show" or "Talk & Info Show". */
const identityKindLabel = (identity: Identity): string =>
  identity.kind === 'persona' ? 'DJ' : specialtyShowLabel(identity.kind);

const identityKey = (identity: Identity): string =>
  identity.persona_id != null ? `p${identity.persona_id}` : `s${identity.specialty_show_id}`;

interface IdentityPickerProps {
  id?: string;
  /** What can be picked (from `passesAPI.getPreassignIdentities` or similar). */
  options: Identity[];
  value: Identity | null;
  onChange: (identity: Identity | null) => void;
  disabled?: boolean;
  placeholder?: string;
  'aria-label'?: string;
}

/**
 * A type-ahead for picking a DJ persona or a show from a fixed list. Typing
 * filters the list by name (and, for personas, the staff member's name).
 * Only a picked option counts: typed text that doesn't match one leaves the
 * value empty, and is cleared when the field loses focus.
 */
const IdentityPicker = ({
  id,
  options,
  value,
  onChange,
  disabled,
  placeholder = 'DJ or show',
  'aria-label': ariaLabel,
}: IdentityPickerProps) => {
  const [text, setText] = useState(value?.name ?? '');
  const [open, setOpen] = useState(false);
  // Follow a value set from outside (a suggestion, or a reset)
  const [shownValue, setShownValue] = useState<Identity | null>(value);
  if (value !== shownValue) {
    setShownValue(value);
    setText(value?.name ?? '');
  }
  // The blur timeout reads this, since a click on an option lands after the
  // blur but before the timeout fires
  const shownValueRef = useRef(shownValue);
  useEffect(() => {
    shownValueRef.current = shownValue;
  }, [shownValue]);

  const query = text.trim().toLowerCase();
  const matches = query
    ? options.filter(
        (o) =>
          o.name.toLowerCase().includes(query) ||
          (o.staff_name ?? '').toLowerCase().includes(query)
      )
    : options;

  const select = (identity: Identity) => {
    setText(identity.name);
    setShownValue(identity);
    setOpen(false);
    onChange(identity);
  };

  const handleChange = (newText: string) => {
    setText(newText);
    setOpen(true);
    // An exact name match picks it, so typing a full name works too
    const exact = options.filter(
      (o) => o.name.toLowerCase() === newText.trim().toLowerCase()
    );
    const picked = exact.length === 1 ? exact[0] : null;
    setShownValue(picked);
    onChange(picked);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setOpen(false);
    } else if ((e.key === 'Tab' || e.key === 'Enter') && open && matches.length === 1) {
      e.preventDefault();
      select(matches[0]);
    }
  };

  return (
    <div className="autocomplete-wrapper">
      <input
        id={id}
        type="text"
        value={text}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        onBlur={() =>
          setTimeout(() => {
            setOpen(false);
            // Text that isn't a picked DJ or show can't be saved, so don't
            // leave it in the box looking like a choice
            setText((current) => (shownValueRef.current ? current : ''));
          }, 150)
        }
        disabled={disabled}
        placeholder={placeholder}
        aria-label={ariaLabel}
        autoComplete="off"
      />
      {open && matches.length > 0 && (
        <ul className="autocomplete-list">
          {matches.map((option) => (
            <li
              key={identityKey(option)}
              onMouseDown={() => select(option)}
              className="autocomplete-item"
            >
              <span>
                {option.name}
                {option.staff_name && (
                  <span className="field-hint"> ({option.staff_name})</span>
                )}
              </span>
              <span
                className={option.kind === 'persona' ? 'dj-name-badge' : 'specialty-show-badge'}
              >
                {identityKindLabel(option)}
              </span>
            </li>
          ))}
          {matches.length === 1 && (
            <li className="autocomplete-hint">Press Tab to complete</li>
          )}
        </ul>
      )}
    </div>
  );
};

export default IdentityPicker;
