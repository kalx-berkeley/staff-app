import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { legacyImportAPI, passesAPI, venuesAPI, showsAPI, autocompleteAPI, specialtyShowsAPI } from '../api';
import type { PassResponse, VenueResponse, AgeRestriction, MovieRating, ShowSummary, WheelchairAccessible } from '../types';
import { MOVIE_RATING_LABELS } from '../utils';
import {
  DatePicker,
  Tooltip,
  DescriptionCheckFeedback,
  useDescriptionCheck,
  PersonAutocomplete,
  extractPersonEmail,
} from '../components';
import DjNameAutocomplete from '../components/DjNameAutocomplete';
import { formatPhone } from '../../common/utils';
import { usePageTitle } from '../../common/hooks/usePageTitle';

type Mode = 'new' | 'existing';

interface StaffMember {
  id: number;
  name: string;
  email: string;
}

interface OnAirWinnerRow {
  recipient_name: string;
  recipient_phone: string;
  recipient_email: string;
  given_away_by_dj: string;
}

interface StaffClaimRow {
  staff_id: number | '';
  /** Text in the staff member autocomplete; staff_id is set once it matches a staff member */
  staff_input: string;
  has_guest: boolean;
  guest_name: string;
}

const emptyWinner = (): OnAirWinnerRow => ({
  recipient_name: '',
  recipient_phone: '',
  recipient_email: '',
  given_away_by_dj: '',
});

const emptyStaffClaim = (): StaffClaimRow => ({
  staff_id: '',
  staff_input: '',
  has_guest: false,
  guest_name: '',
});

/** Grow or shrink the winner rows, keeping what's been typed in the ones that stay. */
const resizeWinners = (rows: OnAirWinnerRow[], count: number): OnAirWinnerRow[] => {
  const next = rows.slice(0, count);
  while (next.length < count) next.push(emptyWinner());
  return next;
};

interface StaffRowCardProps {
  title: string;
  idPrefix: string;
  row: StaffClaimRow;
  error?: string;
  guestError?: string;
  guestRequiresName: boolean;
  staffOptions: { email: string; name: string }[];
  disabled: boolean;
  onRemove: () => void;
  onChange: (changes: Partial<StaffClaimRow>) => void;
  onStaffInputChange: (text: string) => void;
  onStaffInputSubmit: (text: string) => void;
}

/** One staff member and their +1 guest, as a claimant or an alternate. */
const StaffRowCard = ({
  title,
  idPrefix,
  row,
  error,
  guestError,
  guestRequiresName,
  staffOptions,
  disabled,
  onRemove,
  onChange,
  onStaffInputChange,
  onStaffInputSubmit,
}: StaffRowCardProps) => (
  <div className="pass-card" style={{ marginBottom: '0.75rem' }}>
    <div className="pass-header">
      <h3>{title}</h3>
      <button
        type="button"
        className="btn-secondary btn-small"
        onClick={onRemove}
        disabled={disabled}
        aria-label={`Remove ${title}`}
      >
        Remove
      </button>
    </div>
    <div className="form-row">
      <div className="form-group">
        <label htmlFor={idPrefix}>Staff Member</label>
        <PersonAutocomplete
          id={idPrefix}
          value={row.staff_input}
          onChange={onStaffInputChange}
          onSubmit={onStaffInputSubmit}
          options={staffOptions}
          placeholder="Staff name or email"
          className={error ? 'input-error' : undefined}
          disabled={disabled}
        />
        {error && <span className="field-error">{error}</span>}
      </div>
      <div className="form-group checkbox-group">
        <label>
          <input
            type="checkbox"
            checked={row.has_guest}
            onChange={(e) => onChange({ has_guest: e.target.checked })}
            disabled={disabled}
          />
          +1 Guest
        </label>
      </div>
    </div>
    {row.has_guest && (
      <div className="form-group">
        <label htmlFor={`${idPrefix}_guest`}>
          Guest Name {guestRequiresName && <span className="required">*</span>}
        </label>
        <input
          id={`${idPrefix}_guest`}
          type="text"
          value={row.guest_name}
          onChange={(e) => onChange({ guest_name: e.target.value })}
          className={guestError ? 'input-error' : ''}
          disabled={disabled}
          placeholder={guestRequiresName ? 'Required' : 'Optional'}
        />
        {guestError && <span className="field-error">{guestError}</span>}
      </div>
    )}
  </div>
);

interface RecordedPassCardProps {
  pass: PassResponse;
  title: string;
  details: string[];
  /** Explains what releasing does, shown when asking to confirm. */
  releaseNote: string;
  /** On-air winners need a reason, which goes in the email to the show's promotions reps. */
  asksForReason: boolean;
  disabled: boolean;
  /** Resolves to whether the release worked. */
  onRelease: (reason: string) => Promise<boolean>;
}

/** A winner or claim already recorded on an existing show, which can be released. */
const RecordedPassCard = ({
  pass,
  title,
  details,
  releaseNote,
  asksForReason,
  disabled,
  onRelease,
}: RecordedPassCardProps) => {
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState('');
  const reasonId = `li_release_reason_${pass.id}`;

  const handleConfirm = async () => {
    if (await onRelease(reason.trim())) {
      setConfirming(false);
      setReason('');
    }
  };

  return (
    <div className="pass-card" style={{ marginBottom: '0.75rem' }}>
      <div className="pass-header">
        <h3>{title}</h3>
        {!confirming && (
          <button
            type="button"
            className="btn-secondary btn-small"
            onClick={() => setConfirming(true)}
            disabled={disabled}
            aria-label={`Release ${title}`}
          >
            Release
          </button>
        )}
      </div>
      {details.length > 0 && (
        <div className="pass-details">
          {details.map((detail) => <p key={detail}>{detail}</p>)}
        </div>
      )}
      {confirming && (
        <>
          <p className="field-hint">{releaseNote}</p>
          {asksForReason && (
            <div className="form-group">
              <label htmlFor={reasonId}>Reason <span className="required">*</span></label>
              <textarea
                id={reasonId}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                disabled={disabled}
              />
            </div>
          )}
          <div className="form-actions">
            <button
              type="button"
              className="btn-secondary btn-small"
              onClick={() => setConfirming(false)}
              disabled={disabled}
            >
              Keep
            </button>
            <button
              type="button"
              className="btn-primary btn-small"
              onClick={handleConfirm}
              disabled={disabled || (asksForReason && !reason.trim())}
            >
              Confirm Release
            </button>
          </div>
        </>
      )}
    </div>
  );
};

