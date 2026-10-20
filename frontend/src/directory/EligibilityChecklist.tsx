import type { ReactNode } from 'react';
import type { Check, Eligibility, MonthCheck, PlaylistCheck } from './types';
import {
  formatDate,
  formatDateTime,
  formatHours,
  formatMinutes,
  formatMonthKey,
  workformMonthUrl,
} from './profileFormat';

interface EligibilityChecklistProps {
  eligibility: Eligibility;
  // null on your own profile; the person's ID when a site admin views theirs
  otherStaffId: number | null;
}

const REQUIREMENT_COUNT = 5;

const REASONS: Record<NonNullable<PlaylistCheck['reason']>, string> = {
  automated: 'Automated (no live DJ)',
  specialty: 'Specialty show',
  too_short: 'Shorter than 90 minutes',
};

// A requirement's ✓ / ✗ / ?, with a text alternative so it doesn't rely on
// the symbol or its color.
const Mark = ({ met }: { met: boolean | null }) => {
  const [symbol, label, kind] =
    met === true ? ['✓', 'Met', 'met'] : met === false ? ['✗', 'Not met', 'unmet'] : ['?', "Can't check", 'unknown'];
  return (
    <span className={`eligibility-mark eligibility-mark-${kind}`} role="img" aria-label={label}>
      {symbol}
    </span>
  );
};

const Requirement = ({ title, check, children }: { title: string; check: Check; children: ReactNode }) => (
  <li className="eligibility-row">
    <details>
      <summary>
        <Mark met={check.met} />
        <span className="eligibility-row-text">
          <span className="eligibility-row-title">{title}</span>
          <span className="eligibility-row-status">{check.summary}</span>
        </span>
      </summary>
      <div className="eligibility-details">{children}</div>
    </details>
  </li>
);

const playlistDate = (start: string) =>
  new Date(start).toLocaleDateString('en-US', { month: 'short', day: 'numeric', weekday: 'short' });

