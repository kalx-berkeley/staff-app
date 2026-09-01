import { useState, useEffect } from 'react';
import { promotersAPI, adminAPI } from '../../services/api';
import type {
  PromoterResponse,
  PromoterCreate,
  PromoterUpdate,
  PromoterContactCreate,
  APIError,
  ValidationError,
} from '../../types';

interface PromoterFormProps {
  promoter: PromoterResponse | null;
  onClose: () => void;
  onSuccess: () => void;
  onDelete?: () => void;
  asPage?: boolean;
}

const emptyContact = (): PromoterContactCreate => ({
  name: null,
  title: null,
  email: null,
  phone: null,
});

const PromoterForm = ({ promoter, onClose, onSuccess, onDelete, asPage = false }: PromoterFormProps) => {
  const [name, setName] = useState('');
  const [passCallInstructions, setPassCallInstructions] = useState('');
  const [requiresPhoneNumber, setRequiresPhoneNumber] = useState(false);
  const [requiresEmailAddress, setRequiresEmailAddress] = useState(false);
  const [staffGuestRequiresName, setStaffGuestRequiresName] = useState(false);
  const [ownerEmails, setOwnerEmails] = useState<string[]>([]);
  const [newOwnerEmail, setNewOwnerEmail] = useState('');
  const [emailToName, setEmailToName] = useState<Record<string, string>>({});
  const [contacts, setContacts] = useState<PromoterContactCreate[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (promoter) {
      setName(promoter.name);
      setPassCallInstructions(promoter.pass_call_instructions || '');
      setRequiresPhoneNumber(promoter.requires_phone_number ?? false);
      setRequiresEmailAddress(promoter.requires_email_address ?? false);
      setStaffGuestRequiresName(promoter.staff_guest_requires_name ?? false);
      setOwnerEmails(promoter.owner_emails || []);
      setContacts(
        promoter.contacts.length > 0
          ? promoter.contacts.map((c) => ({
              name: c.name ?? null,
              title: c.title ?? null,
              email: c.email ?? null,
              phone: c.phone ?? null,
            }))
          : []
      );
    }
  }, [promoter]);

  useEffect(() => {
    adminAPI.listUsers().then((users) => {
      const map: Record<string, string> = {};
      users.forEach((u) => { map[u.email] = u.name; });
      setEmailToName(map);
    }).catch(() => {});
  }, []);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!name.trim()) newErrors.name = 'Promoter name is required';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleAddOwner = () => {
    const email = newOwnerEmail.trim();
    if (email && !ownerEmails.includes(email)) {
      setOwnerEmails([...ownerEmails, email]);
      setNewOwnerEmail('');
    }
  };

  const handleRemoveOwner = (email: string) => {
    setOwnerEmails(ownerEmails.filter((e) => e !== email));
  };

  const handleAddContact = () => {
    setContacts([...contacts, emptyContact()]);
  };

  const handleRemoveContact = (idx: number) => {
    setContacts(contacts.filter((_, i) => i !== idx));
  };

  const handleContactChange = (idx: number, field: keyof PromoterContactCreate, value: string) => {
    setContacts(
      contacts.map((c, i) => (i === idx ? { ...c, [field]: value || null } : c))
    );
  };

  const handleDelete = async () => {
    if (!promoter) return;
    setDeleting(true);
    setApiError(null);
    try {
      await promotersAPI.delete(promoter.id);
      onDelete?.();
    } catch (err) {
      const error = err as APIError;
      setShowDeleteConfirm(false);
      setApiError(typeof error.detail === 'string' ? error.detail : 'Failed to delete promoter');
    } finally {
      setDeleting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);
    if (!validateForm()) return;
    setSubmitting(true);

    try {
      if (promoter) {
        const updateData: PromoterUpdate = {
          name: name.trim(),
          pass_call_instructions: passCallInstructions.trim() || null,
          requires_phone_number: requiresPhoneNumber,
          requires_email_address: requiresEmailAddress,
          staff_guest_requires_name: staffGuestRequiresName,
          owner_emails: ownerEmails,
          contacts,
        };
        await promotersAPI.update(promoter.id, updateData);
      } else {
        const createData: PromoterCreate = {
          name: name.trim(),
          pass_call_instructions: passCallInstructions.trim() || null,
          requires_phone_number: requiresPhoneNumber,
          requires_email_address: requiresEmailAddress,
          staff_guest_requires_name: staffGuestRequiresName,
          owner_emails: ownerEmails,
          contacts,
        };
        await promotersAPI.create(createData);
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

  const deleteConfirmModal = showDeleteConfirm && promoter && (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h3>Delete Promoter</h3>
        </div>
        <div className="modal-body">
          <p>
            Are you sure you want to delete <strong>{promoter.name}</strong>?
          </p>
          <p>
            This promoter will be hidden from all lists and dropdowns. It can be restored later
            from the Admin page.
          </p>
        </div>
        <div className="form-actions">
          <button
            type="button"
            onClick={() => setShowDeleteConfirm(false)}
            className="btn-secondary"
            disabled={deleting}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="btn-danger"
            disabled={deleting}
          >
            {deleting ? 'Deleting...' : 'Delete Promoter'}
          </button>
        </div>
      </div>
    </div>
  );

  const form = (
    <form onSubmit={handleSubmit} className="venue-form">
      {apiError && <div className="error-message">{apiError}</div>}

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
        <label htmlFor="promoter-pass-instructions">Pass Call Instructions</label>
        <textarea
          id="promoter-pass-instructions"
          value={passCallInstructions}
          onChange={(e) => setPassCallInstructions(e.target.value)}
          disabled={submitting}
          rows={3}
          placeholder="Instructions for DJs when calling in pass claims..."
        />
      </div>

      <div className="form-section">
        <h4>Guest List Requirements</h4>
        <p className="field-hint">
          These settings control what information appears in the guest list when a show with this promoter closes.
        </p>
        <div className="form-group form-group-checkbox">
          <label>
            <input
              type="checkbox"
              checked={requiresPhoneNumber}
              onChange={(e) => setRequiresPhoneNumber(e.target.checked)}
              disabled={submitting}
            />
            {' '}Include winner's phone number in guest list
          </label>
        </div>
        <div className="form-group form-group-checkbox">
          <label>
            <input
              type="checkbox"
              checked={requiresEmailAddress}
              onChange={(e) => setRequiresEmailAddress(e.target.checked)}
              disabled={submitting}
            />
            {' '}Require and include winner's email address in guest list
          </label>
          {requiresEmailAddress && (
            <span className="field-hint">
              DJs will be prompted to collect an email address from on-air winners. Staff claimants' email addresses are collected automatically.
            </span>
          )}
        </div>
        <div className="form-group form-group-checkbox">
          <label>
            <input
              type="checkbox"
              checked={staffGuestRequiresName}
              onChange={(e) => setStaffGuestRequiresName(e.target.checked)}
              disabled={submitting}
            />
            {' '}Require staff guests to be listed by name
          </label>
          <span className="field-hint">
            When checked, staff members bringing a +1 guest must provide the guest's name,
            and the guest list will show the guest's name as a separate entry.
          </span>
        </div>
      </div>

      <fieldset className="form-fieldset">
        <legend>Owners</legend>
        <p className="field-hint">
          Promotions staff members who own the relationship with this promoter and receive pass
          winner notifications for their shows.
        </p>
        {ownerEmails.map((email) => (
          <div key={email} className="owner-row">
            <span className="owner-email">
              {emailToName[email] ? `${emailToName[email]} (${email})` : email}
            </span>
            <button
              type="button"
              onClick={() => handleRemoveOwner(email)}
              className="btn-secondary btn-small"
              disabled={submitting}
            >
              Remove
            </button>
          </div>
        ))}
        <div className="owner-add-row">
          <input
            type="email"
            placeholder="Add owner by email"
            value={newOwnerEmail}
            onChange={(e) => setNewOwnerEmail(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); handleAddOwner(); }
            }}
            disabled={submitting}
          />
          <button
            type="button"
            onClick={handleAddOwner}
            className="btn-secondary btn-small"
            disabled={submitting || !newOwnerEmail.trim()}
          >
            Add
          </button>
        </div>
      </fieldset>

      <fieldset className="form-fieldset">
        <legend>Contacts</legend>
        <p className="field-hint">Contact people at this promoter (for reference).</p>
        {contacts.map((contact, idx) => (
          <div key={idx} className="contact-row">
            <div className="contact-fields">
              <input
                type="text"
                placeholder="Name"
                value={contact.name ?? ''}
                onChange={(e) => handleContactChange(idx, 'name', e.target.value)}
                disabled={submitting}
              />
              <input
                type="text"
                placeholder="Title"
                value={contact.title ?? ''}
                onChange={(e) => handleContactChange(idx, 'title', e.target.value)}
                disabled={submitting}
              />
              <input
                type="email"
                placeholder="Email"
                value={contact.email ?? ''}
                onChange={(e) => handleContactChange(idx, 'email', e.target.value)}
                disabled={submitting}
              />
              <input
                type="tel"
                placeholder="Phone"
                value={contact.phone ?? ''}
                onChange={(e) => handleContactChange(idx, 'phone', e.target.value)}
                disabled={submitting}
              />
            </div>
            <button
              type="button"
              onClick={() => handleRemoveContact(idx)}
              className="btn-secondary btn-small"
              disabled={submitting}
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={handleAddContact}
          className="btn-secondary btn-small"
          disabled={submitting}
        >
          Add Contact
        </button>
      </fieldset>

      <div className="form-actions">
        <button type="button" onClick={onClose} className="btn-secondary" disabled={submitting}>
          Cancel
        </button>
        {promoter && onDelete && (
          <button
            type="button"
            onClick={() => setShowDeleteConfirm(true)}
            className="btn-danger"
            disabled={submitting}
          >
            Delete
          </button>
        )}
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? 'Saving...' : promoter ? 'Update Promoter' : 'Create Promoter'}
        </button>
      </div>
    </form>
  );

  if (asPage) {
    return (
      <div className="venue-form-page">
        {deleteConfirmModal}
        <div className="venue-form-header">
          <h2>{promoter ? `Edit Promoter: ${promoter.name}` : 'New Promoter'}</h2>
        </div>
        {form}
      </div>
    );
  }

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        {deleteConfirmModal}
        <div className="modal-header">
          <h3>{promoter ? `Edit Promoter: ${promoter.name}` : 'New Promoter'}</h3>
          <button className="btn-close" onClick={onClose}>×</button>
        </div>
        {form}
      </div>
    </div>
  );
};

export default PromoterForm;