const LegacyImport = () => {
  usePageTitle('Legacy Import · Promotions');
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>('new');

  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [venues, setVenues] = useState<VenueResponse[]>([]);
  const [staffList, setStaffList] = useState<StaffMember[]>([]);
  const [knownGenres, setKnownGenres] = useState<string[]>([]);
  const [djNames, setDjNames] = useState<string[]>([]);
  const [specialtyShowNames, setSpecialtyShowNames] = useState<Set<string>>(new Set());
  const descriptionCheck = useDescriptionCheck();

  // Venue is at the top and persists across imports
  const [venueId, setVenueId] = useState<number | ''>('');
  const [selectedVenue, setSelectedVenue] = useState<VenueResponse | null>(null);

  // Show fields (New Show mode only)
  const [eventName, setEventName] = useState('');
  const [genreLookupInProgress, setGenreLookupInProgress] = useState(false);
  const [genres, setGenres] = useState<string[]>([]);
  const [genreInput, setGenreInput] = useState('');
  const [showDate, setShowDate] = useState('');
  const [showTime, setShowTime] = useState('');
  const [isMultiDay, setIsMultiDay] = useState(false);
  const [showStartDate, setShowStartDate] = useState('');
  const [onAirDescription, setOnAirDescription] = useState('');
  const [callerSpecialInstructions, setCallerSpecialInstructions] = useState('');
  const [ageRestriction, setAgeRestriction] = useState<AgeRestriction>('all_ages');
  const [movieRating, setMovieRating] = useState<MovieRating>('NR');
  const [wheelchairAccessible, setWheelchairAccessible] = useState<WheelchairAccessible>('yes');
  const [numPassPairs, setNumPassPairs] = useState(1);
  const [coAnnounce, setCoAnnounce] = useState(false);

  // Existing Show mode: picker state
  const [existingShows, setExistingShows] = useState<ShowSummary[]>([]);
  const [existingShowsLoading, setExistingShowsLoading] = useState(false);
  const [existingShowsError, setExistingShowsError] = useState<string | null>(null);
  const [showSearch, setShowSearch] = useState('');
  const [selectedShow, setSelectedShow] = useState<ShowSummary | null>(null);
  // The selected show's passes, for releasing the winners and claims it already has
  const [showPasses, setShowPasses] = useState<PassResponse[] | null>(null);
  const [showPassesError, setShowPassesError] = useState<string | null>(null);
  const [releasing, setReleasing] = useState(false);
  const showPassesRequest = useRef(0);

  // On-air winners, staff claimants and alternates — shared between both modes
  const [onAirWinners, setOnAirWinners] = useState<OnAirWinnerRow[]>([emptyWinner()]);
  const [staffClaims, setStaffClaims] = useState<StaffClaimRow[]>([]);
  const [alternates, setAlternates] = useState<StaffClaimRow[]>([]);

  const staffCapacity = mode === 'new' ? numPassPairs : (selectedShow?.available_staff_count ?? 0);

  const selectedShowVenue = useMemo(
    () => (selectedShow ? venues.find((v) => v.id === selectedShow.venue.id) ?? null : null),
    [selectedShow, venues]
  );
  // The venue whose guest list rules apply to the winners and claims below.
  const targetVenue = mode === 'new' ? selectedVenue : selectedShowVenue;
  // Shows at a movie theater have a movie rating instead of an age restriction
  const isMovieTheater = selectedVenue?.venue_type === 'movie_theater';
  const requiresEmail = !!targetVenue?.requires_email_address;
  const guestRequiresName = !!targetVenue?.staff_guest_requires_name;

  useEffect(() => {
    const init = async () => {
      const isEnabled = await legacyImportAPI.checkEnabled();
      setEnabled(isEnabled);
      if (!isEnabled) {
        setLoading(false);
        return;
      }
      try {
        const [venueList, genreList, staffMembers] = await Promise.all([
          venuesAPI.list(),
          showsAPI.listGenres(),
          legacyImportAPI.listStaff(),
        ]);
        setVenues(venueList);
        setKnownGenres(genreList);
        setStaffList(staffMembers);
        // DJ name suggestions are a convenience, so a failure here is ignored.
        autocompleteAPI.getDJNames().then(setDjNames).catch(() => {});
        specialtyShowsAPI
          .list()
          .then((shows) => setSpecialtyShowNames(new Set(shows.map((s) => s.name.toLowerCase()))))
          .catch(() => {});
        if (venueList.length === 1) {
          setVenueId(venueList[0].id);
          setSelectedVenue(venueList[0]);
          applyVenueDefaults(venueList[0]);
        }
      } catch {
        setApiError('Failed to load form data.');
      }
      setLoading(false);
    };
    init();
  }, []);

  // Lazily load candidate shows the first time Existing Show mode is opened.
  useEffect(() => {
    if (mode !== 'existing' || existingShows.length > 0 || existingShowsLoading) return;
    setExistingShowsLoading(true);
    setExistingShowsError(null);
    showsAPI
      .list()
      .then((shows) => {
        const candidates = shows
          .filter((s) => s.status === 'draft' || s.status === 'published')
          .sort((a, b) => a.show_date.localeCompare(b.show_date));
        setExistingShows(candidates);
      })
      .catch(() => setExistingShowsError('Failed to load shows.'))
      .finally(() => setExistingShowsLoading(false));
  }, [mode, existingShows.length, existingShowsLoading]);

  const applyVenueDefaults = (venue: VenueResponse) => {
    if (venue.default_wheelchair_accessible != null) {
      setWheelchairAccessible(venue.default_wheelchair_accessible);
    }
    if (venue.default_age_restriction != null) {
      setAgeRestriction(venue.default_age_restriction as AgeRestriction);
    }
    if (venue.default_movie_rating != null) {
      setMovieRating(venue.default_movie_rating);
    }
    if (venue.default_num_pass_pairs != null) {
      setNumPassPairs(venue.default_num_pass_pairs);
    }
  };

  const handleVenueChange = (id: number | '') => {
    setVenueId(id);
    if (id !== '') {
      const venue = venues.find((v) => v.id === id) ?? null;
      setSelectedVenue(venue);
      if (venue) applyVenueDefaults(venue);
    } else {
      setSelectedVenue(null);
    }
  };

  // In New Show mode, keep one winner row per chosen pass pair.
  useEffect(() => {
    if (mode !== 'new') return;
    setOnAirWinners((prev) => resizeWinners(prev, numPassPairs));
  }, [mode, numPassPairs]);

  // Existing Show mode's rows are cleared whenever the target show changes (or
  // a submission just succeeded), so leftover text never gets attributed to the
  // wrong show. Releasing a pass doesn't clear them, so entries in progress stay.
  const clearExistingShowRows = (availablePairs: number) => {
    setOnAirWinners(Array.from({ length: availablePairs }, emptyWinner));
    setStaffClaims([]);
    setAlternates([]);
    setErrors({});
  };

  const loadShowPasses = useCallback(async (showId: number) => {
    const request = ++showPassesRequest.current;
    setShowPassesError(null);
    try {
      const passes = await passesAPI.getForShow(showId);
      if (request !== showPassesRequest.current) return;
      const availableCount = (passType: PassResponse['pass_type']) =>
        passes.filter((p) => p.pass_type === passType && p.status === 'available').length;
      const counts = {
        available_pair_count: availableCount('pair'),
        available_staff_count: availableCount('staff'),
      };
      setShowPasses(passes);
      setSelectedShow((prev) => (prev?.id === showId ? { ...prev, ...counts } : prev));
      setExistingShows((prev) => prev.map((s) => (s.id === showId ? { ...s, ...counts } : s)));
      setOnAirWinners((prev) => resizeWinners(prev, counts.available_pair_count));
    } catch {
      if (request === showPassesRequest.current) {
        setShowPassesError("Failed to load this show's winners and claims.");
      }
    }
  }, []);

  const selectShow = (show: ShowSummary | null) => {
    showPassesRequest.current++;
    setSelectedShow(show);
    setShowPasses(null);
    setShowPassesError(null);
    setApiError(null);
    setSuccessMessage(null);
    clearExistingShowRows(show?.available_pair_count ?? 0);
    if (show) loadShowPasses(show.id);
  };

  const runRelease = async (release: () => Promise<string>): Promise<boolean> => {
    if (!selectedShow) return false;
    setApiError(null);
    setSuccessMessage(null);
    setReleasing(true);
    try {
      const message = await release();
      await loadShowPasses(selectedShow.id);
      setSuccessMessage(message);
      return true;
    } catch (err: unknown) {
      setApiError((err as { detail?: string })?.detail ?? 'Release failed. Please try again.');
      return false;
    } finally {
      setReleasing(false);
    }
  };

  const releaseWinner = (pass: PassResponse, reason: string) =>
    runRelease(async () => {
      await passesAPI.releaseWinner(pass.id, { reason });
      return `Released ${pass.recipient_name}'s passes, so they can be given away again.`;
    });

  const releaseClaim = (pass: PassResponse) =>
    runRelease(async () => {
      const updated = await passesAPI.releaseClaim(pass.id);
      const released = `Released ${pass.staff_name ?? 'the'}${pass.staff_name ? "'s" : ''} staff pass`;
      return updated.status === 'claimed' && updated.staff_name
        ? `${released}. It went to the next alternate, ${updated.staff_name}.`
        : `${released}.`;
    });

  const addGenre = (value: string) => {
    const trimmed = value.trim();
    if (trimmed && !genres.includes(trimmed)) {
      setGenres((prev) => [...prev, trimmed]);
    }
    setGenreInput('');
  };

  const removeGenre = (index: number) => {
    setGenres((prev) => prev.filter((_, i) => i !== index));
  };

  const handleEventNameBlur = useCallback(async () => {
    if (!eventName.trim() || genres.length > 0) return;
    setGenreLookupInProgress(true);
    try {
      const suggested = await showsAPI.suggestGenre(eventName.trim());
      if (suggested.length > 0) {
        setGenres((prev) => (prev.length === 0 ? suggested : prev));
      }
    } catch {
      // silently ignore
    } finally {
      setGenreLookupInProgress(false);
    }
  }, [eventName, genres.length]);

  const updateWinner = (index: number, field: keyof OnAirWinnerRow, value: string) => {
    setOnAirWinners((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const addStaffClaim = () => {
    setStaffClaims((prev) => [...prev, emptyStaffClaim()]);
  };

  const removeStaffClaim = (index: number) => {
    setStaffClaims((prev) => prev.filter((_, i) => i !== index));
  };

  const updateStaffClaim = (index: number, changes: Partial<StaffClaimRow>) => {
    setStaffClaims((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], ...changes };
      return next;
    });
  };

  const addAlternate = () => {
    setAlternates((prev) => [...prev, emptyStaffClaim()]);
  };

  const removeAlternate = (index: number) => {
    setAlternates((prev) => prev.filter((_, i) => i !== index));
  };

  const updateAlternate = (index: number, changes: Partial<StaffClaimRow>) => {
    setAlternates((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], ...changes };
      return next;
    });
  };

  const staffOptions = useMemo(
    () => staffList.map((s) => ({ email: s.email, name: s.name })),
    [staffList]
  );

  // Match autocomplete text to a staff member by email ("Name (email)" or a bare
  // email), falling back to an exact name match when only one person has that name
  const resolveStaff = (text: string): StaffMember | undefined => {
    const email = extractPersonEmail(text);
    const byEmail = staffList.find((s) => s.email.toLowerCase() === email);
    if (byEmail) return byEmail;
    const name = text.trim().toLowerCase();
    const byName = staffList.filter((s) => s.name.toLowerCase() === name);
    return byName.length === 1 ? byName[0] : undefined;
  };

  const staffInputChanges = (text: string): Partial<StaffClaimRow> => ({
    staff_input: text,
    staff_id: resolveStaff(text)?.id ?? '',
  });

  const staffInputSubmitChanges = (text: string): Partial<StaffClaimRow> => {
    const staff = resolveStaff(text);
    return staff
      ? { staff_input: `${staff.name} (${staff.email})`, staff_id: staff.id }
      : { staff_input: text, staff_id: '' };
  };

  // How many staff pass slots the current claims consume (guests each take an extra slot)
  const staffSlotsUsed = staffClaims.reduce(
    (sum, c) => sum + 1 + (c.has_guest ? 1 : 0),
    0
  );

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (mode === 'new') {
      if (!eventName.trim()) newErrors.event_name = 'Event name is required';
      if (venueId === '') newErrors.venue_id = 'Venue is required';
      if (!showDate) newErrors.show_date = 'Show date is required';
      if (!isMultiDay && !showTime) newErrors.show_time = 'Show time is required';
      if (isMultiDay && !showStartDate) newErrors.show_start_date = 'Start date is required';
      if (numPassPairs < 1 || numPassPairs > 5) newErrors.num_pass_pairs = 'Must be 1–5';
    } else if (!selectedShow) {
      newErrors.show = 'Select a show to add to';
    }

    if (staffSlotsUsed > staffCapacity) {
      newErrors.staff_passes = `Staff claims use ${staffSlotsUsed} slots but only ${staffCapacity} available (guests each take an extra slot)`;
    }

    onAirWinners.forEach((w, i) => {
      const hasAny = w.recipient_name || w.recipient_phone || w.recipient_email;
      if (hasAny) {
        if (!w.recipient_name.trim()) newErrors[`winner_${i}_name`] = 'Name required';
        if (!w.recipient_phone.trim()) newErrors[`winner_${i}_phone`] = 'Phone required';
        if (requiresEmail && !w.recipient_email.trim()) {
          newErrors[`winner_${i}_email`] = 'This venue requires an email address';
        }
      }
    });

    staffClaims.forEach((c, i) => {
      if (c.staff_id === '') newErrors[`staff_${i}`] = 'Pick a staff member from the list';
      if (guestRequiresName && c.has_guest && !c.guest_name.trim()) {
        newErrors[`staff_${i}_guest`] = 'This venue requires a guest name';
      }
    });

    // The same rule as joining the queue in the app. The backend also checks
    // for passes held for guests already on an existing show.
    if (alternates.length > 0 && (staffSlotsUsed < staffCapacity || staffClaims.some((c) => c.has_guest))) {
      newErrors.alternates =
        'Alternates can only be added when staff members hold every staff pass, with none held for a +1 guest';
    }

    const claimantIds = new Set(staffClaims.map((c) => c.staff_id));
    const alternateIds = new Set<number>();
    alternates.forEach((a, i) => {
      if (a.staff_id === '') {
        newErrors[`alternate_${i}`] = 'Pick a staff member from the list';
      } else if (claimantIds.has(a.staff_id)) {
        newErrors[`alternate_${i}`] = 'This staff member already has a staff pass';
      } else if (alternateIds.has(a.staff_id)) {
        newErrors[`alternate_${i}`] = 'This staff member is already an alternate';
      } else {
        alternateIds.add(a.staff_id);
      }
      if (guestRequiresName && a.has_guest && !a.guest_name.trim()) {
        newErrors[`alternate_${i}_guest`] = 'This venue requires a guest name';
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const resetShowFields = () => {
    setEventName('');
    setGenres([]);
    setGenreInput('');
    setShowDate('');
    setShowTime('');
    setShowStartDate('');
    setIsMultiDay(false);
    setOnAirDescription('');
    setCallerSpecialInstructions('');
    setCoAnnounce(false);
    setStaffClaims([]);
    setAlternates([]);
    setOnAirWinners(Array.from({ length: numPassPairs }, emptyWinner));
    // Venue is intentionally kept for the next import
  };

  const handleSubmit = async () => {
    setApiError(null);
    setSuccessMessage(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      const filledWinners = onAirWinners
        .filter((w) => w.recipient_name.trim() && w.recipient_phone.trim())
        .map((w) => ({
          recipient_name: w.recipient_name.trim(),
          recipient_phone: w.recipient_phone.trim(),
          recipient_email: w.recipient_email.trim() || null,
          given_away_by_dj: w.given_away_by_dj.trim() || null,
        }));

      const toStaffPayload = (rows: StaffClaimRow[]) =>
        rows
          .filter((c) => c.staff_id !== '')
          .map((c) => ({
            staff_id: c.staff_id as number,
            has_guest: c.has_guest,
            guest_name: c.has_guest && c.guest_name.trim() ? c.guest_name.trim() : null,
          }));
      const staffPassPayload = toStaffPayload(staffClaims);
      const alternatesPayload = toStaffPayload(alternates);

      if (mode === 'new') {
        const finalGenres = genreInput.trim()
          ? [...new Set([...genres, genreInput.trim()])]
          : genres;

        const result = await legacyImportAPI.importShow({
          event_name: eventName.trim(),
          genre: finalGenres,
          venue_id: venueId as number,
          show_date: showDate,
          show_time: isMultiDay ? null : showTime || null,
          show_start_date: isMultiDay ? showStartDate : null,
          on_air_description: onAirDescription.trim() || null,
          caller_special_instructions: callerSpecialInstructions.trim() || null,
          age_restriction: isMovieTheater ? null : ageRestriction,
          movie_rating: isMovieTheater ? movieRating : null,
          wheelchair_accessible: wheelchairAccessible,
          num_pass_pairs: numPassPairs,
          co_announce: coAnnounce,
          on_air_winners: filledWinners,
          staff_passes: staffPassPayload,
          alternates: alternatesPayload,
        });

        setSuccessMessage(
          `Imported show #${result.show_id} — ${result.on_air_winners_created} on-air winner(s), ${result.staff_passes_claimed} staff pass(es) claimed, ${result.alternates_added} alternate(s).`
        );
        resetShowFields();
      } else if (selectedShow) {
        const result = await legacyImportAPI.mergeShow(selectedShow.id, {
          on_air_winners: filledWinners,
          staff_passes: staffPassPayload,
          alternates: alternatesPayload,
        });

        setSuccessMessage(
          `Added to "${selectedShow.event_name}" — ${result.on_air_winners_created} on-air winner(s), ${result.staff_passes_claimed} staff pass(es) claimed, ${result.alternates_added} alternate(s).`
        );
        // Reflect the new counts locally (and that a draft is now published)
        // so staff can keep adding more entries without re-picking the show.
        const availablePairs = selectedShow.available_pair_count - result.on_air_winners_created;
        setSelectedShow({
          ...selectedShow,
          status: 'published',
          available_pair_count: availablePairs,
          available_staff_count: selectedShow.available_staff_count - staffSlotsUsed,
        });
        clearExistingShowRows(availablePairs);
        await loadShowPasses(selectedShow.id);
      }
    } catch (err: unknown) {
      const msg =
        (err as { detail?: string })?.detail ??
        'Import failed. Please check the form and try again.';
      setApiError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const filteredExistingShows = useMemo(() => {
    const q = showSearch.trim().toLowerCase();
    if (!q) return existingShows;
    return existingShows.filter(
      (s) => s.event_name.toLowerCase().includes(q) || s.venue.name.toLowerCase().includes(q)
    );
  }, [existingShows, showSearch]);

  const handleModeChange = (next: Mode) => {
    setMode(next);
    setApiError(null);
    setSuccessMessage(null);
    setErrors({});
    if (next === 'existing') selectShow(selectedShow);
  };

  // The passes staff can release. A guest hold goes with its staff member's claim.
  const recordedWinners = (showPasses ?? []).filter(
    (p) => p.pass_type === 'pair' && p.status === 'given_away' && p.recipient_name
  );
  const recordedClaims = (showPasses ?? []).filter(
    (p) => p.pass_type === 'staff' && p.status === 'claimed' && !p.guest_of_pass_id
  );

  const guestDetail = (pass: PassResponse): string[] => {
    const name = pass.guest_name ? `: ${pass.guest_name}` : '';
    if (pass.guest_waiting) return [`+1 guest on the alternate list${name}`];
    return pass.has_guest ? [`+1 guest${name}`] : [];
  };

  if (loading) return <div className="page-loading">Loading…</div>;

  if (!enabled) {
    return (
      <div className="page-content">
        <h2>Legacy Import</h2>
        <p>This feature is not currently enabled.</p>
      </div>
    );
  }

  return (
    <div className="show-form-container">
      <div className="show-form-header">
        <h2>{mode === 'new' ? 'Paper Form Import' : 'Add to Existing Show'}</h2>
        <button className="btn-secondary" onClick={() => navigate('/promotions/shows')} disabled={submitting}>
          Back to Shows
        </button>
      </div>

      <div className="form-group">
        <div className="mine-toggle">
          <button
            type="button"
            className={mode === 'new' ? 'btn-primary btn-small' : 'btn-secondary btn-small'}
            onClick={() => handleModeChange('new')}
            disabled={submitting}
          >
            New Show
          </button>
          <button
            type="button"
            className={mode === 'existing' ? 'btn-primary btn-small' : 'btn-secondary btn-small'}
            onClick={() => handleModeChange('existing')}
            disabled={submitting}
          >
            Add to Existing Show
          </button>
        </div>
      </div>

      <div className="info-message">
        {mode === 'new' ? (
          <>
            <strong>Import mode.</strong> Use this page to enter shows that are currently active
            on paper forms. Shows are created as published so they continue to work normally —
            staff can claim passes and DJs can give away on-air winners as usual.
          </>
        ) : (
          <>
            <strong>Add to Existing Show.</strong> Use this when a show was already entered in
            staff-app before the cutover. Winners, claims and alternates are recorded against that show's
            existing passes — a draft show is published as part of this so it continues to work
            normally afterward. Winners and claims the show already has can be released here too.
          </>
        )}
      </div>

      {apiError && <div className="error-message">{apiError}</div>}
      {successMessage && <div className="success-message">{successMessage}</div>}

      <form onSubmit={(e) => e.preventDefault()} className="show-form">

        {mode === 'new' && (
          <>
            {/* ── Venue (persists across imports) ──────────── */}
            <div className="form-group">
              <label htmlFor="li_venue_id">
                Venue <span className="required">*</span>
              </label>
              <select
                id="li_venue_id"
                value={venueId}
                onChange={(e) => handleVenueChange(e.target.value === '' ? '' : parseInt(e.target.value))}
                className={errors.venue_id ? 'input-error' : ''}
                disabled={submitting}
              >
                <option value="">— Select venue —</option>
                {venues.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
              {errors.venue_id && <span className="field-error">{errors.venue_id}</span>}
              {selectedVenue && (
                <span className="field-hint">
                  Venue stays set between imports — change it when moving to a different venue's forms.
                </span>
              )}
            </div>

            <hr />

            {/* ── Show details ──────────────────────────────── */}
            <h3>Show Details</h3>

            <div className="form-group">
              <label htmlFor="li_event_name">
                Event Name <span className="required">*</span>
                {genreLookupInProgress && (
                  <span className="field-hint" style={{ marginLeft: '0.5rem', display: 'inline' }}>
                    looking up genre…
                  </span>
                )}
              </label>
              <input
                id="li_event_name"
                type="text"
                value={eventName}
                onChange={(e) => setEventName(e.target.value)}
                onBlur={handleEventNameBlur}
                className={errors.event_name ? 'input-error' : ''}
                disabled={submitting}
              />
              {errors.event_name && <span className="field-error">{errors.event_name}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="li_genre_input">Genre</label>
              <div className="genre-tag-input">
                {genres.map((g, i) => (
                  <span key={i} className="genre-tag">
                    {g}
                    <button
                      type="button"
                      className="genre-tag-remove"
                      onClick={() => removeGenre(i)}
                      disabled={submitting}
                      aria-label={`Remove ${g}`}
                    >
                      ×
                    </button>
                  </span>
                ))}
                <input
                  type="text"
                  id="li_genre_input"
                  list="li-genre-suggestions"
                  value={genreInput}
                  onChange={(e) => setGenreInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ',') {
                      e.preventDefault();
                      addGenre(genreInput);
                    }
                  }}
                  onBlur={() => { if (genreInput.trim()) addGenre(genreInput); }}
                  placeholder={genres.length === 0 ? 'Type a genre and press Enter…' : ''}
                  disabled={submitting}
                  className="genre-text-input"
                />
                <datalist id="li-genre-suggestions">
                  {knownGenres
                    .filter((g) => !genres.includes(g))
                    .map((g) => <option key={g} value={g} />)}
                </datalist>
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 500, fontSize: '0.9rem' }}>
                  Date <span className="required">*</span>
                </span>
                <div className="mine-toggle">
                  <button
                    type="button"
                    className={!isMultiDay ? 'btn-primary btn-small' : 'btn-secondary btn-small'}
                    onClick={() => { setIsMultiDay(false); setShowStartDate(''); }}
                    disabled={submitting}
                  >
                    Single Day
                  </button>
                  <button
                    type="button"
                    className={isMultiDay ? 'btn-primary btn-small' : 'btn-secondary btn-small'}
                    onClick={() => setIsMultiDay(true)}
                    disabled={submitting}
                  >
                    Multi-Day
                  </button>
                </div>
              </div>

              {isMultiDay ? (
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="li_show_start_date">Start Date <span className="required">*</span></label>
                    <DatePicker
                      id="li_show_start_date"
                      value={showStartDate}
                      onChange={setShowStartDate}
                      className={errors.show_start_date ? 'input-error' : ''}
                      disabled={submitting}
                    />
                    {errors.show_start_date && <span className="field-error">{errors.show_start_date}</span>}
                  </div>
                  <div className="form-group">
                    <label htmlFor="li_show_date_multi">End Date <span className="required">*</span></label>
                    <DatePicker
                      id="li_show_date_multi"
                      value={showDate}
                      onChange={setShowDate}
                      className={errors.show_date ? 'input-error' : ''}
                      disabled={submitting}
                    />
                    {errors.show_date && <span className="field-error">{errors.show_date}</span>}
                  </div>
                </div>
              ) : (
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="li_show_date">Show Date <span className="required">*</span></label>
                    <DatePicker
                      id="li_show_date"
                      value={showDate}
                      onChange={setShowDate}
                      className={errors.show_date ? 'input-error' : ''}
                      disabled={submitting}
                    />
                    {errors.show_date && <span className="field-error">{errors.show_date}</span>}
                  </div>
                  <div className="form-group">
                    <label htmlFor="li_show_time">Show Time <span className="required">*</span></label>
                    <input
                      id="li_show_time"
                      type="time"
                      value={showTime}
                      onChange={(e) => setShowTime(e.target.value)}
                      className={errors.show_time ? 'input-error' : ''}
                      disabled={submitting}
                    />
                    {errors.show_time && <span className="field-error">{errors.show_time}</span>}
                  </div>
                </div>
              )}
            </div>

            <div className="form-group">
              <div className="label-with-help">
                <label htmlFor="li_on_air_description">On-Air Description</label>
                <Tooltip text="Shown to DJs on the show detail page while they are on-air. Describe the show in a factual, value-neutral way. Supports Markdown formatting: headers, paragraphs, lists, blockquotes, bold/italic, and inline or block code. Links and images are not supported." />
              </div>
              <textarea
                id="li_on_air_description"
                value={onAirDescription}
                onChange={(e) => setOnAirDescription(e.target.value)}
                onBlur={() => descriptionCheck.check(onAirDescription)}
                rows={3}
                disabled={submitting}
              />
              <DescriptionCheckFeedback check={descriptionCheck} savedItem="show" />
            </div>

            <div className="form-group">
              <div className="label-with-help">
                <label htmlFor="li_caller_special_instructions">Caller Special Instructions</label>
                <Tooltip text="Shown to DJs on the give away page when recording a winner — e.g. age requirements, ID at door, or venue parking info. Supports Markdown formatting: headers, paragraphs, lists, blockquotes, bold/italic, and inline or block code. Links and images are not supported." />
              </div>
              <textarea
                id="li_caller_special_instructions"
                value={callerSpecialInstructions}
                onChange={(e) => setCallerSpecialInstructions(e.target.value)}
                rows={2}
                disabled={submitting}
              />
            </div>

            <div className="form-row">
              {isMovieTheater ? (
                <div className="form-group">
                  <label htmlFor="li_movie_rating">Movie Rating <span className="required">*</span></label>
                  <select
                    id="li_movie_rating"
                    value={movieRating}
                    onChange={(e) => setMovieRating(e.target.value as MovieRating)}
                    disabled={submitting}
                  >
                    {(Object.keys(MOVIE_RATING_LABELS) as MovieRating[]).map((rating) => (
                      <option key={rating} value={rating}>{MOVIE_RATING_LABELS[rating]}</option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="form-group">
                  <label htmlFor="li_age_restriction">Age Restriction <span className="required">*</span></label>
                  <select
                    id="li_age_restriction"
                    value={ageRestriction}
                    onChange={(e) => setAgeRestriction(e.target.value as AgeRestriction)}
                    disabled={submitting}
                  >
                    <option value="all_ages">All Ages</option>
                    <option value="18+">18+</option>
                    <option value="21+">21+</option>
                  </select>
                </div>
              )}
              <div className="form-group">
                <label htmlFor="li_num_pass_pairs">Pass Pairs <span className="required">*</span></label>
                <select
                  id="li_num_pass_pairs"
                  value={numPassPairs}
                  onChange={(e) => setNumPassPairs(parseInt(e.target.value))}
                  className={errors.num_pass_pairs ? 'input-error' : ''}
                  disabled={submitting}
                >
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
                {errors.num_pass_pairs && <span className="field-error">{errors.num_pass_pairs}</span>}
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="li_wheelchair_accessible">Wheelchair Accessible</label>
              <select
                id="li_wheelchair_accessible"
                value={wheelchairAccessible}
                onChange={(e) => setWheelchairAccessible(e.target.value as WheelchairAccessible)}
                disabled={submitting}
              >
                <option value="yes">Yes</option>
                <option value="no">No</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>

            <div className="form-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={coAnnounce}
                  onChange={(e) => setCoAnnounce(e.target.checked)}
                  disabled={submitting}
                />
                Co-Announce
              </label>
            </div>

            <hr />
          </>
        )}

        {mode === 'existing' && (
          <>
            {!selectedShow ? (
              <div className="form-group">
                <label htmlFor="li_show_search">Find Show <span className="required">*</span></label>
                <input
                  id="li_show_search"
                  type="text"
                  value={showSearch}
                  onChange={(e) => setShowSearch(e.target.value)}
                  placeholder="Search by event name or venue…"
                  disabled={submitting}
                />
                {errors.show && <span className="field-error">{errors.show}</span>}

                {existingShowsLoading && <p className="field-hint">Loading shows…</p>}
                {existingShowsError && <div className="error-message">{existingShowsError}</div>}

                {!existingShowsLoading && !existingShowsError && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.75rem' }}>
                    {filteredExistingShows.length === 0 && (
                      <p className="field-hint">No draft or published shows match.</p>
                    )}
                    {filteredExistingShows.map((show) => (
                      <div
                        key={show.id}
                        className="pass-card"
                        style={{ cursor: 'pointer' }}
                        onClick={() => selectShow(show)}
                      >
                        <div className="pass-header">
                          <h3>{show.event_name}</h3>
                          <span className={`status-badge status-${show.status}`}>{show.status}</span>
                        </div>
                        <div className="pass-details">
                          <p>{show.venue.name} · {show.show_date}</p>
                          <p>{show.available_pair_count} pair / {show.available_staff_count} staff pass(es) available</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="pass-card">
                <div className="pass-header">
                  <h3>{selectedShow.event_name}</h3>
                  <button
                    type="button"
                    className="btn-secondary btn-small"
                    onClick={() => selectShow(null)}
                    disabled={submitting || releasing}
                  >
                    Change Show
                  </button>
                </div>
                <div className="pass-details">
                  <p>{selectedShow.venue.name} · {selectedShow.show_date}</p>
                  <p>
                    <span className={`status-badge status-${selectedShow.status}`}>{selectedShow.status}</span>
                    {' '}· {selectedShow.available_pair_count} pair / {selectedShow.available_staff_count} staff pass(es) available
                  </p>
                </div>
              </div>
            )}
          </>
        )}

        {(mode === 'new' || selectedShow) && (
          <>
            {showPassesError && <div className="error-message">{showPassesError}</div>}

            {/* ── On-air winners ─────────────────────────────── */}
            <h3>On-Air Pass Winners</h3>

            {mode === 'existing' && recordedWinners.map((pass) => (
              <RecordedPassCard
                key={pass.id}
                pass={pass}
                title={`Winner: ${pass.recipient_name}`}
                details={[
                  ...(pass.recipient_phone ? [formatPhone(pass.recipient_phone)] : []),
                  ...(pass.recipient_email ? [pass.recipient_email] : []),
                  ...(pass.given_away_by_dj ? [`Given away by ${pass.given_away_by_dj}`] : []),
                ]}
                releaseNote="These passes can then be given away again. The show's KALX promotions reps are emailed the reason."
                asksForReason
                disabled={submitting || releasing}
                onRelease={(reason) => releaseWinner(pass, reason)}
              />
            ))}

            <p className="field-hint">Leave a row blank if that pass was not yet given away.</p>

            {onAirWinners.map((winner, i) => (
              <div key={i} className="pass-card" style={{ marginBottom: '0.75rem' }}>
                <div className="pass-header">
                  <h3>Pair {i + 1}</h3>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor={`li_w${i}_name`}>Winner Name</label>
                    <input
                      id={`li_w${i}_name`}
                      type="text"
                      value={winner.recipient_name}
                      onChange={(e) => updateWinner(i, 'recipient_name', e.target.value)}
                      className={errors[`winner_${i}_name`] ? 'input-error' : ''}
                      disabled={submitting}
                    />
                    {errors[`winner_${i}_name`] && (
                      <span className="field-error">{errors[`winner_${i}_name`]}</span>
                    )}
                  </div>
                  <div className="form-group">
                    <label htmlFor={`li_w${i}_phone`}>Phone</label>
                    <input
                      id={`li_w${i}_phone`}
                      type="tel"
                      value={winner.recipient_phone}
                      onChange={(e) => updateWinner(i, 'recipient_phone', e.target.value)}
                      className={errors[`winner_${i}_phone`] ? 'input-error' : ''}
                      disabled={submitting}
                    />
                    {errors[`winner_${i}_phone`] && (
                      <span className="field-error">{errors[`winner_${i}_phone`]}</span>
                    )}
                  </div>
                </div>
                {requiresEmail && (
                  <div className="form-group">
                    <label htmlFor={`li_w${i}_email`}>
                      Email <span className="required">*</span>
                    </label>
                    <input
                      id={`li_w${i}_email`}
                      type="email"
                      value={winner.recipient_email}
                      onChange={(e) => updateWinner(i, 'recipient_email', e.target.value)}
                      className={errors[`winner_${i}_email`] ? 'input-error' : ''}
                      disabled={submitting}
                    />
                    {errors[`winner_${i}_email`] && (
                      <span className="field-error">{errors[`winner_${i}_email`]}</span>
                    )}
                  </div>
                )}
                <div className="form-group">
                  <label htmlFor={`li_w${i}_dj`}>Given Away By (DJ)</label>
                  <DjNameAutocomplete
                    id={`li_w${i}_dj`}
                    value={winner.given_away_by_dj}
                    onChange={(name) => updateWinner(i, 'given_away_by_dj', name)}
                    djNames={djNames}
                    specialtyShowNames={specialtyShowNames}
                    disabled={submitting}
                  />
                </div>
              </div>
            ))}

            {/* ── Staff passes ───────────────────────────────── */}
            <h3>
              Staff Passes Claimed
              <span
                className="field-hint"
                style={{
                  display: 'inline',
                  marginLeft: '0.75rem',
                  color: staffSlotsUsed > staffCapacity ? 'var(--danger-color)' : undefined,
                }}
              >
                {staffSlotsUsed} of {staffCapacity} slot{staffCapacity !== 1 ? 's' : ''} used
                {staffSlotsUsed > 0 && staffClaims.some((c) => c.has_guest) && ' (guests each use an extra slot)'}
              </span>
            </h3>
            {errors.staff_passes && <div className="field-error">{errors.staff_passes}</div>}

            {mode === 'existing' && recordedClaims.map((pass) => (
              <RecordedPassCard
                key={pass.id}
                pass={pass}
                title={`Claimed by ${pass.staff_name ?? 'unknown staff member'}`}
                details={guestDetail(pass)}
                releaseNote="If anyone is on the show's alternate list, the next alternate gets this pass and is emailed. Any +1 guest is released too."
                asksForReason={false}
                disabled={submitting || releasing}
                onRelease={() => releaseClaim(pass)}
              />
            ))}

            {staffClaims.length === 0 && recordedClaims.length === 0 && (
              <p className="field-hint">No staff passes claimed yet.</p>
            )}

            {staffClaims.map((claim, i) => (
              <StaffRowCard
                key={i}
                title={`Claimant ${i + 1}`}
                idPrefix={`li_staff_${i}`}
                row={claim}
                error={errors[`staff_${i}`]}
                guestError={errors[`staff_${i}_guest`]}
                guestRequiresName={guestRequiresName}
                staffOptions={staffOptions}
                disabled={submitting}
                onRemove={() => removeStaffClaim(i)}
                onChange={(changes) => updateStaffClaim(i, changes)}
                onStaffInputChange={(text) => updateStaffClaim(i, staffInputChanges(text))}
                onStaffInputSubmit={(text) => updateStaffClaim(i, staffInputSubmitChanges(text))}
              />
            ))}

            {staffSlotsUsed < staffCapacity && (
              <button
                type="button"
                className="btn-secondary"
                onClick={addStaffClaim}
                disabled={submitting}
                style={{ marginBottom: '1rem' }}
              >
                + Add Staff Claimant
              </button>
            )}

            {/* ── Alternates ─────────────────────────────────── */}
            <h3>Staff Pass Alternates</h3>
            <p className="field-hint">
              Enter them in the order they're waiting. Only available when staff members hold every
              staff pass, with none held for a +1 guest. They aren't emailed.
              {mode === 'existing' && ' They go after anyone already on the show\'s list.'}
            </p>
            {errors.alternates && <div className="field-error">{errors.alternates}</div>}

            {alternates.map((alternate, i) => (
              <StaffRowCard
                key={i}
                title={`Alternate ${i + 1}`}
                idPrefix={`li_alternate_${i}`}
                row={alternate}
                error={errors[`alternate_${i}`]}
                guestError={errors[`alternate_${i}_guest`]}
                guestRequiresName={guestRequiresName}
                staffOptions={staffOptions}
                disabled={submitting}
                onRemove={() => removeAlternate(i)}
                onChange={(changes) => updateAlternate(i, changes)}
                onStaffInputChange={(text) => updateAlternate(i, staffInputChanges(text))}
                onStaffInputSubmit={(text) => updateAlternate(i, staffInputSubmitChanges(text))}
              />
            ))}

            <button
              type="button"
              className="btn-secondary"
              onClick={addAlternate}
              disabled={submitting}
              style={{ marginBottom: '1rem' }}
            >
              + Add Alternate
            </button>

            {/* ── Submit ─────────────────────────────────────── */}
            <div className="form-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => navigate('/promotions/shows')}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleSubmit}
                disabled={submitting || releasing || (mode === 'new' ? venueId === '' : !selectedShow)}
              >
                {submitting
                  ? mode === 'new' ? 'Importing…' : 'Adding…'
                  : mode === 'new' ? 'Import Show' : 'Add to Show'}
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  );
};

export default LegacyImport;
