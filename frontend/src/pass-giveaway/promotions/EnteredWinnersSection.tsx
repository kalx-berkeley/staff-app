import { useEffect, useState } from 'react';
import { showsAPI } from '../api';
import { PersonAutocomplete, extractPersonEmail } from '../components';
import { formatPhone } from '../../common/utils';
import type { PassResponse, StaffPassClaimant } from '../types';
import { emptyOnAirRow, emptyStaffRow, staffPassesNeeded } from './enteredWinners';
import type { FreePasses, OnAirWinnerRow, StaffWinnerRow } from './enteredWinners';

// Hidden behind a toggle to discourage use. See
// docs/pass-giveaway/specs/preassigned-winners/plan.md.

interface EnteredWinnersSectionProps {
  onAirRows: OnAirWinnerRow[];
  staffRows: StaffWinnerRow[];
  onOnAirRowsChange: (rows: OnAirWinnerRow[]) => void;
  onStaffRowsChange: (rows: StaffWinnerRow[]) => void;
  free: FreePasses;
  requiresEmail: boolean;
  guestRequiresName: boolean;
  /** The show's winners and claims so far, when editing. */
  existingPasses: PassResponse[];
  error: string | null;
  disabled: boolean;
}

const EnteredWinnersSection = ({
  onAirRows,
  staffRows,
  onOnAirRowsChange,
  onStaffRowsChange,
  free,
  requiresEmail,
  guestRequiresName,
  existingPasses,
  error,
  disabled,
}: EnteredWinnersSectionProps) => {
  const [open, setOpen] = useState(false);
  const [staffList, setStaffList] = useState<StaffPassClaimant[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Show what's wrong when saving is blocked, even if the rep collapsed the section
  useEffect(() => {
    if (error) setOpen(true);
  }, [error]);

  // Only fetched once the section is opened, since most shows never use it
  useEffect(() => {
    if (!open || staffList !== null) return;
    let cancelled = false;
    showsAPI
      .listStaffPassClaimants()
      .then((list) => {
        if (!cancelled) setStaffList(list);
      })
      .catch(() => {
        if (!cancelled) setLoadError('Failed to load the staff list');
      });
    return () => {
      cancelled = true;
    };
  }, [open, staffList]);

  const entered = onAirRows.length + staffRows.length;
  const staffOptions = staffList ?? [];

  const resolveStaff = (text: string): StaffPassClaimant | undefined => {
    const email = extractPersonEmail(text);
    const byEmail = staffOptions.find((s) => s.email.toLowerCase() === email);
    if (byEmail) return byEmail;
    const name = text.trim().toLowerCase();
    const byName = staffOptions.filter((s) => (s.name ?? '').toLowerCase() === name);
    return byName.length === 1 ? byName[0] : undefined;
  };

  const updateOnAir = (key: number, changes: Partial<OnAirWinnerRow>) =>
    onOnAirRowsChange(onAirRows.map((r) => (r.key === key ? { ...r, ...changes } : r)));
  const updateStaff = (key: number, changes: Partial<StaffWinnerRow>) =>
    onStaffRowsChange(staffRows.map((r) => (r.key === key ? { ...r, ...changes } : r)));

  const pairsShort = onAirRows.length - free.pairs;
  const staffShort = staffPassesNeeded(staffRows) - free.staff;

  const existingWinners = existingPasses.filter(
    (p) => p.pass_type === 'pair' && p.status === 'given_away',
  );
  const existingClaims = existingPasses.filter(
    (p) => p.pass_type === 'staff' && p.status === 'claimed' && !p.guest_of_pass_id,
  );

  return (
    <div className="form-group">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{
          background: 'none',
          border: 'none',
          padding: '0.25rem 0',
          cursor: 'pointer',
          color: 'var(--primary-color)',
          fontWeight: 500,
          fontSize: '0.9rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
        }}
      >
        <span style={{ fontSize: '0.75em' }}>{open ? '▼' : '▶'}</span>
        Enter winners from a previous show
        {entered > 0 && ` (${entered} entered)`}
      </button>
      <span className="field-hint" style={{ display: 'block' }}>
        Only for a show that replaces one that was cancelled, postponed or moved. Most shows
        should leave this alone.
      </span>

      {open && (
        <div style={{ marginTop: '0.75rem' }}>
          <div
            className="error-message"
            style={{ marginBottom: '1rem', background: '#fff3cd', borderColor: '#ffc107', color: '#856404' }}
          >
            <strong>No one is notified.</strong> Winners you add here aren't emailed or texted.
            Contact each of them yourself to let them know about this show.
          </div>

          {(existingWinners.length > 0 || existingClaims.length > 0) && (
            <div style={{ marginBottom: '1rem' }}>
              <strong>Already on this show</strong>
              <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
                {existingWinners.map((p) => (
                  <li key={p.id}>
                    On-air: {p.recipient_name}
                    {p.recipient_phone ? ` (${formatPhone(p.recipient_phone)})` : ''}
                  </li>
                ))}
                {existingClaims.map((p) => (
                  <li key={p.id}>
                    Staff: {p.staff_name}
                    {p.has_guest ? ' +1' : ''}
                  </li>
                ))}
              </ul>
              <span className="field-hint">Change or release these on the show's page.</span>
            </div>
          )}

          <h4 style={{ margin: '0 0 0.5rem' }}>On-air winners</h4>
          {onAirRows.map((row, i) => {
            const prefix = `entered_on_air_${row.key}`;
            return (
              <div key={row.key} className="pass-card" style={{ marginBottom: '0.75rem' }}>
                <div className="pass-header">
                  <h3>On-air winner {i + 1}</h3>
                  <button
                    type="button"
                    className="btn-secondary btn-small"
                    onClick={() => onOnAirRowsChange(onAirRows.filter((r) => r.key !== row.key))}
                    disabled={disabled}
                    aria-label={`Remove on-air winner ${i + 1}`}
                  >
                    Remove
                  </button>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor={`${prefix}_name`}>Name <span className="required">*</span></label>
                    <input
                      id={`${prefix}_name`}
                      type="text"
                      value={row.recipient_name}
                      onChange={(e) => updateOnAir(row.key, { recipient_name: e.target.value })}
                      disabled={disabled}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor={`${prefix}_phone`}>Phone <span className="required">*</span></label>
                    <input
                      id={`${prefix}_phone`}
                      type="tel"
                      value={row.recipient_phone}
                      onChange={(e) => updateOnAir(row.key, { recipient_phone: e.target.value })}
                      disabled={disabled}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor={`${prefix}_email`}>
                      Email {requiresEmail && <span className="required">*</span>}
                    </label>
                    <input
                      id={`${prefix}_email`}
                      type="email"
                      value={row.recipient_email}
                      onChange={(e) => updateOnAir(row.key, { recipient_email: e.target.value })}
                      placeholder={requiresEmail ? 'Required' : 'Optional'}
                      disabled={disabled}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor={`${prefix}_dj`}>Given away by</label>
                    <input
                      id={`${prefix}_dj`}
                      type="text"
                      value={row.given_away_by_dj}
                      onChange={(e) => updateOnAir(row.key, { given_away_by_dj: e.target.value })}
                      placeholder="DJ name (optional)"
                      disabled={disabled}
                    />
                  </div>
                </div>
              </div>
            );
          })}
          <button
            type="button"
            className="btn-secondary btn-small"
            onClick={() => onOnAirRowsChange([...onAirRows, emptyOnAirRow()])}
            disabled={disabled}
            style={{ marginBottom: '1rem' }}
          >
            Add on-air winner
          </button>

          <h4 style={{ margin: '0 0 0.5rem' }}>Staff winners</h4>
          {loadError && <div className="error-message">{loadError}</div>}
          {staffRows.map((row, i) => {
            const prefix = `entered_staff_${row.key}`;
            return (
              <div key={row.key} className="pass-card" style={{ marginBottom: '0.75rem' }}>
                <div className="pass-header">
                  <h3>Staff winner {i + 1}</h3>
                  <button
                    type="button"
                    className="btn-secondary btn-small"
                    onClick={() => onStaffRowsChange(staffRows.filter((r) => r.key !== row.key))}
                    disabled={disabled}
                    aria-label={`Remove staff winner ${i + 1}`}
                  >
                    Remove
                  </button>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor={prefix}>Staff member <span className="required">*</span></label>
                    <PersonAutocomplete
                      id={prefix}
                      value={row.staff_input}
                      onChange={(text) =>
                        updateStaff(row.key, { staff_input: text, staff_id: resolveStaff(text)?.id ?? '' })
                      }
                      onSubmit={(text) => {
                        const staff = resolveStaff(text);
                        updateStaff(
                          row.key,
                          staff
                            ? { staff_input: `${staff.name} (${staff.email})`, staff_id: staff.id }
                            : { staff_input: text, staff_id: '' },
                        );
                      }}
                      options={staffOptions}
                      placeholder="Staff name or email"
                      disabled={disabled}
                    />
                  </div>
                  <div className="form-group checkbox-group">
                    <label>
                      <input
                        type="checkbox"
                        checked={row.has_guest}
                        onChange={(e) => updateStaff(row.key, { has_guest: e.target.checked })}
                        disabled={disabled}
                      />
                      +1 Guest
                    </label>
                  </div>
                </div>
                {row.has_guest && (
                  <div className="form-group">
                    <label htmlFor={`${prefix}_guest`}>
                      Guest name {guestRequiresName && <span className="required">*</span>}
                    </label>
                    <input
                      id={`${prefix}_guest`}
                      type="text"
                      value={row.guest_name}
                      onChange={(e) => updateStaff(row.key, { guest_name: e.target.value })}
                      placeholder={guestRequiresName ? 'Required' : 'Optional'}
                      disabled={disabled}
                    />
                  </div>
                )}
              </div>
            );
          })}
          <button
            type="button"
            className="btn-secondary btn-small"
            onClick={() => onStaffRowsChange([...staffRows, emptyStaffRow()])}
            disabled={disabled}
          >
            Add staff winner
          </button>

          {entered > 0 && (
            <p className="field-hint" style={{ marginTop: '0.75rem' }}>
              Uses {onAirRows.length} of {free.pairs} free pass pair{free.pairs === 1 ? '' : 's'} and{' '}
              {staffPassesNeeded(staffRows)} of {free.staff} free staff pass{free.staff === 1 ? '' : 'es'}.
              {pairsShort > 0 && (
                <strong className="field-error"> {pairsShort} pass pair{pairsShort === 1 ? '' : 's'} short.</strong>
              )}
              {staffShort > 0 && (
                <strong className="field-error"> {staffShort} staff pass{staffShort === 1 ? '' : 'es'} short.</strong>
              )}
            </p>
          )}
          {error && <div className="field-error" style={{ marginTop: '0.5rem' }}>{error}</div>}
        </div>
      )}
    </div>
  );
};

export default EnteredWinnersSection;
