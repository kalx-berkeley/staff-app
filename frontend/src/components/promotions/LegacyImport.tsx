import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { legacyImportAPI, venuesAPI, showsAPI } from '../../services/api';
import type { VenueResponse, AgeRestriction, ShowSummary } from '../../types';
import { DatePicker } from '../shared';
import { usePageTitle } from '../../hooks/usePageTitle';

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
  has_guest: false,
  guest_name: '',
});

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
  const [wheelchairAccessible, setWheelchairAccessible] = useState(true);
  const [numPassPairs, setNumPassPairs] = useState(1);
  const [coAnnounce, setCoAnnounce] = useState(false);

  // Existing Show mode: picker state
  const [existingShows, setExistingShows] = useState<ShowSummary[]>([]);
  const [existingShowsLoading, setExistingShowsLoading] = useState(false);
  const [existingShowsError, setExistingShowsError] = useState<string | null>(null);
  const [showSearch, setShowSearch] = useState('');
  const [selectedShow, setSelectedShow] = useState<ShowSummary | null>(null);

  // On-air winners and staff claimants — shared between both modes
  const [onAirWinners, setOnAirWinners] = useState<OnAirWinnerRow[]>([emptyWinner()]);
  const [staffClaims, setStaffClaims] = useState<StaffClaimRow[]>([]);

  const staffCapacity = mode === 'new' ? numPassPairs : (selectedShow?.available_staff_count ?? 0);

  const selectedShowVenue = useMemo(
    () => (selectedShow ? venues.find((v) => v.id === selectedShow.venue.id) ?? null : null),
    [selectedShow, venues]
  );

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

  // Keep the winner/claim rows sized to the current capacity — the chosen
  // pass-pair count in New Show mode, or the selected show's remaining
  // available passes in Existing Show mode. Also clears stale entries
  // whenever the target show changes (or a submission just succeeded), so
  // leftover text never gets attributed to the wrong show.
  useEffect(() => {
    if (mode === 'new') {
      setOnAirWinners((prev) => {
        const next = [...prev];
        while (next.length < numPassPairs) next.push(emptyWinner());
        return next.slice(0, numPassPairs);
      });
    } else {
      setOnAirWinners(Array.from({ length: selectedShow?.available_pair_count ?? 0 }, emptyWinner));
      setStaffClaims([]);
      setErrors({});
    }
  }, [mode, numPassPairs, selectedShow]);

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
      const hasAny = w.recipient_name || w.recipient_phone;
      if (hasAny) {
        if (!w.recipient_name.trim()) newErrors[`winner_${i}_name`] = 'Name required';
        if (!w.recipient_phone.trim()) newErrors[`winner_${i}_phone`] = 'Phone required';
      }
    });

    staffClaims.forEach((c, i) => {
      if (c.staff_id === '') newErrors[`staff_${i}`] = 'Select a staff member';
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

      const staffPassPayload = staffClaims
        .filter((c) => c.staff_id !== '')
        .map((c) => ({
          staff_id: c.staff_id as number,
          has_guest: c.has_guest,
          guest_name: c.has_guest && c.guest_name.trim() ? c.guest_name.trim() : null,
        }));

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
          age_restriction: ageRestriction,
          wheelchair_accessible: wheelchairAccessible,
          num_pass_pairs: numPassPairs,
          co_announce: coAnnounce,
          on_air_winners: filledWinners,
          staff_passes: staffPassPayload,
        });

        setSuccessMessage(
          `Imported show #${result.show_id} — ${result.on_air_winners_created} on-air winner(s), ${result.staff_passes_claimed} staff pass(es) claimed.`
        );
        resetShowFields();
      } else if (selectedShow) {
        const result = await legacyImportAPI.mergeShow(selectedShow.id, {
          on_air_winners: filledWinners,
          staff_passes: staffPassPayload,
        });

        setSuccessMessage(
          `Added to "${selectedShow.event_name}" — ${result.on_air_winners_created} on-air winner(s), ${result.staff_passes_claimed} staff pass(es) claimed.`
        );
        // Reflect the new counts locally (and that a draft is now published)
        // so staff can keep adding more entries without re-picking the show.
        setSelectedShow((prev) =>
          prev
            ? {
                ...prev,
                status: 'published',
                available_pair_count: prev.available_pair_count - result.on_air_winners_created,
                available_staff_count: prev.available_staff_count - staffSlotsUsed,
              }
            : prev
        );
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
            staff-app before the cutover. Winners and claims are recorded against that show's
            existing passes — a draft show is published as part of this so it continues to work
            normally afterward.
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
              <label htmlFor="li_on_air_description">On-Air Description</label>
              <textarea
                id="li_on_air_description"
                value={onAirDescription}
                onChange={(e) => setOnAirDescription(e.target.value)}
                rows={3}
                disabled={submitting}
              />
            </div>

            <div className="form-group">
              <label htmlFor="li_caller_special_instructions">Caller Special Instructions</label>
              <textarea
                id="li_caller_special_instructions"
                value={callerSpecialInstructions}
                onChange={(e) => setCallerSpecialInstructions(e.target.value)}
                rows={2}
                disabled={submitting}
              />
            </div>

            <div className="form-row">
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

            <div className="form-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={wheelchairAccessible}
                  onChange={(e) => setWheelchairAccessible(e.target.checked)}
                  disabled={submitting}
                />
                Wheelchair Accessible
              </label>
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
                        onClick={() => setSelectedShow(show)}
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
                    onClick={() => setSelectedShow(null)}
                    disabled={submitting}
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
            {/* ── On-air winners ─────────────────────────────── */}
            <h3>On-Air Pass Winners</h3>
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
                {selectedShowVenue?.requires_email_address && (
                  <div className="form-group">
                    <label htmlFor={`li_w${i}_email`}>Email</label>
                    <input
                      id={`li_w${i}_email`}
                      type="email"
                      value={winner.recipient_email}
                      onChange={(e) => updateWinner(i, 'recipient_email', e.target.value)}
                      disabled={submitting}
                    />
                  </div>
                )}
                <div className="form-group">
                  <label htmlFor={`li_w${i}_dj`}>Given Away By (DJ)</label>
                  <input
                    id={`li_w${i}_dj`}
                    type="text"
                    value={winner.given_away_by_dj}
                    onChange={(e) => updateWinner(i, 'given_away_by_dj', e.target.value)}
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

            {staffClaims.length === 0 && (
              <p className="field-hint">No staff passes claimed yet.</p>
            )}

            {staffClaims.map((claim, i) => (
              <div key={i} className="pass-card" style={{ marginBottom: '0.75rem' }}>
                <div className="pass-header">
                  <h3>Claimant {i + 1}</h3>
                  <button
                    type="button"
                    className="btn-secondary btn-small"
                    onClick={() => removeStaffClaim(i)}
                    disabled={submitting}
                  >
                    Remove
                  </button>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor={`li_staff_${i}`}>Staff Member</label>
                    <select
                      id={`li_staff_${i}`}
                      value={claim.staff_id}
                      onChange={(e) =>
                        updateStaffClaim(i, {
                          staff_id: e.target.value === '' ? '' : parseInt(e.target.value),
                        })
                      }
                      className={errors[`staff_${i}`] ? 'input-error' : ''}
                      disabled={submitting}
                    >
                      <option value="">— Select staff member —</option>
                      {staffList.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                    {errors[`staff_${i}`] && (
                      <span className="field-error">{errors[`staff_${i}`]}</span>
                    )}
                  </div>
                  <div className="form-group checkbox-group">
                    <label>
                      <input
                        type="checkbox"
                        checked={claim.has_guest}
                        onChange={(e) => updateStaffClaim(i, { has_guest: e.target.checked })}
                        disabled={submitting}
                      />
                      +1 Guest
                    </label>
                  </div>
                </div>
                {claim.has_guest && (
                  <div className="form-group">
                    <label htmlFor={`li_staff_${i}_guest`}>Guest Name</label>
                    <input
                      id={`li_staff_${i}_guest`}
                      type="text"
                      value={claim.guest_name}
                      onChange={(e) => updateStaffClaim(i, { guest_name: e.target.value })}
                      disabled={submitting}
                      placeholder={selectedShowVenue?.staff_guest_requires_name ? 'Required' : 'Optional'}
                    />
                  </div>
                )}
              </div>
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
                disabled={submitting || (mode === 'new' ? venueId === '' : !selectedShow)}
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
