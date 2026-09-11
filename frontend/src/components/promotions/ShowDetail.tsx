import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { showsAPI, passesAPI, autocompleteAPI, specialtyShowsAPI, lotteryAPI } from '../../services/api';
import { Tooltip, EnrichedShowName, MarkdownContent, FeatureBinBadge, DatePicker } from '../shared';
import { formatPhone, formatDateValue } from '../../utils';
import { useAuth } from '../../contexts/authHooks';
import type {
  ShowResponse,
  PreAssignmentData,
  LotteryStatus,
  APIError,
  PromotionsStaffProfile,
} from '../../types';

type ConfirmAction = 'close' | 'unpublish' | 'reopen' | null;

interface ConfirmModalProps {
  action: Exclude<ConfirmAction, null>;
  show: ShowResponse;
  userEmail: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmModal = ({ action, show, userEmail, onConfirm, onCancel }: ConfirmModalProps) => {
  const isVenueOwner = userEmail
    ? show.venue.owner_emails.includes(userEmail)
    : true;

  if (action === 'close') {
    return (
      <div className="modal-overlay" onClick={onCancel}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h3>Close Show</h3>
            <button className="btn-close" onClick={onCancel}>×</button>
          </div>
          {!isVenueOwner && (
            <div className="error-message" style={{ marginBottom: '1rem' }}>
              <strong>Note:</strong> You are not listed as an owner of{' '}
              <strong>{show.venue.name}</strong>. Closing a show at a venue you
              don't own is unusual — please confirm this is intentional.
            </div>
          )}
          <p>
            Are you sure you want to close <strong>{show.event_name}</strong>?
            No further pass giveaways or staff claims will be allowed.
          </p>
          <div className="form-actions" style={{ marginTop: '1rem' }}>
            <button onClick={onCancel} className="btn-secondary">Cancel</button>
            <button onClick={onConfirm} className="btn-primary">Close Show</button>
          </div>
        </div>
      </div>
    );
  }

  if (action === 'reopen') {
    return (
      <div className="modal-overlay" onClick={onCancel}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h3>Re-open Show</h3>
            <button className="btn-close" onClick={onCancel}>×</button>
          </div>
          <p>
            Are you sure you want to re-open <strong>{show.event_name}</strong>?
            The show will return to published status and pass giveaways and staff claims will be allowed again.
          </p>
          <div className="form-actions" style={{ marginTop: '1rem' }}>
            <button onClick={onCancel} className="btn-secondary">Cancel</button>
            <button onClick={onConfirm} className="btn-primary">Re-open Show</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Unpublish Show</h3>
          <button className="btn-close" onClick={onCancel}>×</button>
        </div>
        <p>
          Are you sure you want to unpublish <strong>{show.event_name}</strong>?
          The show will return to draft status and will no longer be visible to DJs.
        </p>
        <div className="form-actions" style={{ marginTop: '1rem' }}>
          <button onClick={onCancel} className="btn-secondary">Cancel</button>
          <button onClick={onConfirm} className="btn-primary">Unpublish Show</button>
        </div>
      </div>
    </div>
  );
};

const ShowDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [show, setShow] = useState<ShowResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const [copySuccess, setCopySuccess] = useState(false);

  // Pre-assignment state
  const [preassignPassId, setPreassignPassId] = useState<number | null>(null);
  const [preassignDj, setPreassignDj] = useState('');
  const [preassignDate, setPreassignDate] = useState('');

  // Lottery status
  const [lotteryStatus, setLotteryStatus] = useState<LotteryStatus | null>(null);

  // DJ autocomplete for pre-assignment
  const [djNames, setDjNames] = useState<string[]>([]);
  const [filteredDjNames, setFilteredDjNames] = useState<string[]>([]);
  const [showDjAutocomplete, setShowDjAutocomplete] = useState(false);
  const djAutocompleteRef = useRef<HTMLUListElement>(null);
  const [specialtyShowNames, setSpecialtyShowNames] = useState<Set<string>>(new Set());

  // On-air schedule check for the entered DJ/specialty show name, to restrict
  // (and warn about) the pre-assignment date.
  // null = unknown (name not yet checked, or the check failed); [] = checked, no matching dates.
  const [scheduleDates, setScheduleDates] = useState<string[] | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  // Tracks the name a schedule check was last fetched (or is in flight) for, so
  // selecting an autocomplete suggestion (which immediately fetches) followed by
  // the input's blur (which fires right after, for the same name) only fetches once.
  const lastScheduleFetchNameRef = useRef<string | null>(null);

  const loadShow = useCallback(async () => {
    if (!id) return;

    try {
      setLoading(true);
      setError(null);
      const data = await showsAPI.get(parseInt(id));
      setShow(data);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load show'
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadLotteryStatus = useCallback(async () => {
    if (!id) return;
    try {
      const status = await lotteryAPI.getStatus(parseInt(id));
      setLotteryStatus(status);
    } catch {
      // non-fatal — section will not render
    }
  }, [id]);

  useEffect(() => {
    loadShow();
  }, [loadShow]);

  useEffect(() => {
    loadLotteryStatus();
  }, [loadLotteryStatus]);

  useEffect(() => {
    autocompleteAPI.getDJNames().then(setDjNames).catch(() => {});
    specialtyShowsAPI.list()
      .then((shows) => setSpecialtyShowNames(new Set(shows.map((s) => s.name.toLowerCase()))))
      .catch(() => {});
  }, []);

  const fetchScheduleForName = async (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) {
      lastScheduleFetchNameRef.current = null;
      setScheduleDates(null);
      return;
    }
    if (lastScheduleFetchNameRef.current === trimmed) {
      // Already fetched (or fetching) for this exact name — e.g. selecting an
      // autocomplete suggestion fetches immediately, and the blur that follows
      // shouldn't repeat the same request.
      return;
    }
    lastScheduleFetchNameRef.current = trimmed;
    setScheduleLoading(true);
    try {
      const dates = await passesAPI.getPreassignSchedule(trimmed);
      setScheduleDates(dates);
    } catch {
      // Non-fatal — degrade to an unrestricted date picker with no warning.
      setScheduleDates(null);
    } finally {
      setScheduleLoading(false);
    }
  };

  const handlePreassignDjChange = (value: string) => {
    setPreassignDj(value);
    // The name no longer matches whatever was last checked — let the next
    // fetch (on blur, or on selecting a suggestion) run again.
    lastScheduleFetchNameRef.current = null;
    if (value.trim()) {
      const filtered = djNames.filter((name) =>
        name.toLowerCase().includes(value.toLowerCase())
      );
      setFilteredDjNames(filtered);
      setShowDjAutocomplete(filtered.length > 0);
    } else {
      setShowDjAutocomplete(false);
    }
  };

  const selectPreassignDj = (name: string) => {
    setPreassignDj(name);
    setShowDjAutocomplete(false);
    fetchScheduleForName(name);
  };

  const handlePreassignDjBlur = () => {
    setTimeout(() => setShowDjAutocomplete(false), 200);
    fetchScheduleForName(preassignDj);
  };

  const handlePreassignDjKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Tab' && filteredDjNames.length === 1) {
      e.preventDefault();
      selectPreassignDj(filteredDjNames[0]);
    }
  };

  const handlePublish = async () => {
    if (!show || !id) return;

    setActionLoading(true);
    setActionError(null);

    try {
      await showsAPI.publish(parseInt(id));
      await loadShow();
    } catch (err) {
      const apiError = err as APIError;
      setActionError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to publish show'
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirmedAction = async () => {
    if (!show || !id || !confirmAction) return;

    setConfirmAction(null);
    setActionLoading(true);
    setActionError(null);

    try {
      if (confirmAction === 'close') {
        await showsAPI.close(parseInt(id));
      } else if (confirmAction === 'unpublish') {
        await showsAPI.unpublish(parseInt(id));
      } else if (confirmAction === 'reopen') {
        await showsAPI.reopen(parseInt(id));
      }
      await loadShow();
    } catch (err) {
      const apiError = err as APIError;
      setActionError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : `Failed to ${confirmAction} show`
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handlePreassignSubmit = async (passId: number) => {
    if (!preassignDj.trim() || !preassignDate) {
      setActionError('DJ name and date are required for pre-assignment');
      return;
    }

    if (isVenueOwner && userDjName && preassignDj.trim().toLowerCase() === userDjName.toLowerCase()) {
      setActionError('Promotions venue owners cannot pre-assign passes to their own DJ name.');
      return;
    }

    setActionLoading(true);
    setActionError(null);

    try {
      const data: PreAssignmentData = {
        dj_name: preassignDj.trim(),
        assignment_date: preassignDate,
      };
      const updatedPass = await passesAPI.setPreassignment(passId, data);
      // Patch just this pass into local state instead of re-fetching the whole
      // show — loadShow() flips `loading`, which blanks the entire page behind
      // a "Loading show details…" message for what should be a quiet update.
      setShow((prev) =>
        prev
          ? { ...prev, passes: prev.passes.map((p) => (p.id === updatedPass.id ? updatedPass : p)) }
          : prev
      );
      setPreassignPassId(null);
      setPreassignDj('');
      setPreassignDate('');
      setScheduleDates(null);
      lastScheduleFetchNameRef.current = null;
    } catch (err) {
      const apiError = err as APIError;
      setActionError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to set pre-assignment'
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemovePreassignment = async (passId: number) => {
    setActionLoading(true);
    setActionError(null);

    try {
      const updatedPass = await passesAPI.removePreassignment(passId);
      // Patch just this pass into local state instead of re-fetching the whole
      // show — see handlePreassignSubmit for why loadShow() isn't used here.
      setShow((prev) =>
        prev
          ? { ...prev, passes: prev.passes.map((p) => (p.id === updatedPass.id ? updatedPass : p)) }
          : prev
      );
    } catch (err) {
      const apiError = err as APIError;
      setActionError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to remove pre-assignment'
      );
    } finally {
      setActionLoading(false);
    }
  };

  const formatAgeRestriction = (age: string) =>
    age === 'all_ages' ? 'All Ages' : age;

  const formatDate = (dateStr: string): string => {
    const [_y, _m, _d] = dateStr.split('-').map(Number); const date = new Date(_y, _m - 1, _d);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatDateTime = (dateTimeStr: string): string => {
    const date = new Date(dateTimeStr);
    return date.toLocaleString('en-US', {
      timeZone: 'America/Los_Angeles',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const formatTime = (timeStr: string): string => {
    const [hours, minutes] = timeStr.split(':').map(Number);
    const period = hours >= 12 ? 'pm' : 'am';
    const hour12 = hours % 12 || 12;
    return `${hour12}:${String(minutes).padStart(2, '0')}${period}`;
  };

  const formatShowDateTime = (dateStr: string, timeStr: string): string => {
    const [hours, minutes] = timeStr.split(':').map(Number);
    const [_y, _m, _d] = dateStr.split('-').map(Number); const date = new Date(_y, _m - 1, _d);
    const weekday = date.toLocaleDateString('en-US', { weekday: 'long' });
    const monthDayYear = date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
    const period = hours >= 12 ? 'pm' : 'am';
    const hour12 = hours % 12 || 12;
    const time = `${hour12}:${String(minutes).padStart(2, '0')}${period}`;
    return `${weekday}, ${monthDayYear} at ${time}`;
  };

  const formatDateRange = (startDateStr: string, endDateStr: string): string => {
    const [sy, sm, sd] = startDateStr.split('-').map(Number);
    const [ey, em, ed] = endDateStr.split('-').map(Number);
    const start = new Date(sy, sm - 1, sd);
    const end = new Date(ey, em - 1, ed);
    const startFmt = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const endFmt = end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    return `${startFmt} – ${endFmt}`;
  };

  const formatAttemptDateTime = (dateTimeStr: string): string => {
    const date = new Date(dateTimeStr);
    const weekday = date.toLocaleDateString('en-US', { timeZone: 'America/Los_Angeles', weekday: 'long' });
    const monthDayYear = date.toLocaleDateString('en-US', { timeZone: 'America/Los_Angeles', month: 'long', day: 'numeric', year: 'numeric' });
    const time = date.toLocaleTimeString('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', minute: '2-digit', hour12: true })
      .toLowerCase().replace(' ', '');
    return `${weekday} ${monthDayYear} at ${time}`;
  };

  const getStatusBadgeClass = (status: string): string => {
    switch (status) {
      case 'draft':
        return 'status-badge status-draft';
      case 'published':
        return 'status-badge status-published';
      case 'closed':
        return 'status-badge status-closed';
      default:
        return 'status-badge';
    }
  };

  const passPairs = show?.passes.filter((t) => t.pass_type === 'pair') || [];
  const staffPasses = show?.passes.filter((t) => t.pass_type === 'staff') || [];
  const isVenueOwner = user?.email ? (show?.venue.owner_emails.includes(user.email) ?? false) : false;
  const userDjName = (user?.profile as PromotionsStaffProfile | null)?.dj_name ?? null;

  // The pass-pair reservation deadline the backend actually enforces — a
  // plain date comparison against `planned_close_date` (see
  // PassService.set_preassignment), not the show date itself. Falls back to
  // the show date when there's no planned close date.
  const maxPreassignDate = show ? show.planned_close_date ?? show.show_date : undefined;

  // Of the checked schedule dates, which fall on or before that deadline —
  // the actual pickable range.
  const scheduleDatesBeforeClose = show
    ? (scheduleDates?.filter((d) => d <= maxPreassignDate!) ?? null)
    : null;

  const reqPhone = show?.venue.requires_phone_number ?? false;
  const reqEmail = show?.venue.requires_email_address ?? false;
  const staffGuestRequiresName = show?.venue.staff_guest_requires_name ?? false;

  const buildExtras = (phone: string | null, email: string | null): string => {
    const parts: string[] = [];
    if (reqPhone && phone) parts.push(formatPhone(phone));
    if (reqEmail && email) parts.push(email);
    return parts.length > 0 ? ` (${parts.join(', ')})` : '';
  };

  const buildStaffPassLines = (p: typeof staffPasses[number]): string[] => {
    if (!p.staff_name) return [];
    const primaryLine = `1 pass for ${p.staff_name}${buildExtras(p.staff_phone, p.staff_email)}`;
    if (!p.has_guest) return [primaryLine];
    if (staffGuestRequiresName && p.guest_name) {
      return [primaryLine, `1 pass for ${p.guest_name}`];
    }
    return [`1 pass for ${p.staff_name} and a guest${buildExtras(p.staff_phone, p.staff_email)}`];
  };

  const primaryStaffPasses = staffPasses.filter(
    (p) => p.status === 'claimed' && p.guest_of_pass_id == null
  );

  const guestListLines = [
    ...passPairs
      .filter((p) => p.status === 'given_away' && p.recipient_name)
      .map((p) => `1 pair of passes for ${p.recipient_name} and a guest${buildExtras(p.recipient_phone, p.recipient_email)}`),
    ...primaryStaffPasses.flatMap((p) => buildStaffPassLines(p)),
  ];

  const introLine = show
    ? `Here are the pass winners for ${show.event_name} on ${show.show_start_date ? formatDateRange(show.show_start_date, show.show_date) : formatShowDateTime(show.show_date, show.show_time!)}. These guests won their passes through KALX radio's on-air giveaway and we'd love to have them attend the show!`
    : '';

  const emailGreeting = show ? `Hi ${show.venue.name} team,` : '';
  const emailClosing = 'Thank you so much for partnering with KALX — we really appreciate it!\n\nBest,\nKALX Promotions';

  const failedAttempts = show?.attempts ?? [];

  const handleCopyGuestList = async () => {
    const lines = [
      emailGreeting,
      '',
      introLine,
      ...guestListLines,
      ...(failedAttempts.length > 0
        ? [
            '',
            "We also announced the show on-air but didn't get any callers.",
            ...failedAttempts.map(
              (a) => `DJ ${a.dj_name} announced the show on ${formatAttemptDateTime(a.attempted_at)}`
            ),
          ]
        : []),
      '',
      emailClosing,
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch {
      // clipboard API unavailable
    }
  };

  if (loading) {
    return <div className="loading">Loading show details...</div>;
  }

  if (error || !show) {
    return (
      <div className="error">
        <p>Error: {error || 'Show not found'}</p>
        <button onClick={loadShow}>Retry</button>
      </div>
    );
  }

  return (
    <div className="show-detail">
      <div className="show-detail-header">
        <div>
          <h2><EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} /></h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
            <span className={getStatusBadgeClass(show.status)}>{show.status}</span>
            {show.co_announce && <span className="co-announce-badge">📢 Co-Announce</span>}
            {show.in_feature_bin && <FeatureBinBadge releases={show.feature_bin_releases} />}
          </div>
        </div>
        <div className="header-actions">
          {show.status === 'draft' && (
            <button
              onClick={handlePublish}
              className="btn-primary"
              disabled={actionLoading}
              title="Make this show visible to DJs so they can give away pass pairs on air."
            >
              Publish Show
            </button>
          )}
          {show.status === 'published' && (
            <>
              <button
                onClick={() => setConfirmAction('unpublish')}
                className="btn-primary"
                disabled={actionLoading}
                title="Return this show to draft status, hiding it from DJs."
              >
                Unpublish Show
              </button>
              <button
                onClick={() => setConfirmAction('close')}
                className="btn-primary"
                disabled={actionLoading}
                title="Mark this show as complete. No further pass giveaways or staff claims will be allowed."
              >
                Close Show
              </button>
            </>
          )}
          {show.status === 'closed' && show.show_date >= new Date().toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' }) && (
            <button
              onClick={() => setConfirmAction('reopen')}
              className="btn-primary"
              disabled={actionLoading}
              title="Re-open this show so pass giveaways and staff claims are allowed again."
            >
              Re-open Show
            </button>
          )}
          <Link
            to={`/promotions/shows/${show.id}/edit`}
            className="btn-primary"
          >
            Edit
          </Link>
          <button
            onClick={() => navigate(-1)}
            className="btn-secondary"
          >
            Back to Shows
          </button>
        </div>
      </div>

      {actionError && <div className="error-message">{actionError}</div>}

      {show.status === 'closed' && (
        <div className="guest-list-summary">
          <div className="guest-list-summary-header">
            <h3>Guest List for Venue</h3>
            {(guestListLines.length > 0 || failedAttempts.length > 0) && (
              <button onClick={handleCopyGuestList} className="btn-secondary btn-small">
                {copySuccess ? 'Copied!' : 'Copy'}
              </button>
            )}
          </div>
          <p className="guest-list-greeting">{emailGreeting}</p>
          <p className="guest-list-intro">{introLine}</p>
          {guestListLines.length > 0 ? (
            <pre className="guest-list-text">{guestListLines.join('\n')}</pre>
          ) : (
            <p className="guest-list-empty">No passes were given away for this show.</p>
          )}
          {failedAttempts.length > 0 && (
            <div className="guest-list-attempts">
              <p>We also announced the show on-air but didn't get any callers.</p>
              <ul>
                {failedAttempts.map((attempt) => (
                  <li key={attempt.id}>
                    DJ {attempt.dj_name} announced the show on {formatAttemptDateTime(attempt.attempted_at)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="guest-list-closing" style={{ whiteSpace: 'pre-line' }}>{emailClosing}</p>
        </div>
      )}

      {show.status === 'closed' && (show.venue.pass_call_instructions || show.venue.contacts.length > 0) && (
        <div className="show-info">
          {show.venue.pass_call_instructions && (
            <div className="info-section">
              <h3>Venue Call-In Instructions</h3>
              <p style={{ whiteSpace: 'pre-wrap' }}>{show.venue.pass_call_instructions}</p>
            </div>
          )}
          {show.venue.contacts.length > 0 && (
            <div className="info-section">
              <h3>Venue Contact{show.venue.contacts.length > 1 ? 's' : ''}</h3>
              {show.venue.contacts.map((contact) => (
                <dl key={contact.id}>
                  {contact.name && <><dt>Name:</dt><dd>{contact.name}</dd></>}
                  {contact.title && <><dt>Title:</dt><dd>{contact.title}</dd></>}
                  {contact.email && <><dt>Email:</dt><dd>{contact.email}</dd></>}
                  {contact.phone && <><dt>Phone:</dt><dd>{contact.phone}</dd></>}
                </dl>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="show-info">
        <div className="info-section">
          <h3>Event Information</h3>
          <dl>
            <dt>Genre:</dt>
            <dd>{(show.genre ?? []).join(', ')}</dd>
            <dt>Venue:</dt>
            <dd>{show.venue.name}</dd>
            <dt>Address:</dt>
            <dd>{show.venue.address}</dd>
            <dt>{show.show_start_date ? 'Dates:' : 'Date & Time:'}</dt>
            <dd>
              {show.show_start_date
                ? formatDateRange(show.show_start_date, show.show_date)
                : `${formatDate(show.show_date)} at ${formatTime(show.show_time!)}`}
            </dd>
            <dt>Age Restriction:</dt>
            <dd>{formatAgeRestriction(show.age_restriction)}</dd>
            <dt>Wheelchair Accessible:</dt>
            <dd>{show.wheelchair_accessible ? 'Yes' : 'No'}</dd>
            {show.planned_close_date && show.planned_close_time && (
              <>
                <dt>Planned Close:</dt>
                <dd>
                  {formatDate(show.planned_close_date)} at {formatTime(show.planned_close_time)}
                  {show.auto_close && (
                    <span style={{ marginLeft: '0.5rem', fontSize: '0.85em', color: '#666' }}>
                      (auto-close enabled)
                    </span>
                  )}
                </dd>
              </>
            )}
            {show.on_air_description && (
              <>
                <dt>On-Air Description:</dt>
                <dd><MarkdownContent content={show.on_air_description} /></dd>
              </>
            )}
            {show.caller_special_instructions && (
              <>
                <dt>Caller Special Instructions:</dt>
                <dd><MarkdownContent content={show.caller_special_instructions} /></dd>
              </>
            )}
          </dl>
        </div>

        {show.promotions_contacts.length > 0 && (
          <div className="info-section">
            <h3>Promotions Contact{show.promotions_contacts.length > 1 ? 's' : ''}</h3>
            {show.promotions_contacts.map((contact) => (
              <dl key={contact.email}>
                <dt>Name:</dt>
                <dd>{contact.name}</dd>
                <dt>Phone:</dt>
                <dd>{contact.phone}</dd>
              </dl>
            ))}
          </div>
        )}
      </div>

      <div className="passes-section">
        <h3>
          Pass Pairs ({show.available_pair_count}/{show.num_pass_pairs} available)
          <Tooltip text="On-air giveaway pairs — each pair admits 2 people. DJs give these away on air." />
        </h3>
        {isVenueOwner && userDjName && (
          <p className="field-hint">
            As a venue owner, you cannot pre-assign pass pairs to your own DJ name ({userDjName}).
          </p>
        )}
        <div className="passes-list">
          {passPairs.map((pass) => (
            <div key={pass.id} className="pass-card">
              <div className="pass-header">
                <span className="pass-status">{pass.status}</span>
              </div>

              {pass.status === 'given_away' && (
                <div className="pass-details">
                  <p>
                    <strong>Winner:</strong> {pass.recipient_name}
                  </p>
                  <p>
                    <strong>Phone:</strong> {formatPhone(pass.recipient_phone)}
                  </p>
                  <p>
                    <strong>DJ:</strong> {pass.given_away_by_dj}
                  </p>
                  <p>
                    <strong>Given away:</strong>{' '}
                    {pass.given_away_at && formatDateTime(pass.given_away_at)}
                  </p>
                </div>
              )}

              {pass.status === 'available' && (
                <div className="pass-details">
                  {pass.preassigned_dj ? (
                    <div className="preassignment-info">
                      <p>
                        <strong>Pre-assigned to:</strong> {pass.preassigned_dj}
                      </p>
                      <p>
                        <strong>Date:</strong>{' '}
                        {pass.preassigned_date &&
                          formatDate(pass.preassigned_date)}
                      </p>
                      <button
                        onClick={() => handleRemovePreassignment(pass.id)}
                        className="btn-small"
                        disabled={actionLoading}
                      >
                        Remove Pre-assignment
                      </button>
                    </div>
                  ) : preassignPassId === pass.id ? (
                    <div className="preassignment-form">
                      <div className="autocomplete-wrapper">
                        <input
                          type="text"
                          placeholder="DJ Name"
                          value={preassignDj}
                          onChange={(e) => handlePreassignDjChange(e.target.value)}
                          onKeyDown={handlePreassignDjKeyDown}
                          onBlur={handlePreassignDjBlur}
                          disabled={actionLoading}
                          autoComplete="off"
                        />
                        {showDjAutocomplete && (
                          <ul className="autocomplete-list" ref={djAutocompleteRef}>
                            {filteredDjNames.map((name) => {
                              const isSpecialty = specialtyShowNames.has(name.toLowerCase());
                              return (
                                <li
                                  key={name}
                                  onMouseDown={() => selectPreassignDj(name)}
                                  className="autocomplete-item"
                                >
                                  <span>{name}</span>
                                  <span className={isSpecialty ? 'specialty-show-badge' : 'dj-name-badge'}>
                                    {isSpecialty ? 'Specialty Show' : 'DJ'}
                                  </span>
                                </li>
                              );
                            })}
                            {filteredDjNames.length === 1 && (
                              <li className="autocomplete-hint">Press Tab to complete</li>
                            )}
                          </ul>
                        )}
                      </div>
                      {scheduleLoading && (
                        <p className="field-hint">Checking on-air schedule…</p>
                      )}
                      {scheduleDates !== null && scheduleDates.length === 0 && (
                        <p className="field-hint">
                          No scheduled on-air dates found for "{preassignDj.trim()}" in the next
                          ~4 weeks. You can still pick a date below.
                        </p>
                      )}
                      {scheduleDates !== null &&
                        scheduleDates.length > 0 &&
                        scheduleDatesBeforeClose?.length === 0 && (
                          <p className="field-hint">
                            {preassignDj.trim() || 'This DJ'} has upcoming on-air dates, but none
                            before this show closes on {formatDate(maxPreassignDate!)}. You can
                            still pick a date below.
                          </p>
                        )}
                      <DatePicker
                        value={preassignDate}
                        onChange={setPreassignDate}
                        max={maxPreassignDate}
                        disabled={actionLoading}
                        isDateDisabled={
                          scheduleDates && scheduleDates.length > 0
                            ? (date) => !scheduleDates.includes(formatDateValue(date))
                            : undefined
                        }
                      />
                      {scheduleDates !== null &&
                        preassignDate &&
                        !scheduleDates.includes(preassignDate) && (
                          <p className="field-warning">
                            The on-air schedule doesn't show {preassignDj.trim() || 'this DJ'}{' '}
                            scheduled on {formatDate(preassignDate)}. Only save this if you're sure
                            that's correct.
                          </p>
                        )}
                      <button
                        onClick={() => handlePreassignSubmit(pass.id)}
                        className="btn-small btn-primary"
                        disabled={actionLoading}
                      >
                        Save
                      </button>
                      <button
                        onClick={() => {
                          setPreassignPassId(null);
                          setPreassignDj('');
                          setPreassignDate('');
                          setScheduleDates(null);
                          lastScheduleFetchNameRef.current = null;
                        }}
                        className="btn-small"
                        disabled={actionLoading}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setPreassignPassId(pass.id)}
                      className="btn-small"
                      disabled={actionLoading}
                      title="Reserve this pass pair for a specific DJ on a chosen date. They will see it highlighted in their giveaway history."
                    >
                      Pre-assign to DJ
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {confirmAction && (
        <ConfirmModal
          action={confirmAction}
          show={show}
          userEmail={user?.email ?? null}
          onConfirm={handleConfirmedAction}
          onCancel={() => setConfirmAction(null)}
        />
      )}

      {show.attempts.length > 0 && (
        <div className="passes-section">
          <h3>Failed Giveaway Attempts ({show.attempts.length})</h3>
          <div className="passes-list">
            {show.attempts.map((attempt) => (
              <div key={attempt.id} className="pass-card">
                <p>
                  <strong>DJ:</strong> {attempt.dj_name}
                </p>
                <p>
                  <strong>At:</strong> {formatDateTime(attempt.attempted_at)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {show.lottery_enabled && lotteryStatus && (
        <div className="passes-section">
          <h3>Lottery</h3>
          {lotteryStatus.is_active ? (
            <div className="lottery-banner">
              Lottery is open. Closes:{' '}
              {lotteryStatus.deadline
                ? new Date(lotteryStatus.deadline).toLocaleString('en-US', {
                    timeZone: 'America/Los_Angeles',
                    month: 'short',
                    day: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                  })
                : '—'}
            </div>
          ) : (
            <p className="field-hint">Lottery window has closed.</p>
          )}

          <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginTop: '1rem' }}>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <h4 style={{ marginBottom: '0.5rem' }}>
                Staff Entries ({lotteryStatus.staff_entry_count})
              </h4>
              {(lotteryStatus.all_staff_entries ?? []).length === 0 ? (
                <p className="field-hint">No staff entries yet.</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {(lotteryStatus.all_staff_entries ?? []).map((e) => (
                    <li key={e.id} style={{ marginBottom: '0.25rem' }}>
                      {e.staff_name ?? `Staff #${e.staff_id}`}
                      {e.has_guest && (
                        <span style={{ color: '#666', fontSize: '0.9em' }}>
                          {' '}+ {e.guest_name ? e.guest_name : 'guest'}
                          {e.only_attend_with_guest && ' (only with guest)'}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div style={{ flex: 1, minWidth: '200px' }}>
              <h4 style={{ marginBottom: '0.5rem' }}>
                DJ Entries ({lotteryStatus.dj_entry_count})
              </h4>
              {(lotteryStatus.all_dj_entries ?? []).length === 0 ? (
                <p className="field-hint">No DJ entries yet.</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {(lotteryStatus.all_dj_entries ?? []).map((e) => (
                    <li key={e.id} style={{ marginBottom: '0.25rem' }}>
                      {e.dj_name}
                      {e.assignment_date && (
                        <span style={{ color: '#666', fontSize: '0.9em' }}>
                          {' '}({e.assignment_date})
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="passes-section">
        <h3>
          Staff Passes ({show.available_staff_count}/{show.num_pass_pairs} available)
          <Tooltip text="Staff passes allow KALX staff to attend the show. These are separate from the on-air giveaway pairs and claimed directly by staff members." />
        </h3>
        <div className="passes-list">
          {staffPasses.map((pass) => (
            <div key={pass.id} className="pass-card">
              <div className="pass-header">
                <span className="pass-status">{pass.status}</span>
              </div>

              {pass.status === 'claimed' && (
                <div className="pass-details">
                  <p>
                    <strong>Claimed by:</strong> {pass.staff_name}
                  </p>
                  <p>
                    <strong>Phone:</strong> {formatPhone(pass.staff_phone)}
                  </p>
                  <p>
                    <strong>Claimed:</strong>{' '}
                    {pass.claimed_at && formatDateTime(pass.claimed_at)}
                  </p>
                </div>
              )}

              {pass.status === 'available' && (
                <div className="pass-details">
                  <p>Available for staff to claim</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ShowDetail;
