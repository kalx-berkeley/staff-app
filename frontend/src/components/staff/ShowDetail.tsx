import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { showsAPI, passesAPI, lotteryAPI, specialtyShowsAPI } from '../../services/api';
import { Tooltip, EnrichedShowName, MarkdownContent, FeatureBinBadge, DatePicker } from '../shared';
import { formatPhone, formatDateValue } from '../../utils';
import { useAuth } from '../../contexts/authHooks';
import type { ShowResponse, StaffProfile, APIError, ClaimData, LotteryStatus, SpecialtyShowResponse } from '../../types';

const ShowDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [show, setShow] = useState<ShowResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [passActionId, setPassActionId] = useState<number | null>(null);
  const [passActionError, setPassActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [unassignLoading, setUnassignLoading] = useState<number | null>(null);
  const [preassignSelfPassId, setPreassignSelfPassId] = useState<number | null>(null);
  const [preassignSelfDate, setPreassignSelfDate] = useState('');
  const [preassignSelfLoading, setPreassignSelfLoading] = useState(false);
  // '' = first DJ name (default); 'dj:NAME' = specific DJ name; 'ss:ID' = specialty show
  const [preassignSelfReserveFor, setPreassignSelfReserveFor] = useState('');
  // On-air schedule check for preassignSelfReserveFor, to restrict/warn on the reservation date.
  // null = unknown (not yet checked, or the check failed); [] = checked, no matching dates.
  const [scheduleDates, setScheduleDates] = useState<string[] | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);

  // Specialty shows the current DJ belongs to (for specialty show pre-assignment)
  const [myDJSpecialtyShows, setMyDJSpecialtyShows] = useState<SpecialtyShowResponse[]>([]);

  // +1 guest claim state
  const [guestClaimPassId, setGuestClaimPassId] = useState<number | null>(null);
  const [guestName, setGuestName] = useState('');
  const [onlyWithGuest, setOnlyWithGuest] = useState(false);

  // Lottery state
  const [lotteryStatus, setLotteryStatus] = useState<LotteryStatus | null>(null);
  const [lotteryActionLoading, setLotteryActionLoading] = useState(false);
  const [lotteryActionError, setLotteryActionError] = useState<string | null>(null);
  // Staff lottery entry form state
  const [showStaffLotteryForm, setShowStaffLotteryForm] = useState(false);
  const [lotteryGuestName, setLotteryGuestName] = useState('');
  const [lotteryHasGuest, setLotteryHasGuest] = useState(false);
  const [lotteryOnlyWithGuest, setLotteryOnlyWithGuest] = useState(false);
  // DJ lottery entry form state
  const [showDJLotteryForm, setShowDJLotteryForm] = useState(false);
  const [lotteryDJDate, setLotteryDJDate] = useState('');
  // '' = first DJ name (default); 'dj:NAME' = specific DJ name; 'ss:ID' = specialty show
  const [lotteryDJReserveFor, setLotteryDJReserveFor] = useState('');
  // On-air schedule check for lotteryDJReserveFor, mirroring scheduleDates above.
  const [lotteryScheduleDates, setLotteryScheduleDates] = useState<string[] | null>(null);
  const [lotteryScheduleLoading, setLotteryScheduleLoading] = useState(false);

  const loadShow = useCallback(async (silent = false) => {
    if (!id) return;
    try {
      // `silent` skips the `loading` flag, which otherwise blanks the whole
      // page behind a "Loading show details…" message — used to quietly
      // re-sync after an action that can affect more than one pass (e.g. a
      // guest hold pass on claim) or has no updated-pass response to patch
      // in directly (lottery entries), without flashing the page.
      if (!silent) setLoading(true);
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
      if (!silent) setLoading(false);
    }
  }, [id]);

  const loadLotteryStatus = useCallback(async (showData: ShowResponse) => {
    if (!showData.lottery_enabled || !showData.published_at) return;
    try {
      const status = await lotteryAPI.getStatus(showData.id);
      setLotteryStatus(status);
    } catch {
      // non-fatal — lottery UI degrades gracefully
    }
  }, []);

  useEffect(() => {
    loadShow();
  }, [loadShow]);

  useEffect(() => {
    if (show) loadLotteryStatus(show);
  }, [show, loadLotteryStatus]);

  useEffect(() => {
    const staffProfile = user?.profile as StaffProfile | undefined;
    const djName = staffProfile?.dj_name;
    if (!djName) return;
    const myDJNameParts = djName.split(',').map((n) => n.trim().toLowerCase());
    specialtyShowsAPI.list().then((allShows) => {
      const mine = allShows.filter((s) =>
        s.dj_names.some((n) => myDJNameParts.includes(n.toLowerCase()))
      );
      setMyDJSpecialtyShows(mine);
    }).catch(() => {
      // non-fatal
    });
  }, [user]);

  // Resolve a "Reserve for" value ('' | 'dj:NAME' | 'ss:ID') to the plain DJ or
  // specialty-show name used to check the on-air schedule.
  const resolveReserveForName = useCallback(
    (reserveFor: string): string => {
      if (reserveFor.startsWith('ss:')) {
        const showId = parseInt(reserveFor.slice(3));
        return myDJSpecialtyShows.find((s) => s.id === showId)?.name ?? '';
      }
      if (reserveFor.startsWith('dj:')) {
        return reserveFor.slice(3);
      }
      const staffProfile = user?.profile as StaffProfile | undefined;
      const myDjName = staffProfile?.dj_name ?? '';
      return myDjName.split(',').map((n) => n.trim()).filter(Boolean)[0] ?? '';
    },
    [user, myDJSpecialtyShows]
  );

  useEffect(() => {
    if (preassignSelfPassId === null) {
      setScheduleDates(null);
      return;
    }
    const name = resolveReserveForName(preassignSelfReserveFor);
    if (!name) {
      setScheduleDates(null);
      return;
    }
    let cancelled = false;
    setScheduleLoading(true);
    passesAPI
      .getPreassignSchedule(name)
      .then((dates) => {
        if (cancelled) return;
        setScheduleDates(dates);
      })
      .catch(() => {
        if (cancelled) return;
        setScheduleDates(null);
      })
      .finally(() => {
        if (!cancelled) setScheduleLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [preassignSelfPassId, preassignSelfReserveFor, resolveReserveForName]);

  useEffect(() => {
    if (!showDJLotteryForm) {
      setLotteryScheduleDates(null);
      return;
    }
    const name = resolveReserveForName(lotteryDJReserveFor);
    if (!name) {
      setLotteryScheduleDates(null);
      return;
    }
    let cancelled = false;
    setLotteryScheduleLoading(true);
    passesAPI
      .getPreassignSchedule(name)
      .then((dates) => {
        if (cancelled) return;
        setLotteryScheduleDates(dates);
      })
      .catch(() => {
        if (cancelled) return;
        setLotteryScheduleDates(null);
      })
      .finally(() => {
        if (!cancelled) setLotteryScheduleLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [showDJLotteryForm, lotteryDJReserveFor, resolveReserveForName]);

  const showEphemeralSuccess = (msg: string) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  };

  const handleClaimPass = async (passId: number, claimData?: ClaimData) => {
    setPassActionId(passId);
    setPassActionError(null);
    setSuccessMessage(null);
    try {
      await passesAPI.claim(passId, claimData);
      const msg = claimData?.has_guest
        ? 'Pass claimed with +1 guest reservation!'
        : 'Pass claimed successfully!';
      showEphemeralSuccess(msg);
      setGuestClaimPassId(null);
      setGuestName('');
      setOnlyWithGuest(false);
      await loadShow(true);
    } catch (err) {
      const apiError = err as APIError;
      setPassActionError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to claim pass'
      );
    } finally {
      setPassActionId(null);
    }
  };

  const handleGuestClaimSubmit = async (passId: number) => {
    if (!show) return;
    const needsName = show.venue.staff_guest_requires_name;
    if (needsName && !guestName.trim()) {
      setPassActionError('Guest name is required for this venue');
      return;
    }
    await handleClaimPass(passId, {
      has_guest: true,
      guest_name: guestName.trim() || null,
      only_attend_with_guest: onlyWithGuest,
    });
  };

  const handleUnassignSelf = async (passId: number) => {
    setUnassignLoading(passId);
    setPassActionError(null);
    setSuccessMessage(null);
    try {
      const updatedPass = await passesAPI.removePreassignment(passId);
      // Patch just this pass into local state instead of re-fetching the whole
      // show — loadShow() flips `loading`, which blanks the entire page behind
      // a "Loading show details…" message for what should be a quiet update.
      setShow((prev) =>
        prev
          ? { ...prev, passes: prev.passes.map((p) => (p.id === updatedPass.id ? updatedPass : p)) }
          : prev
      );
      showEphemeralSuccess('Pre-assignment removed.');
    } catch (err) {
      const apiError = err as APIError;
      setPassActionError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to remove pre-assignment'
      );
    } finally {
      setUnassignLoading(null);
    }
  };

  const handleReleasePass = async (passId: number) => {
    setPassActionId(passId);
    setPassActionError(null);
    setSuccessMessage(null);
    try {
      await passesAPI.releaseClaim(passId);
      showEphemeralSuccess('Pass released.');
      await loadShow(true);
    } catch (err) {
      const apiError = err as APIError;
      setPassActionError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to release pass'
      );
    } finally {
      setPassActionId(null);
    }
  };

  const handleSelfPreassignSubmit = async (passId: number) => {
    if (!preassignSelfDate) {
      setPassActionError('A date is required for pre-assignment');
      return;
    }
    setPreassignSelfLoading(true);
    setPassActionError(null);
    setSuccessMessage(null);
    try {
      const specialtyShowId = preassignSelfReserveFor.startsWith('ss:')
        ? parseInt(preassignSelfReserveFor.slice(3))
        : undefined;
      const djNameOverride = preassignSelfReserveFor.startsWith('dj:')
        ? preassignSelfReserveFor.slice(3)
        : undefined;
      const updatedPass = await passesAPI.selfPreassign(passId, {
        assignment_date: preassignSelfDate,
        specialty_show_id: specialtyShowId,
        dj_name_override: djNameOverride,
      });
      // Patch just this pass into local state instead of re-fetching the whole
      // show — see handleUnassignSelf for why loadShow() isn't used here.
      setShow((prev) =>
        prev
          ? { ...prev, passes: prev.passes.map((p) => (p.id === updatedPass.id ? updatedPass : p)) }
          : prev
      );
      setPreassignSelfPassId(null);
      setPreassignSelfDate('');
      setPreassignSelfReserveFor('');
      showEphemeralSuccess('Pass pre-assigned successfully!');
    } catch (err) {
      const apiError = err as APIError;
      setPassActionError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to set pre-assignment'
      );
    } finally {
      setPreassignSelfLoading(false);
    }
  };

  const handleEnterStaffLottery = async () => {
    if (!show) return;
    if (show.venue.staff_guest_requires_name && lotteryHasGuest && !lotteryGuestName.trim()) {
      setLotteryActionError('Guest name is required for this venue');
      return;
    }
    setLotteryActionLoading(true);
    setLotteryActionError(null);
    try {
      await lotteryAPI.enterStaff(show.id, {
        has_guest: lotteryHasGuest,
        guest_name: lotteryHasGuest ? (lotteryGuestName.trim() || null) : null,
        only_attend_with_guest: lotteryHasGuest ? lotteryOnlyWithGuest : false,
      });
      setShowStaffLotteryForm(false);
      setLotteryHasGuest(false);
      setLotteryGuestName('');
      setLotteryOnlyWithGuest(false);
      showEphemeralSuccess("You've entered the lottery! You'll receive an email with the result after the lottery closes.");
      await loadShow(true);
    } catch (err) {
      const apiError = err as APIError;
      setLotteryActionError(typeof apiError.detail === 'string' ? apiError.detail : 'Failed to enter lottery');
    } finally {
      setLotteryActionLoading(false);
    }
  };

  const handleWithdrawStaffLottery = async () => {
    if (!show) return;
    setLotteryActionLoading(true);
    setLotteryActionError(null);
    try {
      await lotteryAPI.withdrawStaff(show.id);
      setLotteryStatus(null);
      showEphemeralSuccess('Your lottery entry has been withdrawn.');
      await loadShow(true);
    } catch (err) {
      const apiError = err as APIError;
      setLotteryActionError(typeof apiError.detail === 'string' ? apiError.detail : 'Failed to withdraw entry');
    } finally {
      setLotteryActionLoading(false);
    }
  };

  const handleEnterDJLottery = async () => {
    if (!show || !lotteryDJDate) {
      setLotteryActionError('A date is required');
      return;
    }
    setLotteryActionLoading(true);
    setLotteryActionError(null);
    try {
      const lotterySpecialtyShowId = lotteryDJReserveFor.startsWith('ss:')
        ? parseInt(lotteryDJReserveFor.slice(3))
        : undefined;
      const lotteryDjNameOverride = lotteryDJReserveFor.startsWith('dj:')
        ? lotteryDJReserveFor.slice(3)
        : undefined;
      await lotteryAPI.enterDJ(show.id, {
        assignment_date: lotteryDJDate,
        specialty_show_id: lotterySpecialtyShowId,
        dj_name_override: lotteryDjNameOverride,
      });
      setShowDJLotteryForm(false);
      setLotteryDJDate('');
      setLotteryDJReserveFor('');
      showEphemeralSuccess("You've entered the lottery for a pass pair! You'll receive an email with the result after the lottery closes.");
      await loadShow(true);
    } catch (err) {
      const apiError = err as APIError;
      setLotteryActionError(typeof apiError.detail === 'string' ? apiError.detail : 'Failed to enter lottery');
    } finally {
      setLotteryActionLoading(false);
    }
  };

  const handleWithdrawDJLottery = async () => {
    if (!show) return;
    setLotteryActionLoading(true);
    setLotteryActionError(null);
    try {
      await lotteryAPI.withdrawDJ(show.id);
      setLotteryStatus(null);
      showEphemeralSuccess('Your DJ lottery entry has been withdrawn.');
      await loadShow(true);
    } catch (err) {
      const apiError = err as APIError;
      setLotteryActionError(typeof apiError.detail === 'string' ? apiError.detail : 'Failed to withdraw entry');
    } finally {
      setLotteryActionLoading(false);
    }
  };

  const formatAgeRestriction = (age: string) =>
    age === 'all_ages' ? 'All Ages' : age;

  const formatDate = (dateStr: string) => {
    const [y, m, d] = dateStr.split('-').map(Number);
    const date = new Date(y, m - 1, d);
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatTime = (timeStr: string) => {
    const [hours, minutes] = timeStr.split(':');
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 || 12;
    return `${displayHour}:${minutes} ${ampm}`;
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

  const formatDateTime = (dateTimeStr: string) => {
    const date = new Date(dateTimeStr);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  if (loading) {
    return <div className="loading">Loading show details...</div>;
  }

  if (error || !show) {
    return (
      <div className="error">
        <p>Error: {error || 'Show not found'}</p>
        <button onClick={() => navigate('/staff/shows')} className="btn-secondary">
          Back to Shows
        </button>
      </div>
    );
  }

  const staffPasses = show.passes.filter((p) => p.pass_type === 'staff');
  const availableStaffCount = staffPasses.filter((p) => p.status === 'available').length;
  const guestHoldPassCount = staffPasses.filter((p) => p.status === 'claimed' && p.guest_of_pass_id !== null).length;
  const displayAvailableCount = availableStaffCount + guestHoldPassCount;
  const canClaimWithGuest = availableStaffCount >= 2;
  const myName = user?.profile?.name ?? null;
  const mySpecialtyShowIds = new Set(myDJSpecialtyShows.map((s) => s.id));
  const myPreassignedPasses = myName
    ? show.passes.filter(
        (p) =>
          p.pass_type === 'pair' &&
          p.status === 'available' &&
          p.preassigned_dj?.toLowerCase() === myName.toLowerCase()
      )
    : [];
  const staffProfile = user?.profile as StaffProfile | undefined;
  const isSublistDj = staffProfile?.is_sublist_dj ?? false;
  const myDjName = staffProfile?.dj_name ?? null;
  const myDjNames = myDjName ? myDjName.split(',').map((n) => n.trim()).filter(Boolean) : [];
  const pairPasses = show.passes.filter((p) => p.pass_type === 'pair');
  const isVenueOwner = user?.email ? show.venue.owner_emails.includes(user.email) : false;
  const showReserveForDropdown = myDjNames.length > 1 || myDJSpecialtyShows.length > 0;

  const lotteryDeadline = show.published_at
    ? new Date(new Date(show.published_at).getTime() + show.lottery_window_hours * 3600000)
    : null;
  // Use authoritative is_active from backend when loaded (accounts for early "Run now" execution);
  // fall back to time-based check before the status loads.
  const lotteryActive = lotteryStatus !== null
    ? lotteryStatus.is_active
    : show.lottery_enabled && lotteryDeadline !== null && new Date() < lotteryDeadline;
  const myStaffEntry = lotteryStatus?.my_staff_entry ?? null;
  const myDJEntry = lotteryStatus?.my_dj_entry ?? null;

  const formatLotteryDeadline = (d: Date) =>
    d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

  // First date on or after which DJ pass-pair reservations are prohibited
  // (within `dj_preassign_prohibition_days` of the planned close date).
  let prohibitedFromDate: Date | null = null;
  if (show.dj_preassign_prohibition_days != null && show.planned_close_date) {
    const closeDate = new Date(show.planned_close_date + 'T00:00:00');
    prohibitedFromDate = new Date(closeDate);
    prohibitedFromDate.setDate(prohibitedFromDate.getDate() - show.dj_preassign_prohibition_days);
  }

  const toDateInputValue = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

  // Latest date selectable in the DJ reservation/lottery date pickers.
  // PassService.set_preassignment rejects any date after `planned_close_date`
  // regardless of the prohibition-window setting below, so that's the real
  // ceiling — not the show date — whenever it's set and earlier.
  let maxDJReservationDate = show.show_date;
  if (show.planned_close_date && show.planned_close_date < maxDJReservationDate) {
    maxDJReservationDate = show.planned_close_date;
  }
  if (prohibitedFromDate) {
    const lastAllowed = new Date(prohibitedFromDate);
    lastAllowed.setDate(lastAllowed.getDate() - 1);
    const lastAllowedStr = toDateInputValue(lastAllowed);
    if (lastAllowedStr < maxDJReservationDate) {
      maxDJReservationDate = lastAllowedStr;
    }
  }

  // Of the checked schedule dates, which fall on or before the reservation
  // deadline above — the actual pickable range.
  const scheduleDatesBeforeClose =
    scheduleDates?.filter((d) => d <= maxDJReservationDate) ?? null;
  const lotteryScheduleDatesBeforeClose =
    lotteryScheduleDates?.filter((d) => d <= maxDJReservationDate) ?? null;

  return (
    <div className="show-detail">
      <div className="page-header">
        <button onClick={() => navigate('/staff/shows')} className="btn-back">
          ← Back to Shows
        </button>
        <h2><EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} /></h2>
        {show.in_feature_bin && (
          <div style={{ marginTop: '0.25rem' }}>
            <FeatureBinBadge releases={show.feature_bin_releases} />
          </div>
        )}
      </div>

      {successMessage && (
        <div className="success-message">{successMessage}</div>
      )}

      {passActionError && (
        <div className="error-message">{passActionError}</div>
      )}

      <div className="show-detail-content">
        <div className="show-info-section">
          <h3>Show Information</h3>

          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">Genre:</span>
              <span className="info-value">{(show.genre ?? []).join(', ')}</span>
            </div>

            <div className="info-item">
              <span className="info-label">Venue:</span>
              <span className="info-value">{show.venue.name}</span>
            </div>

            <div className="info-item">
              <span className="info-label">Address:</span>
              <span className="info-value">{show.venue.address}</span>
            </div>

            <div className="info-item">
              <span className="info-label">{show.show_start_date ? 'Dates:' : 'Date:'}</span>
              <span className="info-value">{show.show_start_date ? formatDateRange(show.show_start_date, show.show_date) : formatDate(show.show_date)}</span>
            </div>

            {!show.show_start_date && (
            <div className="info-item">
              <span className="info-label">Time:</span>
              <span className="info-value">{formatTime(show.show_time!)}</span>
            </div>
            )}

            <div className="info-item">
              <span className="info-label">Age Restriction:</span>
              <span className="info-value">{formatAgeRestriction(show.age_restriction)}</span>
            </div>

            <div className="info-item">
              <span className="info-label">Wheelchair Accessible:</span>
              <span className="info-value">
                {show.wheelchair_accessible ? 'Yes' : 'No'}
              </span>
            </div>

            {show.on_air_description && (
              <div className="info-item full-width">
                <span className="info-label">On-Air Description:</span>
                <MarkdownContent content={show.on_air_description} />
              </div>
            )}

            {show.caller_special_instructions && (
              <div className="info-item full-width">
                <span className="info-label">Caller Special Instructions:</span>
                <MarkdownContent content={show.caller_special_instructions} />
              </div>
            )}
          </div>
        </div>

        {show.promotions_contacts.length > 0 && (
          <div className="show-info-section">
            <h3>Promotions Contact{show.promotions_contacts.length > 1 ? 's' : ''}</h3>
            {show.promotions_contacts.map((contact) => (
              <div key={contact.email} className="info-grid">
                <div className="info-item">
                  <span className="info-label">Name:</span>
                  <span className="info-value">{contact.name}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Phone:</span>
                  <span className="info-value">{contact.phone}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {myPreassignedPasses.length > 0 && (
          <div className="pass-claim-section">
            <h3>Your Pre-assigned Pass Pair{myPreassignedPasses.length > 1 ? 's' : ''}</h3>
            <p className="pass-available-note">
              A promotions staff member has reserved a pass pair for you for this show.
            </p>
            <div className="passes-list">
              {myPreassignedPasses.map((pass) => (
                <div key={pass.id} className="pass-card">
                  <div className="pass-details">
                    <p><strong>Pre-assigned to:</strong> {pass.preassigned_dj}</p>
                    {pass.preassigned_date && (
                      <p><strong>Date:</strong> {pass.preassigned_date}</p>
                    )}
                    <button
                      onClick={() => handleUnassignSelf(pass.id)}
                      className="btn-small"
                      disabled={unassignLoading === pass.id}
                      title="Remove this pre-assignment so the pass becomes available to any DJ."
                    >
                      {unassignLoading === pass.id ? 'Removing…' : 'Unassign Me'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {isSublistDj && myDjName && isVenueOwner && (
          <div className="pass-claim-section">
            <h3>Reserve Pass Pair for On-Air Giveaway</h3>
            <p className="pass-unavailable-note">
              Promotions venue owners cannot reserve pass pairs for shows at their own venues.
            </p>
          </div>
        )}

        {isSublistDj && myDjName && !isVenueOwner && (
          <div className="pass-claim-section">
            <h3>
              Reserve Pass Pair for On-Air Giveaway
              <Tooltip text="Reserve a pass pair for yourself to give away on-air on a future date. The passes will be held under your DJ name until the air date." />
            </h3>

            {lotteryActive && lotteryDeadline && (
              <div className="lottery-banner">
                <strong>Lottery mode is active.</strong> Reserving a pass pair during this window
                enters you into a lottery instead of reserving immediately. The lottery closes on{' '}
                {formatLotteryDeadline(lotteryDeadline)}.
                <Tooltip text={`During the first ${show.lottery_window_hours} hours after publication, all DJ reservation requests are pooled. After the window closes, winners are drawn randomly and will receive a confirmation email.`} />
              </div>
            )}

            {prohibitedFromDate && (
              <div className="field-hint" style={{ marginBottom: '0.5rem' }}>
                Reservations are not allowed for shifts on or after{' '}
                <strong>
                  {prohibitedFromDate.toLocaleDateString('en-US', {
                    month: 'short', day: 'numeric', year: 'numeric',
                  })}
                </strong>{' '}
                (within {show.dj_preassign_prohibition_days} day
                {show.dj_preassign_prohibition_days !== 1 ? 's' : ''} of the planned close date).
              </div>
            )}

            {lotteryActionError && (
              <p className="field-error">{lotteryActionError}</p>
            )}

            {lotteryActive ? (
              myDJEntry ? (
                <div className="lottery-entry-confirmation">
                  <p>You have entered the lottery for a pass pair.</p>
                  {myDJEntry.assignment_date && (
                    <p><strong>Requested date:</strong> {myDJEntry.assignment_date}</p>
                  )}
                  <button
                    onClick={handleWithdrawDJLottery}
                    className="btn-small"
                    disabled={lotteryActionLoading}
                  >
                    {lotteryActionLoading ? 'Withdrawing…' : 'Withdraw Entry'}
                  </button>
                </div>
              ) : showDJLotteryForm ? (
                <div className="passes-list">
                  <div className="pass-card">
                    <div className="preassignment-form">
                      {showReserveForDropdown ? (
                        <div className="form-group">
                          <label htmlFor="lottery-reserve-for">Reserve for:</label>
                          <select
                            id="lottery-reserve-for"
                            value={lotteryDJReserveFor}
                            onChange={(e) => setLotteryDJReserveFor(e.target.value)}
                            disabled={lotteryActionLoading}
                          >
                            {myDjNames.map((name, i) => (
                              <option key={name} value={i === 0 ? '' : `dj:${name}`}>
                                {name} (my DJ name)
                              </option>
                            ))}
                            {myDJSpecialtyShows.map((s) => (
                              <option key={s.id} value={`ss:${s.id}`}>
                                {s.name} (specialty show)
                              </option>
                            ))}
                          </select>
                        </div>
                      ) : (
                        <input
                          type="text"
                          value={myDjNames[0] ?? ''}
                          readOnly
                          disabled
                          className="input-readonly"
                        />
                      )}
                      {lotteryScheduleLoading && (
                        <p className="field-hint">Checking on-air schedule…</p>
                      )}
                      {lotteryScheduleDates !== null && lotteryScheduleDates.length === 0 && (
                        <p className="field-hint">
                          No scheduled on-air dates found in the next ~8 weeks. You can still pick
                          a date below.
                        </p>
                      )}
                      {lotteryScheduleDates !== null &&
                        lotteryScheduleDates.length > 0 &&
                        lotteryScheduleDatesBeforeClose?.length === 0 && (
                          <p className="field-hint">
                            You have upcoming on-air dates, but none before the reservation
                            deadline ({formatDate(maxDJReservationDate)}). You can still pick a
                            date below.
                          </p>
                        )}
                      <DatePicker
                        value={lotteryDJDate}
                        onChange={setLotteryDJDate}
                        max={maxDJReservationDate}
                        disabled={lotteryActionLoading}
                        isDateDisabled={
                          lotteryScheduleDates && lotteryScheduleDates.length > 0
                            ? (date) => !lotteryScheduleDates.includes(formatDateValue(date))
                            : undefined
                        }
                      />
                      {lotteryScheduleDates !== null &&
                        lotteryDJDate &&
                        !lotteryScheduleDates.includes(lotteryDJDate) && (
                          <p className="field-warning">
                            The on-air schedule doesn't show you on {formatDate(lotteryDJDate)}.
                            Only enter the lottery for this date if you're sure that's correct.
                          </p>
                        )}
                      <button
                        onClick={handleEnterDJLottery}
                        className="btn-small btn-primary"
                        disabled={lotteryActionLoading || !lotteryDJDate}
                      >
                        {lotteryActionLoading ? 'Entering…' : 'Enter Lottery'}
                      </button>
                      <button
                        onClick={() => { setShowDJLotteryForm(false); setLotteryDJDate(''); setLotteryDJReserveFor(''); }}
                        className="btn-small"
                        disabled={lotteryActionLoading}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowDJLotteryForm(true)}
                  className="btn-small"
                  title="Enter the lottery for a pass pair to give away on-air."
                >
                  Enter Lottery for Pass Pair
                </button>
              )
            ) : (
              <div className="passes-list">
                {pairPasses.map((pass) => {
                  const isMyDJPass =
                    pass.preassigned_dj?.toLowerCase() === myDjName.toLowerCase();
                  const isMySpecialtyShowPass =
                    pass.preassigned_specialty_show_id !== null &&
                    mySpecialtyShowIds.has(pass.preassigned_specialty_show_id!);
                  const isMyPass = isMyDJPass || isMySpecialtyShowPass;
                  const isOtherPass = pass.preassigned_dj && !isMyPass;
                  return (
                    <div key={pass.id} className="pass-card">
                      {pass.status === 'available' && isMyPass ? (
                        <div className="pass-details">
                          <div className="preassignment-info">
                            <p>
                              <strong>Pre-assigned to:</strong> {pass.preassigned_dj}
                              {pass.preassigned_specialty_show_name && (
                                <span className="specialty-show-badge"> (Specialty Show)</span>
                              )}
                            </p>
                            {pass.preassigned_date && (
                              <p>
                                <strong>Date:</strong> {pass.preassigned_date}
                              </p>
                            )}
                            <button
                              onClick={() => handleUnassignSelf(pass.id)}
                              className="btn-small"
                              disabled={unassignLoading === pass.id}
                            >
                              {unassignLoading === pass.id ? 'Removing…' : 'Release Reservation'}
                            </button>
                          </div>
                        </div>
                      ) : pass.status === 'available' && !isOtherPass ? (
                        <div className="pass-details">
                          {preassignSelfPassId === pass.id ? (
                            <div className="preassignment-form">
                              {showReserveForDropdown ? (
                                <div className="form-group">
                                  <label htmlFor={`reserve-for-${pass.id}`}>Reserve for:</label>
                                  <select
                                    id={`reserve-for-${pass.id}`}
                                    value={preassignSelfReserveFor}
                                    onChange={(e) => setPreassignSelfReserveFor(e.target.value)}
                                    disabled={preassignSelfLoading}
                                  >
                                    {myDjNames.map((name, i) => (
                                      <option key={name} value={i === 0 ? '' : `dj:${name}`}>
                                        {name} (my DJ name)
                                      </option>
                                    ))}
                                    {myDJSpecialtyShows.map((s) => (
                                      <option key={s.id} value={`ss:${s.id}`}>
                                        {s.name} (specialty show)
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              ) : (
                                <input
                                  type="text"
                                  value={myDjNames[0] ?? ''}
                                  readOnly
                                  disabled
                                  className="input-readonly"
                                />
                              )}
                              {scheduleLoading && (
                                <p className="field-hint">Checking on-air schedule…</p>
                              )}
                              {scheduleDates !== null && scheduleDates.length === 0 && (
                                <p className="field-hint">
                                  No scheduled on-air dates found in the next ~8 weeks. You can
                                  still pick a date below.
                                </p>
                              )}
                              {scheduleDates !== null &&
                                scheduleDates.length > 0 &&
                                scheduleDatesBeforeClose?.length === 0 && (
                                  <p className="field-hint">
                                    You have upcoming on-air dates, but none before the
                                    reservation deadline ({formatDate(maxDJReservationDate)}). You
                                    can still pick a date below.
                                  </p>
                                )}
                              <DatePicker
                                value={preassignSelfDate}
                                onChange={setPreassignSelfDate}
                                max={maxDJReservationDate}
                                disabled={preassignSelfLoading}
                                isDateDisabled={
                                  scheduleDates && scheduleDates.length > 0
                                    ? (date) => !scheduleDates.includes(formatDateValue(date))
                                    : undefined
                                }
                              />
                              {scheduleDates !== null &&
                                preassignSelfDate &&
                                !scheduleDates.includes(preassignSelfDate) && (
                                  <p className="field-warning">
                                    The on-air schedule doesn't show you on{' '}
                                    {formatDate(preassignSelfDate)}. Only save this if you're sure
                                    that's correct.
                                  </p>
                                )}
                              <button
                                onClick={() => handleSelfPreassignSubmit(pass.id)}
                                className="btn-small btn-primary"
                                disabled={preassignSelfLoading}
                              >
                                {preassignSelfLoading ? 'Saving…' : 'Save'}
                              </button>
                              <button
                                onClick={() => {
                                  setPreassignSelfPassId(null);
                                  setPreassignSelfDate('');
                                  setPreassignSelfReserveFor('');
                                }}
                                className="btn-small"
                                disabled={preassignSelfLoading}
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setPreassignSelfPassId(pass.id)}
                              className="btn-small"
                              title="Reserve this pass pair to give away on-air on a chosen date."
                            >
                              Reserve for On-Air Giveaway
                            </button>
                          )}
                        </div>
                      ) : (
                        <div className="pass-details">
                          {pass.status === 'available' && isOtherPass ? (
                            <p className="pass-unavailable-note">
                              Pre-assigned to {pass.preassigned_dj}
                            </p>
                          ) : (
                            <p className="pass-unavailable-note">
                              {pass.status === 'given_away' ? 'Given away' : pass.status}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div className="pass-claim-section">
          <h3>
            Staff Passes ({displayAvailableCount} of {staffPasses.length} available)
            <Tooltip text="Claim a staff pass to attend this show. Each pass admits 1 person. You can also reserve a +1 guest slot if two passes are available. You can release your claim if your plans change (while the show is still open)." />
          </h3>

          {lotteryActive && lotteryDeadline && (
            <div className="lottery-banner">
              <strong>Lottery mode is active.</strong> Claiming a pass during this window enters
              you into a lottery instead of claiming immediately. The lottery closes on{' '}
              {formatLotteryDeadline(lotteryDeadline)}.
              <Tooltip text={`During the first ${show.lottery_window_hours} hours after publication, all staff claim requests are pooled. After the window closes, winners are drawn randomly and will receive a confirmation email.`} />
            </div>
          )}

          {lotteryActionError && (
            <p className="field-error">{lotteryActionError}</p>
          )}

          {lotteryActive && (
            myStaffEntry ? (
              <div className="lottery-entry-confirmation">
                <p>You have entered the lottery for a staff pass.</p>
                {myStaffEntry.has_guest && (
                  <p>
                    +1 guest requested{myStaffEntry.guest_name ? `: ${myStaffEntry.guest_name}` : ''}
                    {myStaffEntry.only_attend_with_guest ? ' (release pass if guest cannot attend)' : ''}
                  </p>
                )}
                <button
                  onClick={handleWithdrawStaffLottery}
                  className="btn-small"
                  disabled={lotteryActionLoading}
                >
                  {lotteryActionLoading ? 'Withdrawing…' : 'Withdraw Entry'}
                </button>
              </div>
            ) : showStaffLotteryForm ? (
              <div className="guest-claim-form">
                <fieldset className="form-group radio-group">
                  <legend>I'm requesting:</legend>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="lottery-pass-type"
                      checked={!lotteryHasGuest}
                      onChange={() => setLotteryHasGuest(false)}
                      disabled={lotteryActionLoading}
                    />
                    {' '}A pass for myself
                  </label>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="lottery-pass-type"
                      checked={lotteryHasGuest}
                      onChange={() => setLotteryHasGuest(true)}
                      disabled={lotteryActionLoading}
                    />
                    {' '}A pass for me and a guest
                  </label>
                </fieldset>
                {lotteryHasGuest && (
                  <>
                    {show.venue.staff_guest_requires_name && (
                      <div className="form-group">
                        <label htmlFor="lottery-guest-name">Guest name (required by this venue):</label>
                        <input
                          id="lottery-guest-name"
                          type="text"
                          value={lotteryGuestName}
                          onChange={(e) => setLotteryGuestName(e.target.value)}
                          placeholder="Guest full name"
                          className="input-text"
                          disabled={lotteryActionLoading}
                        />
                      </div>
                    )}
                    <fieldset className="form-group radio-group">
                      <legend>If there aren't enough passes for my guest to attend:</legend>
                      <label className="radio-label">
                        <input
                          type="radio"
                          name="lottery-only-with-guest"
                          checked={!lotteryOnlyWithGuest}
                          onChange={() => setLotteryOnlyWithGuest(false)}
                        />
                        {' '}I'll still attend without them
                      </label>
                      <label className="radio-label">
                        <input
                          type="radio"
                          name="lottery-only-with-guest"
                          checked={lotteryOnlyWithGuest}
                          onChange={() => setLotteryOnlyWithGuest(true)}
                        />
                        {' '}Release my pass too (cancel both)
                      </label>
                    </fieldset>
                  </>
                )}
                <div className="form-actions">
                  <button
                    onClick={handleEnterStaffLottery}
                    className="btn-small btn-primary"
                    disabled={lotteryActionLoading}
                  >
                    {lotteryActionLoading ? 'Entering…' : 'Enter Lottery'}
                  </button>
                  <button
                    onClick={() => { setShowStaffLotteryForm(false); setLotteryHasGuest(false); setLotteryGuestName(''); setLotteryOnlyWithGuest(false); }}
                    className="btn-small"
                    disabled={lotteryActionLoading}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowStaffLotteryForm(true)}
                className="btn-small btn-primary"
                title="Enter the lottery for a staff pass to attend this show."
              >
                Enter Lottery
              </button>
            )
          )}

          <div className="passes-list">
            {staffPasses.map((pass) => {
              const isGuestHold = pass.status === 'claimed' && pass.guest_of_pass_id != null;
              const isPrimaryWithGuest = pass.status === 'claimed' && pass.has_guest;

              if (pass.status === 'claimed' && !isGuestHold) {
                return (
                  <div key={pass.id} className="pass-card">
                    <div className="pass-details">
                      <p><strong>Claimed by:</strong> {pass.staff_name ?? '(name not recorded)'}</p>
                      {isPrimaryWithGuest && (
                        <p className="pass-guest-note">
                          +1 guest reserved
                          {pass.guest_name ? `: ${pass.guest_name}` : ''}
                          {pass.only_attend_with_guest ? " (staff will release if guest can't attend)" : ''}
                          {' '}— <em>not confirmed until show closes</em>
                        </p>
                      )}
                      {pass.staff_phone && <p><strong>Phone:</strong> {formatPhone(pass.staff_phone)}</p>}
                      {pass.claimed_at && (
                        <p><strong>Claimed:</strong> {formatDateTime(pass.claimed_at)}</p>
                      )}
                      <button
                        onClick={() => handleReleasePass(pass.id)}
                        className="btn-small"
                        disabled={show.status === 'closed' || passActionId === pass.id}
                        title="Release your claim if you can no longer attend the show."
                      >
                        {passActionId === pass.id ? 'Releasing...' : 'Release'}
                      </button>
                      {show.status === 'closed' && (
                        <p className="pass-closed-note">Show is closed — cannot release.</p>
                      )}
                    </div>
                  </div>
                );
              }

              if (isGuestHold) {
                return (
                  <div key={pass.id} className="pass-card">
                    <div className="pass-details">
                      <p className="pass-available-note">Available</p>
                      {show.status !== 'closed' && (
                        <div className="claim-buttons">
                          <button
                            onClick={() => handleClaimPass(pass.id)}
                            className="btn-small btn-primary"
                            disabled={passActionId === pass.id}
                          >
                            {passActionId === pass.id ? 'Claiming...' : 'Claim'}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              }

              // Available pass
              return (
                <div key={pass.id} className="pass-card">
                  <div className="pass-details">
                    <p className={show.status === 'closed' ? 'pass-unavailable-note' : 'pass-available-note'}>
                      {show.status === 'closed' ? 'Unavailable' : 'Available'}
                    </p>
                    {show.status !== 'closed' && !lotteryActive && (
                      <>
                        {guestClaimPassId === pass.id ? (
                          <div className="guest-claim-form">
                            <p className="guest-claim-info">
                              You're claiming this pass with a +1 guest. Your guest's spot is not
                              guaranteed — if another staff member claims a pass, your guest may be
                              bumped. You'll be notified immediately if that happens, and again when
                              the show closes to confirm whether your guest can attend.
                            </p>
                            {show.venue.staff_guest_requires_name && (
                              <div className="form-group">
                                <label htmlFor="guest-name">Guest name (required by this venue):</label>
                                <input
                                  id="guest-name"
                                  type="text"
                                  value={guestName}
                                  onChange={(e) => setGuestName(e.target.value)}
                                  placeholder="Guest full name"
                                  className="input-text"
                                />
                              </div>
                            )}
                            <fieldset className="form-group radio-group">
                              <legend>If my guest can't attend:</legend>
                              <label className="radio-label">
                                <input
                                  type="radio"
                                  name="only-with-guest"
                                  checked={!onlyWithGuest}
                                  onChange={() => setOnlyWithGuest(false)}
                                />
                                {' '}I'll still attend without them
                              </label>
                              <label className="radio-label">
                                <input
                                  type="radio"
                                  name="only-with-guest"
                                  checked={onlyWithGuest}
                                  onChange={() => setOnlyWithGuest(true)}
                                />
                                {' '}Release my pass too (cancel both)
                              </label>
                            </fieldset>
                            <div className="form-actions">
                              <button
                                onClick={() => handleGuestClaimSubmit(pass.id)}
                                className="btn-small btn-primary"
                                disabled={passActionId === pass.id}
                              >
                                {passActionId === pass.id ? 'Claiming...' : 'Claim with +1'}
                              </button>
                              <button
                                onClick={() => { setGuestClaimPassId(null); setGuestName(''); setOnlyWithGuest(false); setPassActionError(null); }}
                                className="btn-small"
                                disabled={passActionId === pass.id}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="claim-buttons">
                            <button
                              onClick={() => handleClaimPass(pass.id)}
                              className="btn-small btn-primary"
                              disabled={passActionId === pass.id}
                              title="Claim this staff pass to attend the show (1 person)."
                            >
                              {passActionId === pass.id ? 'Claiming...' : 'Claim'}
                            </button>
                            {canClaimWithGuest && (
                              <button
                                onClick={() => { setGuestClaimPassId(pass.id); setGuestName(''); setOnlyWithGuest(false); }}
                                className="btn-small"
                                disabled={passActionId === pass.id}
                                title="Claim this pass and reserve a second pass for a +1 guest. Guest spot is tentative until show closes."
                              >
                                Claim with +1 Guest
                              </button>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ShowDetail;
