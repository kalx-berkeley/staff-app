import { useState } from 'react';
import { passesAPI, showsAPI } from '../api';
import type { ShowResponse, StaffPassClaimant } from '../types';
import type { APIError } from '../../common/types';
import PersonAutocomplete from '../../common/components/PersonAutocomplete';
import { extractPersonEmail } from '../../common/components/personUtils';
import Tooltip from './Tooltip';
import { KALX_TABLE_NAME } from '../utils';

interface TablerPassesSectionProps {
  show: ShowResponse;
  /** Promotions can release anyone's tabler pass and assign one; staff claim their own. */
  mode: 'promotions' | 'staff';
  /** The signed-in user's email, to find their own tabler pass. */
  myEmail: string | null;
  /** Whether the user is in Publicity and can claim a tabler pass (staff mode). */
  canClaim?: boolean;
  /** Why the user can't claim one right now, e.g. they hold a staff pass (staff mode). */
  blockedReason?: string | null;
  /** Reload the show after a change. */
  onChanged: () => Promise<void> | void;
}

const errorText = (err: unknown, fallback: string): string => {
  const detail = (err as APIError)?.detail;
  return typeof detail === 'string' ? detail : fallback;
};

/**
 * The tabler passes of a co-announce show: staff passes set aside for
 * Publicity members at the KALX Co-Announce Table. Everyone sees who's tabling;
 * only Publicity members can claim, and promotions can release and assign.
 */
const TablerPassesSection = ({
  show,
  mode,
  myEmail,
  canClaim = false,
  blockedReason = null,
  onChanged,
}: TablerPassesSectionProps) => {
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [assignInput, setAssignInput] = useState('');
  const [staffList, setStaffList] = useState<StaffPassClaimant[] | null>(null);

  if (!show.co_announce || show.num_tabler_passes <= 0) return null;

  const tablerPasses = show.passes.filter((p) => p.pass_type === 'tabler');
  const claimed = tablerPasses.filter((p) => p.status === 'claimed');
  const openCount = tablerPasses.length - claimed.length;
  const myPass = myEmail
    ? claimed.find((p) => p.staff_email?.toLowerCase() === myEmail.toLowerCase()) ?? null
    : null;
  const isOpen = show.status !== 'closed' && show.status !== 'deleted';

  const run = async (action: () => Promise<unknown>, fallback: string) => {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      await onChanged();
    } catch (err) {
      setActionError(errorText(err, fallback));
    } finally {
      setBusy(false);
    }
  };

  const loadStaff = () => {
    if (staffList !== null) return;
    showsAPI
      .listStaffPassClaimants(true)
      .then(setStaffList)
      .catch(() => setActionError('Failed to load the staff list'));
  };

  const resolveStaff = (text: string): StaffPassClaimant | undefined => {
    const options = staffList ?? [];
    const email = extractPersonEmail(text);
    const byEmail = options.find((s) => s.email.toLowerCase() === email);
    if (byEmail) return byEmail;
    const name = text.trim().toLowerCase();
    const byName = options.filter((s) => (s.name ?? '').toLowerCase() === name);
    return byName.length === 1 ? byName[0] : undefined;
  };

  const assign = (text: string) => {
    const staff = resolveStaff(text);
    if (!staff) {
      setActionError('Pick a current staff member from the list');
      return;
    }
    run(async () => {
      await passesAPI.assignTablerPass(show.id, staff.id);
      setAssignInput('');
    }, 'Failed to assign the tabler pass');
  };

  return (
    <div className="pass-claim-section tabler-passes-section">
      <h3>
        🪑 {KALX_TABLE_NAME} ({claimed.length} of {tablerPasses.length} tabler pass
        {tablerPasses.length === 1 ? '' : 'es'} claimed)
        <Tooltip text="Tabler passes are staff passes set aside for Publicity members who sit at the KALX table at this show, hand out swag and promote KALX. They're first come, first served, with no +1 guest and no alternate list." />
      </h3>

      {claimed.length > 0 ? (
        <ul className="tabler-list" style={{ margin: '0 0 0.75rem', paddingLeft: '1.25rem' }}>
          {claimed.map((p) => {
            const mine = myPass?.id === p.id;
            const canRelease = isOpen && (mode === 'promotions' || mine);
            return (
              <li key={p.id} style={{ marginBottom: '0.25rem' }}>
                {p.staff_name ?? 'Unknown'}
                {mine && ' (you)'}
                {canRelease && (
                  <>
                    {' '}
                    <button
                      className="btn-small btn-secondary"
                      onClick={() =>
                        run(() => passesAPI.releaseClaim(p.id), 'Failed to release the tabler pass')
                      }
                      disabled={busy}
                    >
                      {mine ? 'Release my tabler pass' : 'Release'}
                    </button>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="field-hint">No one has claimed a tabler pass yet.</p>
      )}

      {mode === 'staff' && isOpen && !myPass && (
        canClaim ? (
          blockedReason ? (
            <p className="field-hint">{blockedReason}</p>
          ) : openCount > 0 ? (
            <button
              className="btn-small btn-primary"
              onClick={() =>
                run(() => passesAPI.claimTablerPass(show.id), 'Failed to claim the tabler pass')
              }
              disabled={busy}
            >
              {busy ? 'Claiming…' : 'Claim a tabler pass'}
            </button>
          ) : (
            <p className="field-hint">All the tabler passes have been claimed.</p>
          )
        ) : (
          <p className="field-hint">Only Publicity members can claim tabler passes.</p>
        )
      )}

      {mode === 'promotions' && isOpen && openCount > 0 && (
        <div className="form-group" style={{ maxWidth: '24rem' }}>
          <label htmlFor="assign-tabler">Give a tabler pass to</label>
          <div onFocus={loadStaff}>
            <PersonAutocomplete
              id="assign-tabler"
              value={assignInput}
              onChange={setAssignInput}
              onSubmit={assign}
              options={staffList ?? []}
              placeholder="Staff name or email"
              disabled={busy}
            />
          </div>
          <span className="field-hint" style={{ display: 'block', marginTop: '0.25rem' }}>
            Any current staff member. They'll get an email.
          </span>
        </div>
      )}

      {actionError && <p className="field-error">{actionError}</p>}
    </div>
  );
};

export default TablerPassesSection;
