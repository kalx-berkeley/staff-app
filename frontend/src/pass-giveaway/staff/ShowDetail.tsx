import { useState, useEffect, useCallback } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { showsAPI, passesAPI, lotteryAPI, alternatesAPI } from '../api';
import { Tooltip, EnrichedShowName, FeatureBinBadge, KalxLiveBadge, DatePicker, AlternateQueueList, AlternateGuestForm, WaitingGuestsList, GuestFallbackOptions, ClaimGuestActions, TablerPassesSection, ShowInfoCards } from '../components';
import { formatPhone, formatLeave, isOnLeave, leaveCoversShow, formatDateValue } from '../../common/utils';
import { useAuth } from '../../common/contexts/authHooks';
import { usePageTitle } from '../../common/hooks/usePageTitle';
import { STAFF_PASSES_NOT_YET_ACTIVE, ageCheckMessage, guestAgeNote, seatedFallbackNote, specialtyShowLabel, staffPassesNotYetActive, waitingFallbackNote } from '../utils';
import type { ShowResponse, ClaimData, LotteryStatus, MyIdentity, IdentityChoice, AlternateQueue, AlternateJoinRequest, GuestFallback } from '../types';
import type { StaffProfile, APIError } from '../../common/types';
import { formatCalendarDate, formatPacific } from '../../common/dateTime';
import { useMyAgeChecks } from '../useMyAgeChecks';

const ShowDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const ageChecks = useMyAgeChecks(!!user?.profile);
  const [show, setShow] = useState<ShowResponse | null>(null);
  usePageTitle(`${show?.event_name ?? 'Show'} · Staff`);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [passActionId, setPassActionId] = useState<number | null>(null);
  const [passActionError, setPassActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [unassignLoading, setUnassignLoading] = useState<number | null>(null);
  const [preassignSelfPassId, setPreassignSelfPassId] = useState<number | null>(null);
  const [preassignSelfDate, setPreassignSelfDate] = useState('');
  const [preassignSelfLoading, setPreassignSelfLoading] = useState(false);
  // A "Reserve for" value: '' (the default: see identityFor), 'p:ID' (one of
  // your personas) or 'ss:ID' (a show)
  const [preassignSelfReserveFor, setPreassignSelfReserveFor] = useState('');

  // What the user may reserve on-air passes for, each with its schedule: their
  // personas (Sublist DJs only), Specialty Music Shows they're a DJ on
  // (Sublist DJs only) and Talk & Info Shows they're on the staff of
  const [myIdentities, setMyIdentities] = useState<MyIdentity[]>([]);
  const [identitiesLoading, setIdentitiesLoading] = useState(true);

  // +1 guest claim state
  const [guestClaimPassId, setGuestClaimPassId] = useState<number | null>(null);
  const [guestName, setGuestName] = useState('');
  const [guestFallback, setGuestFallback] = useState<GuestFallback>('attend_alone');

  // Alternate queue state
  const [alternateQueue, setAlternateQueue] = useState<AlternateQueue | null>(null);
  const [alternateFormMode, setAlternateFormMode] = useState<'join' | 'edit' | null>(null);
  const [alternateActionLoading, setAlternateActionLoading] = useState(false);
  const [alternateActionError, setAlternateActionError] = useState<string | null>(null);
  // Pass awaiting confirmation that releasing it hands it to the next alternate
  const [releaseConfirmPassId, setReleaseConfirmPassId] = useState<number | null>(null);

  // Lottery state
  const [lotteryStatus, setLotteryStatus] = useState<LotteryStatus | null>(null);
  const [lotteryActionLoading, setLotteryActionLoading] = useState(false);
  const [lotteryActionError, setLotteryActionError] = useState<string | null>(null);
  // Staff lottery entry form state
  const [showStaffLotteryForm, setShowStaffLotteryForm] = useState(false);
  const [lotteryGuestName, setLotteryGuestName] = useState('');
  const [lotteryHasGuest, setLotteryHasGuest] = useState(false);
  const [lotteryGuestFallback, setLotteryGuestFallback] = useState<GuestFallback>('attend_alone');
  // DJ lottery entry form state
  const [showDJLotteryForm, setShowDJLotteryForm] = useState(false);
  const [lotteryDJDate, setLotteryDJDate] = useState('');
  // Like preassignSelfReserveFor
  const [lotteryDJReserveFor, setLotteryDJReserveFor] = useState('');

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

  const loadAlternateQueue = useCallback(async (showData: ShowResponse) => {
    if (showData.status === 'draft') return;
    try {
      setAlternateQueue(await alternatesAPI.getQueue(showData.id));
    } catch {
      // non-fatal — the alternate queue UI is hidden if it can't load
    }
  }, []);

  // Re-fetched whenever the show reloads, since claims and releases move the queue.
  useEffect(() => {
    if (show) loadAlternateQueue(show);
  }, [show, loadAlternateQueue]);

  useEffect(() => {
    if (!user?.profile) {
      setIdentitiesLoading(false);
      return;
    }
    passesAPI
      .getMyPreassignIdentities()
      .then((identities) => {
        // Most people have none; leaving the initial [] skips a re-render
        if (identities.length > 0) setMyIdentities(identities);
      })
      .catch(() => {
        // non-fatal: the reservation form stays hidden
      })
      .finally(() => setIdentitiesLoading(false));
  }, [user]);

  const myPersonas = myIdentities.filter((i) => i.kind === 'persona');

  /**
   * The identity a "Reserve for" value means. The default ('') is your
   * persona on the schedule on *date*, else your first choice.
   */
  const identityFor = (reserveFor: string, date: string): MyIdentity | undefined => {
    if (reserveFor.startsWith('ss:')) {
      const showId = parseInt(reserveFor.slice(3));
      return myIdentities.find((i) => i.specialty_show_id === showId);
    }
    if (reserveFor.startsWith('p:')) {
      const personaId = parseInt(reserveFor.slice(2));
      return myIdentities.find((i) => i.persona_id === personaId);
    }
    return (date && myPersonas.find((i) => i.dates.includes(date))) || myIdentities[0];
  };

  /**
   * The on-air dates a "Reserve for" value can pick from. The default, when
   * it's a persona, offers every day any of your personas is on air.
   */
  const scheduleFor = (reserveFor: string): string[] | null => {
    if (identitiesLoading) return null;
    const identity = identityFor(reserveFor, '');
    if (!identity) return null;
    if (!reserveFor && identity.kind === 'persona') {
      return [...new Set(myPersonas.flatMap((i) => i.dates))].sort();
    }
    return identity.dates;
  };

  /** Pick *date*, and with the default choice, the persona on air that day. */
  const pickDate = (
    date: string,
    reserveFor: string,
    setReserveFor: (value: string) => void,
    setDate: (value: string) => void,
  ) => {
    setDate(date);
    if (!reserveFor && date) {
      const scheduled = myPersonas.find((i) => i.dates.includes(date));
      if (scheduled && scheduled !== myIdentities[0]) setReserveFor(`p:${scheduled.persona_id}`);
    }
  };

  /** The persona or show a "Reserve for" value means on *date*, for the API. */
  const choiceFor = (reserveFor: string, date: string): IdentityChoice => {
    const identity = identityFor(reserveFor, date);
    return identity?.specialty_show_id != null
      ? { specialty_show_id: identity.specialty_show_id }
      : { persona_id: identity?.persona_id ?? null };
  };

  const showEphemeralSuccess = (msg: string) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  };

  const handleClaimPass = async (passId: number, claimData?: ClaimData) => {
    setPassActionId(passId);
    setPassActionError(null);
    setSuccessMessage(null);
    try {
      const claimed = await passesAPI.claim(passId, claimData);
      const msg = claimed.guest_waiting
        ? 'Pass claimed. Your guest is on the alternate list.'
        : claimData?.has_guest
          ? 'Pass claimed with +1 guest reservation!'
          : 'Pass claimed successfully!';
      showEphemeralSuccess(msg);
      setGuestClaimPassId(null);
      setGuestName('');
      setGuestFallback('attend_alone');
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
    const needsName = show.guest_list_requirements.staff_guest_requires_name;
    if (needsName && !guestName.trim()) {
      setPassActionError('Guest name is required for this venue');
      return;
    }
    await handleClaimPass(passId, {
      has_guest: true,
      guest_name: guestName.trim() || null,
      guest_fallback: guestFallback,
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

  const handleJoinAlternates = async (data: AlternateJoinRequest) => {
    if (!show) return;
    setAlternateActionLoading(true);
    setAlternateActionError(null);
    try {
      const entry = await alternatesAPI.join(show.id, data);
      setAlternateFormMode(null);
      showEphemeralSuccess(
        `You're alternate #${entry.position}. If a pass frees up it will be assigned to you automatically and you'll be emailed.`
      );
      await loadShow(true);
    } catch (err) {
      const apiError = err as APIError;
      setAlternateActionError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to join the alternate list'
      );
    } finally {
      setAlternateActionLoading(false);
    }
  };

  const handleUpdateAlternate = async (data: AlternateJoinRequest) => {
    if (!show) return;
    setAlternateActionLoading(true);
    setAlternateActionError(null);
    try {
      await alternatesAPI.updateMine(show.id, data);
      setAlternateFormMode(null);
      showEphemeralSuccess('Your alternate request has been updated.');
      await loadShow(true);
    } catch (err) {
      const apiError = err as APIError;
      setAlternateActionError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to update your alternate request'
      );
    } finally {
      setAlternateActionLoading(false);
    }
  };

  const handleLeaveAlternates = async () => {
    if (!show) return;
    setAlternateActionLoading(true);
    setAlternateActionError(null);
    try {
      await alternatesAPI.leave(show.id);
      showEphemeralSuccess('You have left the alternate list.');
      await loadShow(true);
    } catch (err) {
      const apiError = err as APIError;
      setAlternateActionError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to leave the alternate list'
      );
    } finally {
      setAlternateActionLoading(false);
    }
  };

  const handleReleasePass = async (passId: number) => {
    setReleaseConfirmPassId(null);
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
      const updatedPass = await passesAPI.selfPreassign(passId, {
        assignment_date: preassignSelfDate,
        ...choiceFor(preassignSelfReserveFor, preassignSelfDate),
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
    if (show.guest_list_requirements.staff_guest_requires_name && lotteryHasGuest && !lotteryGuestName.trim()) {
      setLotteryActionError('Guest name is required for this venue');
      return;
    }
    setLotteryActionLoading(true);
    setLotteryActionError(null);
    try {
      await lotteryAPI.enterStaff(show.id, {
        has_guest: lotteryHasGuest,
        guest_name: lotteryHasGuest ? (lotteryGuestName.trim() || null) : null,
        guest_fallback: lotteryHasGuest ? lotteryGuestFallback : 'attend_alone',
      });
      setShowStaffLotteryForm(false);
      setLotteryHasGuest(false);
      setLotteryGuestName('');
      setLotteryGuestFallback('attend_alone');
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
      await lotteryAPI.enterDJ(show.id, {
        assignment_date: lotteryDJDate,
        ...choiceFor(lotteryDJReserveFor, lotteryDJDate),
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

  const formatDate = (dateStr: string) =>
    formatCalendarDate(dateStr, {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });



  const formatDateTime = (dateTimeStr: string) =>
    formatPacific(dateTimeStr, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });

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
  // A second free pass can seat a guest now. Without one, a guest can only wait.
  const hasSpareGuestPass = availableStaffCount >= 2;
  const myEmail = user?.email?.toLowerCase() ?? null;
  // A staff member may hold at most one staff pass per show (enforced
  // server-side too) — used to disable claiming a second one from the UI.
  const holdsStaffPass = myEmail
    ? staffPasses.some(
        (p) => p.status === 'claimed' && p.staff_email?.toLowerCase() === myEmail
      )
    : false;
  // One pass per person per show, so a tabler pass rules out a staff pass too
  const holdsTablerPass = myEmail
    ? show.passes.some(
        (p) =>
          p.pass_type === 'tabler' &&
          p.status === 'claimed' &&
          p.staff_email?.toLowerCase() === myEmail
      )
    : false;
  const alreadyHasStaffPass = holdsStaffPass || holdsTablerPass;
  const notYetActive = staffPassesNotYetActive(user);
  // Why the claim buttons are disabled, if they are
  const claimBlockedTitle = notYetActive
    ? STAFF_PASSES_NOT_YET_ACTIVE
    : holdsTablerPass
      ? 'You have a tabler pass for this show.'
      : alreadyHasStaffPass
        ? 'You already have a staff pass for this show.'
        : undefined;
  const mySpecialtyShowIds = new Set(
    myIdentities.flatMap((i) => (i.specialty_show_id != null ? [i.specialty_show_id] : [])),
  );
  const staffProfile = user?.profile as StaffProfile | undefined;
  // Staff on leave for the whole show, or under 21 on the date of a 21+ show
  // (going by their birth year), can't claim a pass, enter the lottery, or
  // join the alternate list (enforced server-side too).
  const leaveBlocksPasses = leaveCoversShow(staffProfile, show);
  const myAgeCheck = ageChecks[show.id] ?? null;
  const under21 = myAgeCheck === 'under_21';
  const passesBlocked = leaveBlocksPasses || under21;
  const passesBlockedMessage = leaveBlocksPasses && staffProfile
    ? `You're on leave of absence ${formatLeave(staffProfile)}, so you can't claim passes for this show.`
    : under21
      ? ageCheckMessage('under_21', show)
      : '';
  const guestNote = guestAgeNote(show);
  /**
   * A warning about reserving for *reserveFor* on *date*, or null: you're on
   * leave (not for a show, which has others), or the schedule has you
   * hosting a Talk & Info Show that day, or not on air at all.
   */
  const scheduleWarningFor = (reserveFor: string, date: string, action: string): string | null => {
    const identity = identityFor(reserveFor, date);
    if (!date || !identity) return null;
    if (identity.kind === 'persona' && isOnLeave(staffProfile, date)) {
      return `You're on leave of absence ${formatLeave(staffProfile!)}, so you probably won't be on air on ${formatDate(date)}. Only continue if you're sure that's correct.`;
    }
    if (identitiesLoading || identity.dates.includes(date)) return null;
    const talkShow = identity.talk_show_dates[date];
    if (talkShow) {
      return `You host ${talkShow} (Talk & Info Show) on ${formatDate(date)}, so reserve for the show instead.`;
    }
    const who = identity.kind === 'persona' ? 'you' : identity.name;
    return `The on-air schedule doesn't show ${who} on ${formatDate(date)}. Only ${action} if you're sure that's correct.`;
  };
  const myPersonaIds = staffProfile?.spinitron_ids ?? [];
  // Sublist DJs, and staff members of a Talk & Info Show, can reserve on-air pass pairs
  const canReserveOnAir = myIdentities.length > 0;
  // The "Reserve for" choices; the first one's value is always '' (the default)
  const reserveForOptions = myIdentities
    .map((i) => ({
      value: i.kind === 'persona' ? `p:${i.persona_id}` : `ss:${i.specialty_show_id}`,
      label: i.kind === 'persona' ? `${i.name} (my DJ name)` : `${i.name} (${specialtyShowLabel(i.kind)})`,
    }))
    .map((o, i) => (i === 0 ? { ...o, value: '' } : o));
  // The value the dropdown shows: the default is shown as the first choice
  const shownReserveFor = (reserveFor: string): string =>
    reserveForOptions.some((o) => o.value === reserveFor) ? reserveFor : '';
  const pairPasses = show.passes.filter((p) => p.pass_type === 'pair');
  const isVenueOwner = user?.email ? show.venue.owner_emails.includes(user.email) : false;
  const showReserveForDropdown = reserveForOptions.length > 1;

  const lotteryDeadline = show.published_at
    ? new Date(new Date(show.published_at).getTime() + show.lottery_window_hours * 3600000)
    : null;
  // Use authoritative is_active from backend when loaded (accounts for early "Run now" execution);
  // fall back to time-based check before the status loads.
  const lotteryActive = lotteryStatus !== null
    ? lotteryStatus.is_active
    : show.lottery_enabled && lotteryDeadline !== null && new Date() < lotteryDeadline;
  const myStaffEntry = lotteryStatus?.my_staff_entry ?? null;
  // A show can have no staff passes, but someone who entered before they were
  // removed can still withdraw.
  const staffLotteryActive = lotteryActive && (staffPasses.length > 0 || myStaffEntry !== null);

  const alternateEntries = alternateQueue?.entries ?? [];
  const myAlternateEntry =
    alternateEntries.find((e) => e.id === alternateQueue?.my_entry_id) ?? null;
  // The join control only appears once every staff pass is held by a staff member.
  const canJoinAlternates =
    !!alternateQueue?.queue_open &&
    !alreadyHasStaffPass &&
    !myAlternateEntry &&
    show.status === 'published' &&
    !lotteryActive &&
    !passesBlocked;
  const releaseCandidateName = alternateQueue?.next_candidate_name ?? null;
  const myDJEntry = lotteryStatus?.my_dj_entry ?? null;
  // A 21+ show they might be too young for, or are too young for but already
  // have a pass, lottery entry or alternate list spot for (kept, not released)
  const ageWarning = !myAgeCheck
    ? null
    : myAgeCheck === 'maybe_under_21'
      ? ageCheckMessage('maybe_under_21', show)
      : alreadyHasStaffPass
        ? `${ageCheckMessage('under_21', show)} Please release yours.`
        : myStaffEntry
          ? `${ageCheckMessage('under_21', show)} Please withdraw your lottery entry.`
          : myAlternateEntry
            ? `${ageCheckMessage('under_21', show)} Please leave the alternate list.`
            : null;

  const claimWithGuestButton = (passId: number) => (
    <button
      onClick={() => {
        setGuestClaimPassId(passId);
        setGuestName('');
        setGuestFallback(hasSpareGuestPass ? 'attend_alone' : 'wait');
        setPassActionError(null);
      }}
      className="btn-small"
      disabled={passActionId === passId || alreadyHasStaffPass || notYetActive}
      title={claimBlockedTitle ?? 'Claim this pass with a +1 guest. Guest spot is tentative until show closes.'}
    >
      Claim with +1 Guest
    </button>
  );

  const renderGuestClaimForm = (passId: number) => (
    <div className="guest-claim-form">
      <p className="guest-claim-info">
        You're claiming this pass with a +1 guest. Your guest's spot is not
        guaranteed — if another staff member claims a pass, your guest may be
        bumped. You'll be notified immediately if that happens, and again when
        the show closes to confirm whether your guest can attend.
      </p>
      {guestNote && <p className="field-hint">{guestNote}</p>}
      {show.guest_list_requirements.staff_guest_requires_name && (
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
      <GuestFallbackOptions
        name="guest-fallback"
        legend="If my guest can't attend:"
        value={guestFallback}
        onChange={setGuestFallback}
        waitOnly={!hasSpareGuestPass}
      />
      <div className="form-actions">
        <button
          onClick={() => handleGuestClaimSubmit(passId)}
          className="btn-small btn-primary"
          disabled={passActionId === passId}
        >
          {passActionId === passId ? 'Claiming...' : 'Claim with +1'}
        </button>
        <button
          onClick={() => { setGuestClaimPassId(null); setGuestName(''); setGuestFallback('attend_alone'); setPassActionError(null); }}
          className="btn-small btn-secondary"
          disabled={passActionId === passId}
        >
          Cancel
        </button>
      </div>
    </div>
  );

  const formatLotteryDeadline = (d: Date) =>
    formatPacific(d, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

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
  const scheduleDates = scheduleFor(preassignSelfReserveFor);
  const lotteryScheduleDates = scheduleFor(lotteryDJReserveFor);
  const scheduleDatesBeforeClose =
    scheduleDates?.filter((d) => d <= maxDJReservationDate) ?? null;
  const lotteryScheduleDatesBeforeClose =
    lotteryScheduleDates?.filter((d) => d <= maxDJReservationDate) ?? null;

  return (
    <div className="show-detail">
      <div className="page-header">
        <button onClick={() => navigate('/staff/shows')} className="btn-secondary">
          ← Back to Shows
        </button>
        <h2><EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} /></h2>
        {show.in_feature_bin && (
          <div style={{ marginTop: '0.25rem' }}>
            <FeatureBinBadge releases={show.feature_bin_releases} />
          </div>
        )}
        {show.on_kalx_live && (
          <div style={{ marginTop: '0.25rem' }}>
            <KalxLiveBadge appearances={show.kalx_live_appearances} />
          </div>
        )}
      </div>

      {alreadyHasStaffPass && (
        <p className="info-message" role="note">
          You have a {holdsTablerPass ? 'tabler' : 'staff'} pass for this show.{' '}
          <Link to="/staff/my-passes">See it and your other passes in My Passes</Link>.
        </p>
      )}

      {successMessage && (
        <div className="success-message">{successMessage}</div>
      )}

      {passActionError && (
        <div className="error-message">{passActionError}</div>
      )}

      <div className="show-detail-content">
        <ShowInfoCards show={show} />

        {ageWarning && (
          <div className="field-warning" role="alert">
            {ageWarning}
          </div>
        )}

        {canReserveOnAir && isVenueOwner && show.status !== 'closed' && (
          <div className="pass-claim-section">
            <h3>Reserve Pass Pair for On-Air Giveaway</h3>
            <p className="pass-unavailable-note">
              KALX promotions reps cannot reserve pass pairs for shows at the venues they rep.
            </p>
          </div>
        )}

        {canReserveOnAir && !isVenueOwner && show.status !== 'closed' && (
          <div className="pass-claim-section">
            <h3>
              Reserve Pass Pair for On-Air Giveaway
              <Tooltip text="Reserve a pass pair to give away on-air on a future date. The passes will be held under your DJ name, or the show you reserve them for, until the air date." />
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
                  {formatCalendarDate(toDateInputValue(prohibitedFromDate), {
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
                    className="btn-small btn-danger"
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
                            value={shownReserveFor(lotteryDJReserveFor)}
                            onChange={(e) => setLotteryDJReserveFor(e.target.value)}
                            disabled={lotteryActionLoading}
                          >
                            {reserveForOptions.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      ) : (
                        <input
                          type="text"
                          value={reserveForOptions[0]?.label ?? ''}
                          readOnly
                          disabled
                          className="input-readonly"
                        />
                      )}
                      {identitiesLoading && (
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
                        onChange={(date) =>
                          pickDate(date, lotteryDJReserveFor, setLotteryDJReserveFor, setLotteryDJDate)
                        }
                        max={maxDJReservationDate}
                        disabled={lotteryActionLoading}
                        isDateDisabled={
                          lotteryScheduleDates && lotteryScheduleDates.length > 0
                            ? (date) => !lotteryScheduleDates.includes(formatDateValue(date))
                            : undefined
                        }
                      />
                      {scheduleWarningFor(lotteryDJReserveFor, lotteryDJDate, 'enter the lottery for this date') && (
                        <p className="field-warning">
                          {scheduleWarningFor(lotteryDJReserveFor, lotteryDJDate, 'enter the lottery for this date')}
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
                        className="btn-small btn-secondary"
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
                    pass.preassigned_persona_id != null &&
                    myPersonaIds.includes(pass.preassigned_persona_id);
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
                              {pass.preassigned_specialty_show_id !== null && (
                                <span className="specialty-show-badge">
                                  {' '}({specialtyShowLabel(
                                    myIdentities.find((i) => i.specialty_show_id === pass.preassigned_specialty_show_id)
                                      ?.kind as 'music' | 'talk' | undefined,
                                  )})
                                </span>
                              )}
                            </p>
                            {pass.preassigned_date && (
                              <p>
                                <strong>Date:</strong> {formatDate(pass.preassigned_date)}
                              </p>
                            )}
                            <button
                              onClick={() => handleUnassignSelf(pass.id)}
                              className="btn-small btn-danger"
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
                                    value={shownReserveFor(preassignSelfReserveFor)}
                                    onChange={(e) => setPreassignSelfReserveFor(e.target.value)}
                                    disabled={preassignSelfLoading}
                                  >
                                    {reserveForOptions.map((o) => (
                                      <option key={o.value} value={o.value}>
                                        {o.label}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              ) : (
                                <input
                                  type="text"
                                  value={reserveForOptions[0]?.label ?? ''}
                                  readOnly
                                  disabled
                                  className="input-readonly"
                                />
                              )}
                              {identitiesLoading && (
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
                                onChange={(date) =>
                                  pickDate(
                                    date,
                                    preassignSelfReserveFor,
                                    setPreassignSelfReserveFor,
                                    setPreassignSelfDate,
                                  )
                                }
                                max={maxDJReservationDate}
                                disabled={preassignSelfLoading}
                                isDateDisabled={
                                  scheduleDates && scheduleDates.length > 0
                                    ? (date) => !scheduleDates.includes(formatDateValue(date))
                                    : undefined
                                }
                              />
                              {scheduleWarningFor(preassignSelfReserveFor, preassignSelfDate, 'save this') && (
                                <p className="field-warning">
                                  {scheduleWarningFor(preassignSelfReserveFor, preassignSelfDate, 'save this')}
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
                                className="btn-small btn-secondary"
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
                              {pass.preassigned_date && <> for {formatDate(pass.preassigned_date)}</>}
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

        <TablerPassesSection
          show={show}
          mode="staff"
          myEmail={myEmail}
          canClaim={user?.can_claim_tabler_passes ?? false}
          canClaimWhenOpenToAll={user?.can_claim_staff_passes ?? false}
          canReleaseAny={user?.is_site_admin ?? false}
          blockedReason={
            holdsStaffPass
              ? 'You have a staff pass for this show. Release it to claim a tabler pass instead.'
              : myStaffEntry
                ? "You've entered the staff pass lottery for this show. Withdraw to claim a tabler pass instead."
                : myAlternateEntry
                  ? "You're on the alternate list for this show. Leave it to claim a tabler pass instead."
                  : passesBlocked
                    ? passesBlockedMessage
                    : null
          }
          onChanged={() => loadShow(true)}
        />

        <div className="pass-claim-section">
          <h3>
            Staff Passes ({displayAvailableCount} of {staffPasses.length} available)
            <Tooltip text="Claim a staff pass to attend this show. Each pass admits 1 person. You can also reserve a +1 guest slot if two passes are available. You can release your claim if your plans change (while the show is still open)." />
          </h3>

          {holdsTablerPass ? (
            <p className="field-hint">
              You have a tabler pass for this show — release it before claiming a staff pass.
            </p>
          ) : alreadyHasStaffPass && (
            <p className="field-hint">
              You already have a staff pass for this show — release it before claiming another.
            </p>
          )}

          {passesBlocked && !alreadyHasStaffPass && (
            <p className="field-hint">{passesBlockedMessage}</p>
          )}

          {notYetActive && <p className="field-hint">{STAFF_PASSES_NOT_YET_ACTIVE}</p>}

          {staffPasses.length === 0 && (
            <p className="field-hint">This show has no staff passes.</p>
          )}

          {staffLotteryActive && lotteryDeadline && (
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

          {staffLotteryActive && (
            myStaffEntry ? (
              <div className="lottery-entry-confirmation">
                <p>You have entered the lottery for a staff pass.</p>
                {myStaffEntry.has_guest && (
                  <p>
                    +1 guest requested{myStaffEntry.guest_name ? `: ${myStaffEntry.guest_name}` : ''}
                    {myStaffEntry.guest_fallback === 'release' ? ' (release pass if guest cannot attend)' : ''}
                    {waitingFallbackNote(myStaffEntry.guest_fallback)}
                  </p>
                )}
                <button
                  onClick={handleWithdrawStaffLottery}
                  className="btn-small btn-danger"
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
                    {guestNote && <p className="field-hint">{guestNote}</p>}
                    {show.guest_list_requirements.staff_guest_requires_name && (
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
                    <GuestFallbackOptions
                      name="lottery-guest-fallback"
                      legend="If there aren't enough passes for my guest to attend:"
                      value={lotteryGuestFallback}
                      onChange={setLotteryGuestFallback}
                    />
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
                    onClick={() => { setShowStaffLotteryForm(false); setLotteryHasGuest(false); setLotteryGuestName(''); setLotteryGuestFallback('attend_alone'); }}
                    className="btn-small btn-secondary"
                    disabled={lotteryActionLoading}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : passesBlocked ? null : (
              <button
                onClick={() => setShowStaffLotteryForm(true)}
                className="btn-small btn-primary"
                disabled={notYetActive || holdsTablerPass}
                title={claimBlockedTitle ?? 'Enter the lottery for a staff pass to attend this show.'}
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
                // Only the claimer can release their own pass.
                const isMine = !!myEmail && pass.staff_email?.toLowerCase() === myEmail;
                return (
                  <div key={pass.id} className="pass-card">
                    <div className="pass-details">
                      <p><strong>Claimed by:</strong> {pass.staff_name ?? '(name not recorded)'}</p>
                      {isPrimaryWithGuest && (
                        <p className="pass-guest-note">
                          +1 guest reserved
                          {pass.guest_name ? `: ${pass.guest_name}` : ''}
                          {show.status !== 'closed' && pass.guest_fallback === 'release' ? " (staff will release if guest can't attend)" : ''}
                          {show.status !== 'closed' && seatedFallbackNote(pass.guest_fallback)}
                          {' '}— <em>
                            {show.close_notifications_pending
                              ? isMine
                                ? "not confirmed yet, you'll get an email"
                                : 'not confirmed yet'
                              : show.status === 'closed'
                                ? 'confirmed'
                                : 'not confirmed until show closes'}
                          </em>
                        </p>
                      )}
                      {pass.guest_waiting && (
                        <p className="pass-guest-note">
                          {show.status !== 'closed' ? (
                            <>
                              +1 guest on the alternate list
                              {pass.guest_name ? `: ${pass.guest_name}` : ''}
                              {pass.guest_position ? ` (guest #${pass.guest_position})` : ''}
                              {pass.guest_fallback === 'wait_then_release'
                                ? " — staff's pass is released if they don't have one at close"
                                : ''}
                            </>
                          ) : show.close_notifications_pending ? (
                            <>
                              +1 guest{pass.guest_name ? `: ${pass.guest_name}` : ''} — <em>
                                {isMine ? "not confirmed yet, you'll get an email" : 'not confirmed yet'}
                              </em>
                            </>
                          ) : (
                            <>+1 guest didn't get a pass{pass.guest_name ? `: ${pass.guest_name}` : ''}</>
                          )}
                        </p>
                      )}
                      {pass.staff_phone && <p><strong>Phone:</strong> {formatPhone(pass.staff_phone)}</p>}
                      {pass.claimed_at && (
                        <p><strong>Claimed:</strong> {formatDateTime(pass.claimed_at)}</p>
                      )}
                      {isMine && show.status === 'published' && (
                        <ClaimGuestActions
                          pass={pass}
                          availableCount={availableStaffCount}
                          requireGuestName={show.guest_list_requirements.staff_guest_requires_name}
                          guestNote={guestNote}
                          canAddGuest={!lotteryActive && !passesBlocked && !notYetActive}
                          onChanged={async (message) => {
                            showEphemeralSuccess(message);
                            await loadShow(true);
                          }}
                        />
                      )}
                      {isMine && (
                        <>
                          <button
                            onClick={() => {
                              if (releaseCandidateName) {
                                setReleaseConfirmPassId(pass.id);
                              } else {
                                handleReleasePass(pass.id);
                              }
                            }}
                            className="btn-small"
                            disabled={show.status === 'closed' || passActionId === pass.id}
                            title="Release your claim if you can no longer attend the show."
                          >
                            {passActionId === pass.id ? 'Releasing...' : 'Release'}
                          </button>
                          {show.status === 'closed' && (
                            <p className="pass-closed-note">Show is closed — cannot release.</p>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              }

              if (isGuestHold) {
                return (
                  <div key={pass.id} className="pass-card">
                    <div className="pass-details">
                      <p className={show.status === 'closed' ? 'pass-unavailable-note' : 'pass-available-note'}>
                        {show.status === 'closed' ? 'Unavailable' : 'Available'}
                      </p>
                      {show.status !== 'closed' && !passesBlocked && (
                        guestClaimPassId === pass.id ? (
                          renderGuestClaimForm(pass.id)
                        ) : (
                          <div className="claim-buttons">
                            <button
                              onClick={() => handleClaimPass(pass.id)}
                              className="btn-small btn-primary"
                              disabled={passActionId === pass.id || alreadyHasStaffPass || notYetActive}
                              title={claimBlockedTitle}
                            >
                              {passActionId === pass.id ? 'Claiming...' : 'Claim'}
                            </button>
                            {claimWithGuestButton(pass.id)}
                          </div>
                        )
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
                    {show.status !== 'closed' && !lotteryActive && !passesBlocked && (
                      <>
                        {guestClaimPassId === pass.id ? (
                          renderGuestClaimForm(pass.id)
                        ) : (
                          <div className="claim-buttons">
                            <button
                              onClick={() => handleClaimPass(pass.id)}
                              className="btn-small btn-primary"
                              disabled={passActionId === pass.id || alreadyHasStaffPass || notYetActive}
                              title={claimBlockedTitle ?? 'Claim this staff pass to attend the show (1 person).'}
                            >
                              {passActionId === pass.id ? 'Claiming...' : 'Claim'}
                            </button>
                            {claimWithGuestButton(pass.id)}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {alternateActionError && <p className="field-error">{alternateActionError}</p>}

          {alternateQueue?.my_outcome_pending && (
            <div className="alternate-summary">
              <p style={{ margin: 0 }}>The show has closed. You'll get an email with the outcome.</p>
            </div>
          )}

          {canJoinAlternates && (
            <div className="alternate-summary">
              <p style={{ margin: '0 0 0.5rem' }}>
                <strong>All staff passes are taken.</strong>{' '}
                {alternateEntries.length === 0
                  ? 'You can join the alternate list — if a pass frees up, the first alternate gets it automatically and is emailed.'
                  : `${alternateEntries.length} ${alternateEntries.length === 1 ? 'person is' : 'people are'} already on the alternate list ahead of you. If a pass frees up, the first alternate gets it automatically and is emailed.`}
              </p>
              {alternateFormMode === 'join' ? (
                <AlternateGuestForm
                  idPrefix="alternate-join"
                  requireGuestName={show.guest_list_requirements.staff_guest_requires_name}
                  guestNote={guestNote}
                  submitLabel="Join Alternate List"
                  busy={alternateActionLoading}
                  onSubmit={handleJoinAlternates}
                  onCancel={() => { setAlternateFormMode(null); setAlternateActionError(null); }}
                />
              ) : (
                <button
                  onClick={() => setAlternateFormMode('join')}
                  className="btn-small btn-primary"
                  disabled={notYetActive}
                  title={notYetActive ? STAFF_PASSES_NOT_YET_ACTIVE : 'Get in line for a staff pass in case someone releases theirs.'}
                >
                  Join Alternate List
                </button>
              )}
            </div>
          )}

          {myAlternateEntry && (
            <div className="alternate-summary">
              You are <strong>alternate #{myAlternateEntry.position}</strong>
              {myAlternateEntry.position === 1
                ? ' — you are next in line if a staff pass frees up.'
                : ` — ${myAlternateEntry.position - 1} ${myAlternateEntry.position === 2 ? 'person is' : 'people are'} ahead of you.`}
              {myAlternateEntry.guest_fallback === 'release' &&
                ' Because you only want to attend with your guest, you will be skipped until two passes are free at once.'}
            </div>
          )}

          <AlternateQueueList
            entries={alternateEntries}
            myEntryId={myAlternateEntry?.id ?? null}
            renderMyActions={(entry) =>
              alternateFormMode === 'edit' ? (
                <AlternateGuestForm
                  idPrefix="alternate-edit"
                  requireGuestName={show.guest_list_requirements.staff_guest_requires_name}
                  guestNote={guestNote}
                  initial={{
                    has_guest: entry.has_guest,
                    guest_name: entry.guest_name,
                    guest_fallback: entry.guest_fallback,
                  }}
                  submitLabel="Save"
                  busy={alternateActionLoading}
                  onSubmit={handleUpdateAlternate}
                  onCancel={() => { setAlternateFormMode(null); setAlternateActionError(null); }}
                />
              ) : (
                <div className="claim-buttons">
                  <button
                    onClick={() => setAlternateFormMode('edit')}
                    className="btn-small"
                    disabled={alternateActionLoading}
                    title="Change your +1 guest request without losing your place in line."
                  >
                    Edit guest
                  </button>
                  <button
                    onClick={handleLeaveAlternates}
                    className="btn-small btn-danger"
                    disabled={alternateActionLoading}
                    title="Leave the alternate list. Rejoining puts you at the back of the line."
                  >
                    {alternateActionLoading ? 'Leaving…' : 'Leave list'}
                  </button>
                </div>
              )
            }
          />
          <WaitingGuestsList guests={alternateQueue?.waiting_guests ?? []} />
        </div>
      </div>

      {releaseConfirmPassId !== null && (
        <div className="modal-overlay" onClick={() => setReleaseConfirmPassId(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Release Your Pass</h3>
              <button className="btn-close" onClick={() => setReleaseConfirmPassId(null)}>×</button>
            </div>
            <p>
              Your pass will go to <strong>{releaseCandidateName}</strong>; you can rejoin at
              the back of the line.
            </p>
            <div className="form-actions" style={{ marginTop: '1rem' }}>
              <button onClick={() => setReleaseConfirmPassId(null)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => handleReleasePass(releaseConfirmPassId)}
                className="btn-primary"
              >
                Release Pass
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ShowDetail;
