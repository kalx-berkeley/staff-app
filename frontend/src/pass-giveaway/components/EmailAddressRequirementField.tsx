import type { EmailAddressRequirement } from '../types';

const OPTIONS: { value: EmailAddressRequirement; label: string; hint: string }[] = [
  {
    value: 'none',
    label: "Don't include email addresses",
    hint: '',
  },
  {
    value: 'staff_passes',
    label: 'Staff pass winners only',
    hint: "Staff pass winners' email addresses are included. DJs don't ask on-air winners for one.",
  },
  {
    value: 'all',
    label: 'All winners (on-air and staff pass)',
    hint: "DJs must collect an email address from every on-air winner. Staff pass winners' email addresses are included too.",
  },
];

interface EmailAddressRequirementFieldProps {
  idPrefix: string;
  value: EmailAddressRequirement;
  onChange: (value: EmailAddressRequirement) => void;
  disabled?: boolean;
}

/** Which winners' email addresses a venue or promoter wants in the guest list. */
const EmailAddressRequirementField = ({
  idPrefix,
  value,
  onChange,
  disabled,
}: EmailAddressRequirementFieldProps) => {
  const hint = OPTIONS.find((o) => o.value === value)?.hint;
  return (
    <fieldset className="form-group radio-group">
      <legend>Winners' email addresses in guest list</legend>
      {OPTIONS.map((o) => (
        <label key={o.value} className="radio-label">
          <input
            type="radio"
            name={`${idPrefix}-email-address-requirement`}
            checked={value === o.value}
            onChange={() => onChange(o.value)}
            disabled={disabled}
          />
          {' '}{o.label}
        </label>
      ))}
      {hint && <span className="field-hint">{hint}</span>}
    </fieldset>
  );
};

export default EmailAddressRequirementField;
