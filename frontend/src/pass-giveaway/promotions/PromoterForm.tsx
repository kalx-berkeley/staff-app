import { useState, useEffect } from 'react';
import { promotersAPI } from '../api';
import { Tooltip } from '../components';
import type { PromoterResponse, PromoterCreate } from '../types';
import type { APIError, ValidationError } from '../../common/types';
import EntityFormPage from './shared/EntityFormPage';
import GuestListRequirementsFields from './shared/GuestListRequirementsFields';
import PromotionsRepsField from './shared/PromotionsRepsField';
import ContactsField from './shared/ContactsField';
import {
  DEFAULT_GUEST_LIST_REQUIREMENTS,
  NEW_CONTACT_ROWS,
  contactRowsFrom,
  contactsToSave,
  guestListRequirementsFrom,
} from './shared/formValues';

interface PromoterFormProps {
  promoter: PromoterResponse | null;
  onClose: () => void;
  onSuccess: () => void;
  onDelete?: () => void;
}

const PromoterForm = ({ promoter, onClose, onSuccess, onDelete }: PromoterFormProps) => {
  const [name, setName] = useState('');
  const [showSourcingInstructions, setShowSourcingInstructions] = useState('');
  const [passCallInstructions, setPassCallInstructions] = useState('');
  const [guestList, setGuestList] = useState(DEFAULT_GUEST_LIST_REQUIREMENTS);
  const [ownerEmails, setOwnerEmails] = useState<string[]>([]);
  const [contacts, setContacts] = useState(NEW_CONTACT_ROWS);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    if (promoter) {
      setName(promoter.name);
      setShowSourcingInstructions(promoter.show_sourcing_instructions || '');
      setPassCallInstructions(promoter.pass_call_instructions || '');
      setGuestList(guestListRequirementsFrom(promoter));
      setOwnerEmails(promoter.owner_emails || []);
      setContacts(contactRowsFrom(promoter.contacts));
    }
  }, [promoter]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!name.trim()) newErrors.name = 'Promoter name is required';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);
    if (!validateForm()) return;
    setSubmitting(true);

    try {
      const data: PromoterCreate = {
        name: name.trim(),
        show_sourcing_instructions: showSourcingInstructions.trim() || null,
        pass_call_instructions: passCallInstructions.trim() || null,
        ...guestList,
        owner_emails: ownerEmails,
        contacts: contactsToSave(contacts),
      };
      if (promoter) {
        await promotersAPI.update(promoter.id, data);
      } else {
        await promotersAPI.create(data);
      }
      onSuccess();
    } catch (err) {
      const error = err as APIError;
      if (typeof error.detail === 'string') {
        setApiError(error.detail);
      } else if (Array.isArray(error.detail)) {
        const fieldErrors: Record<string, string> = {};
        error.detail.forEach((validationError: ValidationError) => {
          const field = validationError.loc[validationError.loc.length - 1];
          fieldErrors[field.toString()] = validationError.msg;
        });
        setErrors(fieldErrors);
      } else {
        setApiError('Failed to save promoter');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <EntityFormPage
      noun="Promoter"
      savedName={promoter?.name ?? null}
      apiError={apiError}
      submitting={submitting}
      onSubmit={handleSubmit}
      onCancel={onClose}
      onDelete={
        promoter
          ? async () => {
              await promotersAPI.delete(promoter.id);
              onDelete?.();
            }
          : undefined
      }
    >
      <div className="form-group">
        <label htmlFor="promoter-name">
          Promoter Name <span className="required">*</span>
        </label>
        <input
          type="text"
          id="promoter-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={errors.name ? 'input-error' : ''}
          disabled={submitting}
        />
        {errors.name && <span className="field-error">{errors.name}</span>}
      </div>

      <div className="form-group">
        <div className="label-with-help">
          <label htmlFor="promoter-sourcing-instructions">Promoter Show Sourcing Instructions</label>
          <Tooltip text="How the KALX promotions rep decides which of this promoter's shows KALX will promote. For example, we may be free to pick any shows we like, or the promoter may email the rep a month ahead with the shows they want promoted. Include when to check, where to look and who to ask." />
        </div>
        <textarea
          id="promoter-sourcing-instructions"
          value={showSourcingInstructions}
          onChange={(e) => setShowSourcingInstructions(e.target.value)}
          disabled={submitting}
          rows={3}
          placeholder="e.g. We can pick any shows we want, or the promoter emails us a month ahead with the shows to promote..."
        />
      </div>

      <div className="form-group">
        <div className="label-with-help">
          <label htmlFor="promoter-pass-instructions">Promoter Call-In Instructions</label>
          <Tooltip text="Notes for promotions staff on how to call in the guest list to this promoter. Shown only on this form." />
        </div>
        <textarea
          id="promoter-pass-instructions"
          value={passCallInstructions}
          onChange={(e) => setPassCallInstructions(e.target.value)}
          disabled={submitting}
          rows={3}
          placeholder="How to call in the guest list to this promoter..."
        />
      </div>

      <GuestListRequirementsFields
        idPrefix="promoter"
        intro={
          <>
            These settings control what information appears in the guest list when a show with this
            promoter closes. They're all optional. Leave every box unchecked if the promoter doesn't
            need any of them.
          </>
        }
        value={guestList}
        onChange={setGuestList}
        disabled={submitting}
      />

      <PromotionsRepsField
        hint="Promotions staff members who own the relationship with this promoter and receive pass winner notifications for their shows. Type a name or email address."
        ownerEmails={ownerEmails}
        onChange={setOwnerEmails}
        disabled={submitting}
      />

      <ContactsField
        title="Contacts"
        hint="Contact people at this promoter (for reference)."
        contacts={contacts}
        onChange={setContacts}
        disabled={submitting}
      />
    </EntityFormPage>
  );
};

export default PromoterForm;
