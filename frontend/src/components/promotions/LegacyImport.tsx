import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { legacyImportAPI, venuesAPI, showsAPI } from '../../services/api';
import type { VenueResponse, AgeRestriction } from '../../types';
import { DatePicker } from '../shared';

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
  const navigate = useNavigate();

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

  // Show fields
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

  // On-air winners (one row per pass pair slot)
  const [onAirWinners, setOnAirWinners] = useState<OnAirWinnerRow[]>([emptyWinner()]);

  // Staff claimants (dynamic list)
  const [staffClaims, setStaffClaims] = useState<StaffClaimRow[]>([]);

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

  // Sync winner/claimant arrays when numPassPairs changes
  useEffect(() => {
    setOnAirWinners((prev) => {
      const next = [...prev];
      while (next.length < numPassPairs) next.push(emptyWinner());
      return next.slice(0, numPassPairs);
    });
  }, [numPassPairs]);

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
    if (!eventName.trim()) newErrors.event_name = 'Event name is required';
    if (venueId === '') newErrors.venue_id = 'Venue is required';
    if (!showDate) newErrors.show_date = 'Show date is required';
    if (!isMultiDay && !showTime) newErrors.show_time = 'Show time is required';
    if (isMultiDay && !showStartDate) newErrors.show_start_date = 'Start date is required';
    if (numPassPairs < 1 || numPassPairs > 5) newErrors.num_pass_pairs = 'Must be 1–5';
    if (staffSlotsUsed > numPassPairs) {
      newErrors.staff_passes = `Staff claims use ${staffSlotsUsed} slots but only ${numPassPairs} available (guests each take an extra slot)`;
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
      const finalGenres = genreInput.trim()
        ? [...new Set([...genres, genreInput.trim()])]
        : genres;

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
    } catch (err: unknown) {
      const msg =
        (err as { detail?: string })?.detail ??
        'Import failed. Please check the form and try again.';
      setApiError(msg);
    } finally {
      setSubmitting(false);
    }
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
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 style={{ margin: 0 }}>Paper Form Import</h2>
        <button className="btn-secondary" onClick={() => navigate('/promotions/shows')} disabled={submitting}>
          Back to Shows
        </button>
      </div>

      <div className="error-message" style={{ background: '#e8f4fd', borderColor: '#90caf9', color: '#0d47a1', marginBottom: '1.25rem' }}>
        <strong>Import mode.</strong> Use this page to enter shows that are currently active
        on paper forms. Shows are created as published so they continue to work normally —
        staff can claim passes and DJs can give away on-air winners as usual.
      </div>

      {apiError && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>{apiError}</div>
      )}
      {successMessage && (
        <div className="error-message" style={{ background: '#d4edda', borderColor: '#28a745', color: '#155724', marginBottom: '1rem' }}>
          {successMessage}
        </div>
      )}

      <form onSubmit={(e) => e.preventDefault()} className="show-form">

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
            <span style={{ fontSize: '0.85em', color: '#666', marginTop: '0.25rem', display: 'block' }}>
              Venue stays set between imports — change it when moving to a different venue's forms.
            </span>
          )}
        </div>

        <hr style={{ margin: '1rem 0' }} />

        {/* ── Show details ──────────────────────────────── */}
        <h3 style={{ marginTop: 0 }}>Show Details</h3>

        <div className="form-group">
          <label htmlFor="li_event_name">
            Event Name <span className="required">*</span>
            {genreLookupInProgress && (
              <span style={{ marginLeft: '0.5rem', fontWeight: 'normal', color: '#666', fontSize: '0.85em' }}>
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

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={isMultiDay}
              onChange={(e) => setIsMultiDay(e.target.checked)}
              disabled={submitting}
              style={{ marginRight: '0.4rem' }}
            />
            Multi-day show
          </label>
        </div>

        {isMultiDay ? (
          <div className="form-row" style={{ display: 'flex', gap: '1rem' }}>
            <div className="form-group" style={{ flex: 1 }}>
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
            <div className="form-group" style={{ flex: 1 }}>
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
          <div className="form-row" style={{ display: 'flex', gap: '1rem' }}>
            <div className="form-group" style={{ flex: 1 }}>
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
            <div className="form-group" style={{ flex: 1 }}>
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

        <div className="form-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ flex: '1 1 160px' }}>
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
          <div className="form-group" style={{ flex: '1 1 120px' }}>
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
          <div className="form-group" style={{ flex: '1 1 160px', display: 'flex', alignItems: 'flex-end', paddingBottom: '0.1rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={wheelchairAccessible}
                onChange={(e) => setWheelchairAccessible(e.target.checked)}
                disabled={submitting}
              />
              Wheelchair Accessible
            </label>
          </div>
          <div className="form-group" style={{ flex: '1 1 120px', display: 'flex', alignItems: 'flex-end', paddingBottom: '0.1rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={coAnnounce}
                onChange={(e) => setCoAnnounce(e.target.checked)}
                disabled={submitting}
              />
              Co-Announce
            </label>
          </div>
        </div>

        {/* ── On-air winners ─────────────────────────────── */}
        <h3 style={{ marginTop: '1.5rem' }}>On-Air Pass Winners</h3>
        <p style={{ marginTop: 0, color: '#555', fontSize: '0.9em' }}>
          Leave a row blank if that pass was not yet given away.
        </p>

        {onAirWinners.map((winner, i) => (
          <div
            key={i}
            style={{ border: '1px solid #ddd', borderRadius: '6px', padding: '0.75rem', marginBottom: '0.75rem' }}
          >
            <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: '#444' }}>Pair {i + 1}</div>
            <div className="form-row" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <div className="form-group" style={{ flex: '2 1 160px' }}>
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
              <div className="form-group" style={{ flex: '1 1 140px' }}>
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
              {selectedVenue?.requires_email_address && (
                <div className="form-group" style={{ flex: '2 1 160px' }}>
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
              <div className="form-group" style={{ flex: '2 1 160px' }}>
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
          </div>
        ))}

        {/* ── Staff passes ───────────────────────────────── */}
        <h3 style={{ marginTop: '1.5rem' }}>
          Staff Passes Claimed
          <span style={{ marginLeft: '0.75rem', fontSize: '0.8em', fontWeight: 'normal', color: staffSlotsUsed > numPassPairs ? '#c62828' : '#666' }}>
            {staffSlotsUsed} of {numPassPairs} slot{numPassPairs !== 1 ? 's' : ''} used
            {staffSlotsUsed > 0 && staffClaims.some((c) => c.has_guest) && ' (guests each use an extra slot)'}
          </span>
        </h3>
        {errors.staff_passes && (
          <div className="field-error" style={{ marginBottom: '0.75rem' }}>{errors.staff_passes}</div>
        )}

        {staffClaims.length === 0 && (
          <p style={{ color: '#666', fontSize: '0.9em', marginTop: 0 }}>
            No staff passes claimed yet.
          </p>
        )}

        {staffClaims.map((claim, i) => (
          <div
            key={i}
            style={{ border: '1px solid #ddd', borderRadius: '6px', padding: '0.75rem', marginBottom: '0.75rem' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ fontWeight: 600, color: '#444' }}>Claimant {i + 1}</span>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: '0.2rem 0.6rem', fontSize: '0.85em' }}
                onClick={() => removeStaffClaim(i)}
                disabled={submitting}
              >
                Remove
              </button>
            </div>
            <div className="form-row" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div className="form-group" style={{ flex: '2 1 200px' }}>
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
              <div className="form-group" style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: '0.4rem', paddingBottom: '0.1rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', margin: 0 }}>
                  <input
                    type="checkbox"
                    checked={claim.has_guest}
                    onChange={(e) => updateStaffClaim(i, { has_guest: e.target.checked })}
                    disabled={submitting}
                  />
                  +1 Guest
                </label>
              </div>
              {claim.has_guest && (
                <div className="form-group" style={{ flex: '2 1 160px' }}>
                  <label htmlFor={`li_staff_${i}_guest`}>Guest Name</label>
                  <input
                    id={`li_staff_${i}_guest`}
                    type="text"
                    value={claim.guest_name}
                    onChange={(e) => updateStaffClaim(i, { guest_name: e.target.value })}
                    disabled={submitting}
                    placeholder={selectedVenue?.staff_guest_requires_name ? 'Required' : 'Optional'}
                  />
                </div>
              )}
            </div>
          </div>
        ))}

        {staffSlotsUsed < numPassPairs && (
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
        <div className="form-actions" style={{ marginTop: '1.5rem' }}>
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
            disabled={submitting || venueId === ''}
          >
            {submitting ? 'Importing…' : 'Import Show'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default LegacyImport;
