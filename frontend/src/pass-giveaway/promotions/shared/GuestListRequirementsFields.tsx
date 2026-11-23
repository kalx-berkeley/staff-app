import type { ReactNode } from 'react';
import { EmailAddressRequirementField, HoldCloseNotificationsHint } from '../../components';
import type { GuestListRequirements } from './formValues';

interface GuestListRequirementsFieldsProps {
  idPrefix: string;
  /** The hint under the heading: what the settings apply to. */
  intro: ReactNode;
  value: GuestListRequirements;
  onChange: (value: GuestListRequirements) => void;
  disabled: boolean;
}

const GuestListRequirementsFields = ({
  idPrefix,
  intro,
  value,
  onChange,
  disabled,
}: GuestListRequirementsFieldsProps) => {
  const checkbox = (field: Exclude<keyof GuestListRequirements, 'email_address_requirement'>, label: string) => (
    <label>
      <input
        type="checkbox"
        checked={value[field]}
        onChange={(e) => onChange({ ...value, [field]: e.target.checked })}
        disabled={disabled}
      />
      {' '}{label}
    </label>
  );

  return (
    <div className="form-section">
      <h4>Guest List Requirements (optional)</h4>
      <p className="field-hint">{intro}</p>
      <div className="form-group form-group-checkbox">
        {checkbox('requires_phone_number', "Include winner's phone number in guest list")}
      </div>
      <EmailAddressRequirementField
        idPrefix={idPrefix}
        value={value.email_address_requirement}
        onChange={(email_address_requirement) => onChange({ ...value, email_address_requirement })}
        disabled={disabled}
      />
      <div className="form-group form-group-checkbox">
        {checkbox('staff_guest_requires_name', 'Require staff guests to be listed by name')}
        <span className="field-hint">
          When checked, staff members bringing a +1 guest must provide the guest's name,
          and the guest list will show the guest's name as a separate entry. When unchecked,
          the list shows "John Doe and a guest" without requiring the guest's name.
        </span>
      </div>
      <div className="form-group form-group-checkbox">
        {checkbox('hold_close_notifications', 'Wait for me to send close notifications')}
        <HoldCloseNotificationsHint />
      </div>
      <div className="form-group form-group-checkbox">
        {checkbox('track_pass_call_in', "Track when I've called in the passes")}
        <span className="field-hint">
          Closed shows get a Mark Passes Called In button next to the guest list, so you can keep
          track of which ones you've sent to the venue.
        </span>
      </div>
    </div>
  );
};

export default GuestListRequirementsFields;
