import { useState, useEffect, useRef } from 'react';
import { venuesAPI, adminAPI, promotersAPI } from '../../services/api';
import { Tooltip } from '../shared';
import type {
  VenueResponse,
  VenueCreate,
  VenueUpdate,
  VenueContactCreate,
  AgeRestriction,
  APIError,
  ValidationError,
  PromoterResponse,
} from '../../types';

const venueLogoUrl = (id: number) => `/pass-giveaway/api/venues/${id}/logo`;

interface VenueFormProps {
  venue: VenueResponse | null;
  onClose: () => void;
  onSuccess: () => void;
  onDelete?: () => void;
  asPage?: boolean;
}

const emptyContact = (): VenueContactCreate => ({
  name: null,
  title: null,
  email: null,
  phone: null,
});

const VenueForm = ({ venue, onClose, onSuccess, onDelete, asPage = false }: VenueFormProps) => {
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [passCallInstructions, setPassCallInstructions] = useState('');
  const [winFrequencyDays, setWinFrequencyDays] = useState('');
  const [defaultWheelchair, setDefaultWheelchair] = useState<'' | 'true' | 'false'>('');
  const [defaultAgeRestriction, setDefaultAgeRestriction] = useState<'' | AgeRestriction>('');
  const [defaultNumPassPairs, setDefaultNumPassPairs] = useState('');
  const [requiresPhoneNumber, setRequiresPhoneNumber] = useState(false);
  const [requiresEmailAddress, setRequiresEmailAddress] = useState(false);
  const [staffGuestRequiresName, setStaffGuestRequiresName] = useState(false);
  const [defaultLotteryEnabled, setDefaultLotteryEnabled] = useState(false);
  const [defaultLotteryWindowHours, setDefaultLotteryWindowHours] = useState('24');
  const [defaultDjPreassignProhibitionDays, setDefaultDjPreassignProhibitionDays] = useState('');
  const [defaultCloseHoursBeforeShow, setDefaultCloseHoursBeforeShow] = useState('');
  const [promoterId, setPromoterId] = useState<number | null>(null);
  const [showsHaveExternalPromoter, setShowsHaveExternalPromoter] = useState(false);
  const [promotersList, setPromotersList] = useState<PromoterResponse[]>([]);
  const [ownerEmails, setOwnerEmails] = useState<string[]>([]);
  const [newOwnerEmail, setNewOwnerEmail] = useState('');
  const [emailToName, setEmailToName] = useState<Record<string, string>>({});
  const [contacts, setContacts] = useState<VenueContactCreate[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [hasLogo, setHasLogo] = useState(false);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [pendingLogoFile, setPendingLogoFile] = useState<File | null>(null);
  const [pendingLogoDelete, setPendingLogoDelete] = useState(false);
  const [logoKey, setLogoKey] = useState(0);
  const logoInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (venue) {
      setName(venue.name);
      setAddress(venue.address);
      setPassCallInstructions(venue.pass_call_instructions || '');
      setWinFrequencyDays(venue.win_frequency_days != null ? String(venue.win_frequency_days) : '');
      setDefaultWheelchair(
        venue.default_wheelchair_accessible === true ? 'true'
        : venue.default_wheelchair_accessible === false ? 'false'
        : ''
      );
      setDefaultAgeRestriction((venue.default_age_restriction ?? '') as '' | AgeRestriction);
      setDefaultNumPassPairs(venue.default_num_pass_pairs != null ? String(venue.default_num_pass_pairs) : '');
      setRequiresPhoneNumber(venue.requires_phone_number ?? false);
      setRequiresEmailAddress(venue.requires_email_address ?? false);
      setStaffGuestRequiresName(venue.staff_guest_requires_name ?? false);
      setDefaultLotteryEnabled(venue.default_lottery_enabled ?? false);
      setDefaultLotteryWindowHours(String(venue.default_lottery_window_hours ?? 24));
      setDefaultDjPreassignProhibitionDays(
        venue.default_dj_preassign_prohibition_days != null
          ? String(venue.default_dj_preassign_prohibition_days)
          : ''
      );
      setDefaultCloseHoursBeforeShow(
        venue.default_close_hours_before_show != null
          ? String(venue.default_close_hours_before_show)
          : ''
      );
      setOwnerEmails(venue.owner_emails || []);
      setContacts(
        venue.contacts.length > 0
          ? venue.contacts.map((c) => ({
              name: c.name ?? null,
              title: c.title ?? null,
              email: c.email ?? null,
              phone: c.phone ?? null,
            }))
          : []
      );
      setPromoterId(venue.promoter_id ?? null);
      setShowsHaveExternalPromoter(venue.shows_have_external_promoter ?? false);
      setHasLogo(venue.has_logo);
      setLogoPreview(null);
      setPendingLogoFile(null);
      setPendingLogoDelete(false);
      setLogoKey((k) => k + 1);
    }
  }, [venue]);

  useEffect(() => {
    adminAPI.listUsers().then((users) => {
      const map: Record<string, string> = {};
      users.forEach((u) => { map[u.email] = u.name; });
      setEmailToName(map);
    }).catch(() => {});
    promotersAPI.list().then(setPromotersList).catch(() => {});
  }, []);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!name.trim()) newErrors.name = 'Venue name is required';
    if (!address.trim()) newErrors.address = 'Address is required';
    if (winFrequencyDays.trim() && (isNaN(Number(winFrequencyDays)) || Number(winFrequencyDays) < 1)) {
      newErrors.winFrequencyDays = 'Must be a positive number';
    }
    if (defaultNumPassPairs.trim() && (isNaN(Number(defaultNumPassPairs)) || Number(defaultNumPassPairs) < 1 || Number(defaultNumPassPairs) > 5)) {
      newErrors.defaultNumPassPairs = 'Must be between 1 and 5';
    }
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

  const handleContactChange = (idx: number, field: keyof VenueContactCreate, value: string) => {
    setContacts(
      contacts.map((c, i) => (i === idx ? { ...c, [field]: value || null } : c))
    );
  };

  const handleLogoFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingLogoFile(file);
    setPendingLogoDelete(false);
    const url = URL.createObjectURL(file);
    setLogoPreview(url);
  };

  const handleLogoRemove = () => {
    setPendingLogoFile(null);
    setLogoPreview(null);
    setPendingLogoDelete(true);
    setLogoKey((k) => k + 1);
  };

  const handleDelete = async () => {
    if (!venue) return;
    setDeleting(true);
    setApiError(null);
    try {
      await venuesAPI.delete(venue.id);
      onDelete?.();
    } catch (err) {
      const error = err as APIError;
      setShowDeleteConfirm(false);
      setApiError(typeof error.detail === 'string' ? error.detail : 'Failed to delete venue');
    } finally {
      setDeleting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);
    if (!validateForm()) return;
    setSubmitting(true);

    const winDays = winFrequencyDays.trim() ? Number(winFrequencyDays) : null;
    const instructions = passCallInstructions.trim() || null;
    const defaultWheelchairValue = defaultWheelchair === 'true' ? true : defaultWheelchair === 'false' ? false : null;
    const defaultAgeValue = (defaultAgeRestriction || null) as AgeRestriction | null;
    const defaultNumPassPairsValue = defaultNumPassPairs.trim() ? Number(defaultNumPassPairs) : null;
    const defaultDjPreassignProhibitionDaysValue = defaultDjPreassignProhibitionDays.trim()
      ? Number(defaultDjPreassignProhibitionDays)
      : null;
    const defaultCloseHoursBeforeShowValue = defaultCloseHoursBeforeShow.trim()
      ? Number(defaultCloseHoursBeforeShow)
      : null;

    try {
      let savedVenue: VenueResponse;
      if (venue) {
        const updateData: VenueUpdate = {
          name: name.trim(),
          address: address.trim(),
          pass_call_instructions: instructions,
          win_frequency_days: winDays,
          default_wheelchair_accessible: defaultWheelchairValue,
          default_age_restriction: defaultAgeValue,
          default_num_pass_pairs: defaultNumPassPairsValue,
          requires_phone_number: requiresPhoneNumber,
          requires_email_address: requiresEmailAddress,
          staff_guest_requires_name: staffGuestRequiresName,
          default_lottery_enabled: defaultLotteryEnabled,
          default_lottery_window_hours: defaultLotteryEnabled ? (parseInt(defaultLotteryWindowHours) || 24) : 24,
          default_dj_preassign_prohibition_days: defaultDjPreassignProhibitionDaysValue,
          default_close_hours_before_show: defaultCloseHoursBeforeShowValue,
          promoter_id: promoterId,
          shows_have_external_promoter: showsHaveExternalPromoter,
          owner_emails: ownerEmails,
          contacts,
        };
        savedVenue = await venuesAPI.update(venue.id, updateData);
      } else {
        const createData: VenueCreate = {
          name: name.trim(),
          address: address.trim(),
          pass_call_instructions: instructions,
          win_frequency_days: winDays,
          default_wheelchair_accessible: defaultWheelchairValue,
          default_age_restriction: defaultAgeValue,
          default_num_pass_pairs: defaultNumPassPairsValue,
          requires_phone_number: requiresPhoneNumber,
          requires_email_address: requiresEmailAddress,
          staff_guest_requires_name: staffGuestRequiresName,
          default_lottery_enabled: defaultLotteryEnabled,
          default_lottery_window_hours: defaultLotteryEnabled ? (parseInt(defaultLotteryWindowHours) || 24) : 24,
          default_dj_preassign_prohibition_days: defaultDjPreassignProhibitionDaysValue,
          default_close_hours_before_show: defaultCloseHoursBeforeShowValue,
          promoter_id: promoterId,
          shows_have_external_promoter: showsHaveExternalPromoter,
          owner_emails: ownerEmails,
          contacts,
        };
        savedVenue = await venuesAPI.create(createData);
      }

      if (pendingLogoFile) {
        await venuesAPI.uploadLogo(savedVenue.id, pendingLogoFile);
      } else if (pendingLogoDelete && (venue?.has_logo)) {
        await venuesAPI.deleteLogo(savedVenue.id);
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
        setApiError('Failed to save venue');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const deleteConfirmModal = showDeleteConfirm && venue && (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h3>Delete Venue</h3>
        </div>
        <div className="modal-body">
          <p>
            Are you sure you want to delete <strong>{venue.name}</strong>?
          </p>
          <p>
            This venue will be hidden from all lists and dropdowns. It can be restored later
            from the Admin page.
          </p>
          <p className="field-hint">
            Note: venues with published shows must have those shows closed before deletion.
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
            {deleting ? 'Deleting...' : 'Delete Venue'}
          </button>
        </div>
      </div>
    </div>
  );

  const form = (
    <form onSubmit={handleSubmit} className="venue-form">
      {apiError && <div className="error-message">{apiError}</div>}

          <div className="form-group">
            <label htmlFor="venue-name">
              Venue Name <span className="required">*</span>
            </label>
            <input
              type="text"
              id="venue-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={errors.name ? 'input-error' : ''}
              disabled={submitting}
            />
            {errors.name && <span className="field-error">{errors.name}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="venue-address">
              Address <span className="required">*</span>
            </label>
            <textarea
              id="venue-address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className={errors.address ? 'input-error' : ''}
              disabled={submitting}
              rows={2}
            />
            {errors.address && <span className="field-error">{errors.address}</span>}
            {(/\bCA\b/.test(address) || /\b\d{5}\b/.test(address)) && (
              <span className="field-warning">
                This address appears to include the state (&ldquo;CA&rdquo;) or a zip code.
                Please remove these — the DJ reads this address on air and the state and zip code aren&apos;t needed.
              </span>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="venue-promoter">Default Promoter</label>
            <select
              id="venue-promoter"
              value={promoterId ?? ''}
              onChange={(e) => setPromoterId(e.target.value ? Number(e.target.value) : null)}
              disabled={submitting}
            >
              <option value="">Venue is its own promoter</option>
              {promotersList.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <span className="field-hint">
              When set, pass winner names for shows at this venue are sent to the promoter's owners
              rather than this venue's owners.
            </span>
          </div>

          <div className="form-group form-group-checkbox">
            <label>
              <input
                type="checkbox"
                checked={showsHaveExternalPromoter}
                onChange={(e) => setShowsHaveExternalPromoter(e.target.checked)}
                disabled={submitting}
              />
              {' '}Shows at this venue can have a promoter different from the venue
            </label>
            <span className="field-hint">
              When checked, a promoter selection field appears in the new show form whenever this
              venue is selected, allowing individual shows to be assigned a different promoter.
            </span>
          </div>

          <div className="form-group">
            <div className="label-with-help">
            <label htmlFor="venue-pass-instructions">Pass Call Instructions</label>
            <Tooltip text="These instructions are shown to DJs on the giveaway page for shows at this venue — e.g. how winners should claim their passes at the door." />
          </div>
            <textarea
              id="venue-pass-instructions"
              value={passCallInstructions}
              onChange={(e) => setPassCallInstructions(e.target.value)}
              disabled={submitting}
              rows={3}
              placeholder="Instructions for DJs when calling in pass claims..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="venue-win-frequency">Win Frequency Limit (days)</label>
            <input
              type="number"
              id="venue-win-frequency"
              value={winFrequencyDays}
              onChange={(e) => setWinFrequencyDays(e.target.value)}
              className={errors.winFrequencyDays ? 'input-error' : ''}
              disabled={submitting}
              min="1"
              placeholder="e.g. 30 (leave blank for no limit)"
            />
            {errors.winFrequencyDays && (
              <span className="field-error">{errors.winFrequencyDays}</span>
            )}
            <span className="field-hint">
              Minimum days between wins for the same phone number at this venue.
            </span>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="venue-default-wheelchair">Default Wheelchair Accessible</label>
              <select
                id="venue-default-wheelchair"
                value={defaultWheelchair}
                onChange={(e) => setDefaultWheelchair(e.target.value as '' | 'true' | 'false')}
                disabled={submitting}
              >
                <option value="">No default</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="venue-default-age">Default Age Restriction</label>
              <select
                id="venue-default-age"
                value={defaultAgeRestriction}
                onChange={(e) => setDefaultAgeRestriction(e.target.value as '' | AgeRestriction)}
                disabled={submitting}
              >
                <option value="">No default</option>
                <option value="all_ages">All Ages</option>
                <option value="18+">18+</option>
                <option value="21+">21+</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="venue-default-num-pass-pairs">Default Pass Pairs</label>
              <input
                type="number"
                id="venue-default-num-pass-pairs"
                value={defaultNumPassPairs}
                onChange={(e) => setDefaultNumPassPairs(e.target.value)}
                className={errors.defaultNumPassPairs ? 'input-error' : ''}
                disabled={submitting}
                min="1"
                max="5"
                placeholder="e.g. 2 (leave blank for no default)"
              />
              {errors.defaultNumPassPairs && (
                <span className="field-error">{errors.defaultNumPassPairs}</span>
              )}
              <span className="field-hint">
                Default number of pass pairs pre-filled when creating a new show at this venue (1–5).
              </span>
            </div>
          </div>

          <div className="form-section">
            <h4>Guest List Requirements</h4>
            <p className="field-hint">
              These settings control what information appears in the guest list sent to this venue when a show closes.
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
                and the guest list will show the guest's name as a separate entry. When unchecked,
                the list shows "John Doe and a guest" without requiring the guest's name.
              </span>
            </div>
          </div>

          <div className="form-section">
            <h4>Lottery Defaults</h4>
            <p className="field-hint">
              When enabled, new shows at this venue will use a lottery window during which staff
              and DJ entries are held and randomly drawn instead of first-come first-served.
            </p>
            <div className="form-group form-group-checkbox">
              <label>
                <input
                  type="checkbox"
                  checked={defaultLotteryEnabled}
                  onChange={(e) => setDefaultLotteryEnabled(e.target.checked)}
                  disabled={submitting}
                />
                {' '}Enable lottery for new shows by default
              </label>
            </div>
            {defaultLotteryEnabled && (
              <div className="form-group">
                <label htmlFor="defaultLotteryWindowHours">Default lottery window (hours)</label>
                <input
                  id="defaultLotteryWindowHours"
                  type="number"
                  min="1"
                  max="168"
                  value={defaultLotteryWindowHours}
                  onChange={(e) => setDefaultLotteryWindowHours(e.target.value)}
                  disabled={submitting}
                  style={{ width: '6rem' }}
                />
                <span className="field-hint">
                  How many hours after publication the lottery window stays open (default: 24).
                </span>
              </div>
            )}
          </div>

          <div className="form-section">
            <h4>DJ Self-Assignment Restriction</h4>
            <p className="field-hint">
              Prevents DJs from reserving passes for shifts that are too close to the planned close
              date — ensuring there is enough time for another DJ to succeed if they fail.
            </p>
            <div className="form-group">
              <label htmlFor="venue-dj-preassign-prohibition-days">
                Default prohibition window (days before close date)
              </label>
              <input
                type="number"
                id="venue-dj-preassign-prohibition-days"
                value={defaultDjPreassignProhibitionDays}
                onChange={(e) => setDefaultDjPreassignProhibitionDays(e.target.value)}
                disabled={submitting}
                min="1"
                placeholder="e.g. 2 (leave blank for no restriction)"
              />
              <span className="field-hint">
                When set, DJs cannot reserve passes for shifts within this many days of the
                show's planned close date. Leave blank for no restriction.
              </span>
            </div>
          </div>

          <div className="form-section">
            <h4>Default Planned Close Offset</h4>
            <p className="field-hint">
              When set, new shows at this venue will have their planned close date and time
              automatically pre-filled when the show date and time are entered.
            </p>
            <div className="form-group">
              <label htmlFor="venue-default-close-hours-before-show">
                Hours before show date/time
              </label>
              <input
                type="number"
                id="venue-default-close-hours-before-show"
                value={defaultCloseHoursBeforeShow}
                onChange={(e) => setDefaultCloseHoursBeforeShow(e.target.value)}
                disabled={submitting}
                min="1"
                placeholder="e.g. 48 (leave blank for no default)"
              />
              <span className="field-hint">
                The planned close date/time will be pre-filled this many hours before the show
                when creating a new show. Leave blank for no default.
              </span>
            </div>
          </div>

          {venue && (
            <div className="form-section">
              <div className="label-with-help">
                <h4>Venue Logo</h4>
                <Tooltip text="The logo is displayed on the DJ show page in place of the venue name. Use a PNG with a transparent background for best results." />
              </div>
              <p className="field-hint">
                Recommended: PNG with transparent background, landscape orientation (e.g. 400×200 px).
                Max file size: 5 MB. The image will be scaled to fit within 800×400 px.
              </p>

              {(logoPreview || (!pendingLogoDelete && hasLogo)) && (
                <div className="venue-logo-preview">
                  <img
                    src={logoPreview ?? `${venueLogoUrl(venue.id)}?v=${logoKey}`}
                    alt="Venue logo preview"
                    className="venue-logo-img"
                  />
                  <button
                    type="button"
                    onClick={handleLogoRemove}
                    className="btn-danger btn-small"
                    disabled={submitting}
                  >
                    Remove Logo
                  </button>
                </div>
              )}

              {!logoPreview && (pendingLogoDelete || !hasLogo) && (
                <p className="field-hint">No logo uploaded.</p>
              )}

              <input
                key={logoKey}
                ref={logoInputRef}
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                onChange={handleLogoFileChange}
                disabled={submitting}
                style={{ marginTop: '0.5rem' }}
              />
            </div>
          )}

          <div className="form-section">
            <h4>Owners</h4>
            <p className="field-hint">Promotions staff emails with access to manage this venue.</p>
            <div className="tag-input-row">
              <input
                type="email"
                value={newOwnerEmail}
                onChange={(e) => setNewOwnerEmail(e.target.value)}
                placeholder="Add owner email..."
                disabled={submitting}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddOwner();
                  }
                }}
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
            {ownerEmails.length > 0 && (
              <ul className="tag-list">
                {ownerEmails.map((email) => (
                  <li key={email} className="tag-item">
                    <span>
                      {emailToName[email] ? `${emailToName[email]} (${email})` : email}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveOwner(email)}
                      className="tag-remove"
                      disabled={submitting}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="form-section">
            <h4>Venue Contacts</h4>
            {contacts.map((contact, idx) => (
              <div key={idx} className="contact-row">
                <div className="contact-fields">
                  <input
                    type="text"
                    placeholder="Name"
                    value={contact.name || ''}
                    onChange={(e) => handleContactChange(idx, 'name', e.target.value)}
                    disabled={submitting}
                  />
                  <input
                    type="text"
                    placeholder="Title"
                    value={contact.title || ''}
                    onChange={(e) => handleContactChange(idx, 'title', e.target.value)}
                    disabled={submitting}
                  />
                  <input
                    type="email"
                    placeholder="Email"
                    value={contact.email || ''}
                    onChange={(e) => handleContactChange(idx, 'email', e.target.value)}
                    disabled={submitting}
                  />
                  <input
                    type="tel"
                    placeholder="Phone"
                    value={contact.phone || ''}
                    onChange={(e) => handleContactChange(idx, 'phone', e.target.value)}
                    disabled={submitting}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveContact(idx)}
                  className="btn-danger btn-small"
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
              + Add Contact
            </button>
          </div>

          <div className="form-actions">
            {venue && (
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                className="btn-danger"
                disabled={submitting || deleting}
              >
                Delete Venue
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary"
              disabled={submitting || deleting}
            >
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={submitting || deleting}>
              {submitting ? 'Saving...' : venue ? 'Update' : 'Create'}
            </button>
          </div>
    </form>
  );

  if (asPage) {
    return (
      <>
        <div className="venue-form-page">
          <h2>{venue ? 'Edit Venue' : 'Create New Venue'}</h2>
          {form}
        </div>
        {deleteConfirmModal}
      </>
    );
  }

  return (
    <>
      <div className="modal-overlay">
        <div className="modal-content modal-content-wide">
          <div className="modal-header">
            <h3>{venue ? 'Edit Venue' : 'Create New Venue'}</h3>
            <button onClick={onClose} className="btn-close" disabled={submitting}>
              ×
            </button>
          </div>
          {form}
        </div>
      </div>
      {deleteConfirmModal}
    </>
  );
};

export default VenueForm;
