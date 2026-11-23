import { useEffect, useState } from 'react';
import { venuesAPI } from '../../api';
import { PersonAutocomplete, extractPersonEmail } from '../../components';
import type { PromotionsStaffOption } from '../../types';

interface PromotionsRepsFieldProps {
  /** The hint under the heading: what the reps do. */
  hint: string;
  ownerEmails: string[];
  onChange: (ownerEmails: string[]) => void;
  disabled: boolean;
}

/** The KALX promotions reps picker on the venue and promoter forms. */
const PromotionsRepsField = ({ hint, ownerEmails, onChange, disabled }: PromotionsRepsFieldProps) => {
  const [input, setInput] = useState('');
  const [promotionsStaff, setPromotionsStaff] = useState<PromotionsStaffOption[]>([]);

  useEffect(() => {
    venuesAPI.listPromotionsStaff().then(setPromotionsStaff).catch(() => {});
  }, []);

  const nameFor = (email: string) => promotionsStaff.find((s) => s.email === email)?.name || email;

  const handleAdd = (rawInput: string) => {
    const email = extractPersonEmail(rawInput);
    if (email && !ownerEmails.includes(email)) {
      onChange([...ownerEmails, email]);
    }
    setInput('');
  };

  return (
    <div className="form-section">
      <h4>KALX Promotions Reps</h4>
      <p className="field-hint">{hint}</p>
      <div className="tag-input-row">
        <PersonAutocomplete
          value={input}
          onChange={setInput}
          onSubmit={handleAdd}
          options={promotionsStaff}
          placeholder="Add rep by name or email..."
          disabled={disabled}
          style={{ flex: 1 }}
        />
        <button
          type="button"
          onClick={() => handleAdd(input)}
          className="btn-secondary btn-small"
          disabled={disabled || !input.trim()}
        >
          Add
        </button>
      </div>
      {ownerEmails.length > 0 && (
        <ul className="tag-list">
          {ownerEmails.map((email) => (
            <li key={email} className="tag-item">
              <span>
                <a href={`mailto:${email}`}>{nameFor(email)}</a>
              </span>
              <button
                type="button"
                onClick={() => onChange(ownerEmails.filter((e) => e !== email))}
                className="tag-remove"
                disabled={disabled}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default PromotionsRepsField;
