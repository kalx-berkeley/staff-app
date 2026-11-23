import { emptyContact, contactHasText } from './formValues';
import type { ContactInput } from './formValues';

const FIELDS: { field: keyof ContactInput; type: string; placeholder: string }[] = [
  { field: 'name', type: 'text', placeholder: 'Name' },
  { field: 'title', type: 'text', placeholder: 'Title' },
  { field: 'email', type: 'email', placeholder: 'Email' },
  { field: 'phone', type: 'tel', placeholder: 'Phone' },
];

interface ContactsFieldProps {
  title: string;
  hint: string;
  contacts: ContactInput[];
  onChange: (contacts: ContactInput[]) => void;
  disabled: boolean;
}

/** The list of contact people on the venue and promoter forms. */
const ContactsField = ({ title, hint, contacts, onChange, disabled }: ContactsFieldProps) => {
  const handleChange = (idx: number, field: keyof ContactInput, value: string) => {
    onChange(contacts.map((c, i) => (i === idx ? { ...c, [field]: value || null } : c)));
  };

  const handleRemove = (idx: number) => {
    const remaining = contacts.filter((_, i) => i !== idx);
    onChange(remaining.length > 0 ? remaining : [emptyContact()]);
  };

  return (
    <div className="form-section">
      <h4>{title}</h4>
      <p className="field-hint">{hint}</p>
      {contacts.map((contact, idx) => (
        <div key={idx} className="contact-row">
          <div className="contact-fields">
            {FIELDS.map(({ field, type, placeholder }) => (
              <input
                key={field}
                type={type}
                placeholder={placeholder}
                value={contact[field] ?? ''}
                onChange={(e) => handleChange(idx, field, e.target.value)}
                disabled={disabled}
              />
            ))}
          </div>
          {(contacts.length > 1 || contactHasText(contact)) && (
            <button
              type="button"
              onClick={() => handleRemove(idx)}
              className="btn-secondary btn-small"
              disabled={disabled}
            >
              Remove
            </button>
          )}
        </div>
      ))}
      {contactHasText(contacts[0]) && (
        <button
          type="button"
          onClick={() => onChange([...contacts, emptyContact()])}
          className="btn-secondary btn-small"
          disabled={disabled}
        >
          + Add Another Contact
        </button>
      )}
    </div>
  );
};

export default ContactsField;