const PlaylistTable = ({ playlists }: { playlists: PlaylistCheck[] }) =>
  playlists.length === 0 ? (
    <p className="eligibility-empty">No playlists under your DJ names.</p>
  ) : (
    <table className="eligibility-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Show</th>
          <th>Length</th>
          <th>Counts?</th>
        </tr>
      </thead>
      <tbody>
        {playlists.map((p) => (
          <tr key={p.id}>
            <td>{playlistDate(p.start)}</td>
            <td>
              <a href={p.url} target="_blank" rel="noreferrer">
                {p.title || 'Untitled'}
              </a>
            </td>
            <td>
              {formatMinutes(p.minutes)}
              {p.shift_minutes !== null && p.shift_minutes !== p.minutes && (
                <span className="eligibility-note"> ({formatMinutes(p.shift_minutes)} back to back)</span>
              )}
            </td>
            <td>{p.counted ? 'Yes' : REASONS[p.reason ?? 'too_short']}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

const MonthRow = ({ month, otherStaffId }: { month: MonthCheck; otherStaffId: number | null }) => (
  <li className="eligibility-month">
    <div>
      <Mark met={month.met} /> <a href={workformMonthUrl(month.month, otherStaffId)}>{formatMonthKey(month.month)}</a>
      {': '}
      {month.loa
        ? 'leave of absence, so the minimum doesn’t apply'
        : `${formatHours(month.counted_hours)} h counted`}
      {month.most_recent && !month.loa && (
        <span className="eligibility-note"> (submitted hours count until departments decide)</span>
      )}
    </div>
    {month.status === 'draft' && <div className="eligibility-note">Not submitted yet</div>}
    {month.status === 'not_started' && !month.loa && (
      <div className="eligibility-note">No workform</div>
    )}
    {month.departments.length > 0 && (
      <ul className="eligibility-departments">
        {month.departments.map((d) => (
          <li key={d.department}>
            {d.department}: {formatHours(d.hours)} h, {d.decision ?? 'not decided yet'}
            {!d.counted && ' (doesn’t count)'}
          </li>
        ))}
      </ul>
    )}
    {month.pending_departments.length > 0 && (
      <div className="eligibility-note">
        Awaiting {month.pending_departments.join(', ')}: hours count once approved.
      </div>
    )}
  </li>
);

// Whether a Sublist DJ meets each requirement for subbing a DJ shift, each
// one expandable to its rule and the evidence behind the answer.
const EligibilityChecklist = ({ eligibility: e, otherStaffId }: EligibilityChecklistProps) => {
  const previous = e.shift.playlists.filter((p) => p.quarter === 'previous');
  const current = e.shift.playlists.filter((p) => p.quarter === 'current');
  return (
    <div className="eligibility">
      <div className={`eligibility-summary ${e.eligible ? 'eligibility-summary-met' : 'eligibility-summary-unmet'}`}>
        {e.eligible ? (
          <>
            <strong>✅ Eligible to sub DJ shifts</strong>
            {e.eligible_until && <div>Eligible until {formatDate(e.eligible_until)}</div>}
          </>
        ) : (
          <>
            <strong>
              ❌ Not eligible yet: {e.unmet} of {REQUIREMENT_COUNT} requirements unmet
            </strong>
            {e.unavailable > 0 && (
              <div>
                {e.unavailable} requirement{e.unavailable > 1 ? 's' : ''} couldn’t be checked
              </div>
            )}
          </>
        )}
        <div className="eligibility-note">{e.next_workform_note}</div>
      </div>

      <ul className="eligibility-rows">
        <Requirement title="DJ sublist" check={e.sublist}>
          <p>
            Your Status in the staff directory must include “Sublist DJ”. Staff management adds
            DJs to the sublist in Airtable.
          </p>
        </Requirement>

        <Requirement title="Leave of absence" check={e.leave}>
          <p>You can’t sub while you’re on a leave of absence from the station.</p>
          {(e.leave.loa_start || e.leave.loa_end) && (
            <p>
              Leave on record: {e.leave.loa_start ? formatDate(e.leave.loa_start) : '…'} –{' '}
              {e.leave.loa_end ? formatDate(e.leave.loa_end) : '…'}
            </p>
          )}
        </Requirement>

        <Requirement title="A DJ shift last quarter" check={e.shift}>
          <p>
            In the previous quarter ({e.shift.previous_quarter}) you need at least one DJ shift of{' '}
            {e.shift.min_minutes} minutes or more under your own DJ name, that isn’t a specialty show. Quarters run Feb–Apr, May–Jul, Aug–Oct and Nov–Jan. Back-to-back playlists count as
            one shift. Automated playlists, and shared names like DJ Trainee, don’t count.
          </p>
          <p>
            You can also meet this by submitting a 2-hour roboshow recording, but this page can’t see
            those yet, so it won’t show here if you have.
          </p>
          <h4>Last quarter ({e.shift.previous_quarter})</h4>
          <PlaylistTable playlists={previous} />
          <h4>This quarter so far ({e.shift.current_quarter})</h4>
          <p className="eligibility-note">A shift this quarter keeps you eligible next quarter.</p>
          <PlaylistTable playlists={current} />
          {e.shift.shifts_as_of && (
            <p className="eligibility-note">Shifts as of {formatDateTime(e.shift.shifts_as_of)}</p>
          )}
        </Requirement>

        <Requirement
          title={`Workforms: ${formatHours(e.workforms.required_hours)} h a month`}
          check={e.workforms}
        >
          <p>
            Each of the last 3 complete months needs at least{' '}
            {formatHours(e.workforms.required_hours)} hours on your workform. For the older two months,
            only hours a department has approved count. For the most recent month, submitted hours
            count unless a department denies them, since decisions can take a few weeks. A month during
            a leave of absence counts as met.
          </p>
          <ul className="eligibility-months">
            {e.workforms.months.map((month) => (
              <MonthRow key={month.month} month={month} otherStaffId={otherStaffId} />
            ))}
          </ul>
        </Requirement>

        <Requirement title="DJ Quiz" check={e.quiz}>
          <p>
            You need to have done the yearly DJ Quiz. Until this year’s quiz is due, last year’s
            still counts.
          </p>
          <p>
            Quizzes done: {e.quiz.years.length > 0 ? e.quiz.years.join(', ') : 'none on record'}
          </p>
          {e.quiz.this_year_deadline ? (
            <p>
              The {e.quiz.this_year_deadline.slice(0, 4)} quiz is due{' '}
              {formatDate(e.quiz.this_year_deadline)}.
            </p>
          ) : (
            <p>This year’s quiz deadline hasn’t been announced.</p>
          )}
        </Requirement>
      </ul>
    </div>
  );
};

export default EligibilityChecklist;
