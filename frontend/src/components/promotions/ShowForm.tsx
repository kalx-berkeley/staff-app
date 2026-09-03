import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { showsAPI, venuesAPI, venuesMyAPI, promotersAPI } from '../../services/api';
import { Tooltip, BandAnnotator } from '../shared';
import { formatPhone } from '../../utils';
import type {
  ShowCreate,
  ShowUpdate,
  ShowBand,
  MusicBrainzArtist,
  VenueResponse,
  AgeRestriction,
  APIError,
  ValidationError,
  PassResponse,
  PromoterResponse,
  PassAdjustmentResult,
} from '../../types';

interface DeleteConfirmModalProps {
  eventName: string;
  passes: PassResponse[];
  onConfirm: () => void;
  onCancel: () => void;
}

const DeleteConfirmModal = ({ eventName, passes, onConfirm, onCancel }: DeleteConfirmModalProps) => {
  const givenAwayPasses = passes.filter((p) => p.pass_type === 'pair' && p.status === 'given_away');
  const claimedPasses = passes.filter((p) => p.pass_type === 'staff' && p.status === 'claimed');
  const preassignedPasses = passes.filter((p) => p.pass_type === 'pair' && p.preassigned_dj);
  const hasContactWarning = givenAwayPasses.length > 0 || claimedPasses.length > 0;
  const hasPreassignWarning = preassignedPasses.length > 0;

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Delete Show</h3>
          <button className="btn-close" onClick={onCancel}>×</button>
        </div>
        <p>
          Are you sure you want to permanently delete <strong>{eventName}</strong>?
          This cannot be undone.
        </p>

        {hasContactWarning && (
          <div className="error-message" style={{ marginBottom: '1rem' }}>
            <strong>Action required:</strong> This show has passes that have already been
            distributed. You will need to personally contact the following people to let
            them know the show has been cancelled. The venue owner will also receive an
            email notification.
            {givenAwayPasses.length > 0 && (
              <>
                <p style={{ marginTop: '0.5rem', marginBottom: '0.25rem' }}><strong>On-air winners:</strong></p>
                <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                  {givenAwayPasses.map((p) => (
                    <li key={p.id}>
                      {p.recipient_name} ({formatPhone(p.recipient_phone)})
                      {p.given_away_by_dj ? ` — given by ${p.given_away_by_dj}` : ''}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {claimedPasses.length > 0 && (
              <>
                <p style={{ marginTop: '0.5rem', marginBottom: '0.25rem' }}><strong>Staff who claimed passes:</strong></p>
                <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                  {claimedPasses.map((p) => (
                    <li key={p.id}>{p.staff_name} ({formatPhone(p.staff_phone)})</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}

        {hasPreassignWarning && (
          <div className="error-message" style={{ marginBottom: '1rem', background: '#fff3cd', borderColor: '#ffc107', color: '#856404' }}>
            <strong>Heads up:</strong> The following DJs have passes pre-assigned for this show.
            They may be planning to give away tickets on an upcoming air shift. Please notify them
            that this show has been cancelled.
            <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.25rem' }}>
              {preassignedPasses.map((p) => (
                <li key={p.id}>
                  {p.preassigned_dj}
                  {p.preassigned_date ? ` (assigned for ${p.preassigned_date})` : ''}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="form-actions" style={{ marginTop: '1rem' }}>
          <button onClick={onCancel} className="btn-secondary">Cancel</button>
          <button onClick={onConfirm} className="btn-danger">Delete Show</button>
        </div>
      </div>
    </div>
  );
};

interface PassAdjustmentModalProps {
  eventName: string;
  adjustment: PassAdjustmentResult;
  onClose: () => void;
}

const PassAdjustmentModal = ({ eventName, adjustment, onClose }: PassAdjustmentModalProps) => (
  <div className="modal-overlay" onClick={onClose}>
    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
      <div className="modal-header">
        <h3>Pass Count Reduced — Action Required</h3>
        <button className="btn-close" onClick={onClose}>×</button>
      </div>
      <p>
        The number of passes for <strong>{eventName}</strong> was reduced. The following
        people have been affected. A notification email has been sent to the venue
        owners. Please contact these individuals to let them know.
      </p>
      {adjustment.affected_djs.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <strong>DJs whose pre-assigned passes have been removed:</strong>
          <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
            {adjustment.affected_djs.map((dj, i) => (
              <li key={i}>{dj}</li>
            ))}
          </ul>
        </div>
      )}
      {adjustment.affected_staff.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <strong>Staff members who no longer have a claimed pass:</strong>
          <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
            {adjustment.affected_staff.map((s, i) => (
              <li key={i}>
                {s.name}
                {s.phone ? ` (${formatPhone(s.phone)})` : ''}
                {s.email ? ` — ${s.email}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="form-actions" style={{ marginTop: '1rem' }}>
        <button onClick={onClose} className="btn-primary">Understood</button>
      </div>
    </div>
  </div>
);

const ShowForm = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditing = !!id;

  const [venues, setVenues] = useState<VenueResponse[]>([]);
  const [promotersList, setPromotersList] = useState<PromoterResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [passAdjustment, setPassAdjustment] = useState<PassAdjustmentResult | null>(null);
  const [eventNameSnapshot, setEventNameSnapshot] = useState('');
  const [showPasses, setShowPasses] = useState<PassResponse[]>([]);
  const [showMineOnly, setShowMineOnly] = useState(true);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const venueToggleMounted = useRef(false);

  const [genreLookupInProgress, setGenreLookupInProgress] = useState(false);
  const [knownGenres, setKnownGenres] = useState<string[]>([]);
  const [bands, setBands] = useState<ShowBand[]>([]);

  // Form fields
  const [eventName, setEventName] = useState('');
  const [genres, setGenres] = useState<string[]>([]);
  const [genreInput, setGenreInput] = useState('');
  const [venueId, setVenueId] = useState<number | ''>('');
  const [promoterId, setPromoterId] = useState<number | null>(null);
  const [showDate, setShowDate] = useState('');
  const [showTime, setShowTime] = useState('19:00');
  const [showStartDate, setShowStartDate] = useState('');
  const [isMultiDay, setIsMultiDay] = useState(false);
  const [onAirDescription, setOnAirDescription] = useState('');
  const [callerSpecialInstructions, setCallerSpecialInstructions] = useState('');
  const [ageRestriction, setAgeRestriction] = useState<AgeRestriction>('all_ages');
  const [wheelchairAccessible, setWheelchairAccessible] = useState(true);
  const [numPassPairs, setNumPassPairs] = useState<number>(1);
  const [plannedCloseDate, setPlannedCloseDate] = useState('');
  const [plannedCloseTime, setPlannedCloseTime] = useState('');
  const [autoClose, setAutoClose] = useState(true);
  const [coAnnounce, setCoAnnounce] = useState(false);
  const [lotteryEnabled, setLotteryEnabled] = useState(false);
  const [lotteryWindowHours, setLotteryWindowHours] = useState('24');
  const [djPreassignProhibitionDays, setDjPreassignProhibitionDays] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setApiError(null);

        // Load venues, genres, and promoters in parallel
        const [venuesData, genreList, promotersData] = await Promise.all([
          venuesMyAPI.listMy(),
          showsAPI.listGenres().catch(() => [] as string[]),
          promotersAPI.list().catch(() => [] as PromoterResponse[]),
        ]);
        setVenues(venuesData);
        setKnownGenres(genreList);
        setPromotersList(promotersData);

        // Auto-select venue for new shows when user owns exactly one
        if (!isEditing && venuesData.length === 1) {
          const only = venuesData[0];
          setVenueId(only.id);
          setPromoterId(only.promoter_id ?? null);
          if (only.default_wheelchair_accessible !== null && only.default_wheelchair_accessible !== undefined) {
            setWheelchairAccessible(only.default_wheelchair_accessible);
          }
          if (only.default_age_restriction) {
            setAgeRestriction(only.default_age_restriction);
          }
          if (only.default_num_pass_pairs != null) {
            setNumPassPairs(only.default_num_pass_pairs);
          }
          setLotteryEnabled(only.default_lottery_enabled ?? false);
          setLotteryWindowHours(String(only.default_lottery_window_hours ?? 24));
          setDjPreassignProhibitionDays(
            only.default_dj_preassign_prohibition_days != null
              ? String(only.default_dj_preassign_prohibition_days)
              : ''
          );
        }

        // Load show if editing
        if (isEditing && id) {
          const show = await showsAPI.get(parseInt(id));
          setEventName(show.event_name);
          setEventNameSnapshot(show.event_name);
          setShowPasses(show.passes);
          setGenres(show.genre ?? []);
          setVenueId(show.venue.id);
          setPromoterId(show.promoter_id ?? null);
          if (!venuesData.some((v) => v.id === show.venue.id)) {
            setShowMineOnly(false);
          }
          setShowDate(show.show_date);
          setShowTime(show.show_time || '');
          setShowStartDate(show.show_start_date || '');
          setIsMultiDay(!!show.show_start_date);
          setOnAirDescription(show.on_air_description || '');
          setCallerSpecialInstructions(show.caller_special_instructions || '');
          setAgeRestriction(show.age_restriction);
          setWheelchairAccessible(show.wheelchair_accessible);
          setNumPassPairs(show.num_pass_pairs);
          setPlannedCloseDate(show.planned_close_date ?? '');
          setPlannedCloseTime(show.planned_close_time ?? '');
          setAutoClose(show.auto_close ?? false);
          setCoAnnounce(show.co_announce ?? false);
          setLotteryEnabled(show.lottery_enabled ?? false);
          setLotteryWindowHours(String(show.lottery_window_hours ?? 24));
          setDjPreassignProhibitionDays(
            show.dj_preassign_prohibition_days != null
              ? String(show.dj_preassign_prohibition_days)
              : ''
          );
          setBands(show.bands ?? []);
        }
      } catch (err) {
        const error = err as APIError;
        setApiError(
          typeof error.detail === 'string'
            ? error.detail
            : 'Failed to load data'
        );
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [id, isEditing]);

  useEffect(() => {
    if (!venueToggleMounted.current) {
      venueToggleMounted.current = true;
      return;
    }
    const reloadVenues = async () => {
      try {
        const data = showMineOnly ? await venuesMyAPI.listMy() : await venuesAPI.list();
        setVenues(data);
      } catch (err) {
        const error = err as APIError;
        setApiError(
          typeof error.detail === 'string' ? error.detail : 'Failed to load venues'
        );
      }
    };
    reloadVenues();
  }, [showMineOnly]);

  const applyVenueCloseDefault = (date: string, time: string, hoursBeforeShow: number) => {
    const [year, month, day] = date.split('-').map(Number);
    const [hours, minutes] = time.split(':').map(Number);
    const dt = new Date(year, month - 1, day, hours, minutes);
    dt.setHours(dt.getHours() - hoursBeforeShow);
    const closeDate = [
      dt.getFullYear(),
      String(dt.getMonth() + 1).padStart(2, '0'),
      String(dt.getDate()).padStart(2, '0'),
    ].join('-');
    const closeTime = [
      String(dt.getHours()).padStart(2, '0'),
      String(dt.getMinutes()).padStart(2, '0'),
    ].join(':');
    setPlannedCloseDate(closeDate);
    setPlannedCloseTime(closeTime);
  };

  const handleShowDateChange = (newDate: string) => {
    setShowDate(newDate);
    if (!plannedCloseDate && !plannedCloseTime && newDate && showTime) {
      const selected = venueId !== '' ? venues.find((v) => v.id === venueId) : undefined;
      if (selected?.default_close_hours_before_show != null) {
        applyVenueCloseDefault(newDate, showTime, selected.default_close_hours_before_show);
      }
    }
  };

  const handleShowTimeChange = (newTime: string) => {
    setShowTime(newTime);
    if (!plannedCloseDate && !plannedCloseTime && showDate && newTime) {
      const selected = venueId !== '' ? venues.find((v) => v.id === venueId) : undefined;
      if (selected?.default_close_hours_before_show != null) {
        applyVenueCloseDefault(showDate, newTime, selected.default_close_hours_before_show);
      }
    }
  };

  const handleVenueChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newId = e.target.value ? parseInt(e.target.value) : '';
    setVenueId(newId);
    if (newId !== '') {
      const selected = venues.find((v) => v.id === newId);
      setPromoterId(selected?.promoter_id ?? null);
      if (selected?.default_wheelchair_accessible !== null && selected?.default_wheelchair_accessible !== undefined) {
        setWheelchairAccessible(selected.default_wheelchair_accessible);
      }
      if (selected?.default_age_restriction) {
        setAgeRestriction(selected.default_age_restriction);
      }
      if (selected?.default_num_pass_pairs != null) {
        setNumPassPairs(selected.default_num_pass_pairs);
      }
      setLotteryEnabled(selected?.default_lottery_enabled ?? false);
      setLotteryWindowHours(String(selected?.default_lottery_window_hours ?? 24));
      setDjPreassignProhibitionDays(
        selected?.default_dj_preassign_prohibition_days != null
          ? String(selected.default_dj_preassign_prohibition_days)
          : ''
      );
      if (
        !plannedCloseDate &&
        !plannedCloseTime &&
        showDate &&
        showTime &&
        selected?.default_close_hours_before_show != null
      ) {
        applyVenueCloseDefault(showDate, showTime, selected.default_close_hours_before_show);
      }
    }
  };

  const addGenre = (value: string) => {
    const normalized = value.trim().toLowerCase();
    if (normalized && !genres.includes(normalized)) {
      setGenres((prev) => [...prev, normalized]);
    }
    setGenreInput('');
  };

  const removeGenre = (index: number) => {
    setGenres((prev) => prev.filter((_, i) => i !== index));
  };

  const handleGenreKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addGenre(genreInput);
    } else if (e.key === 'Backspace' && !genreInput && genres.length > 0) {
      setGenres((prev) => prev.slice(0, -1));
    }
  };

  const handleEventNameBlur = async () => {
    if (!eventName.trim() || genres.length > 0) return;
    setGenreLookupInProgress(true);
    try {
      const suggested = await showsAPI.suggestGenre(eventName.trim());
      if (suggested.length > 0 && genres.length === 0) {
        setGenres(suggested);
      }
    } catch {
      // silently ignore genre lookup failures
    } finally {
      setGenreLookupInProgress(false);
    }
  };

  const handleBandAdded = (artist: MusicBrainzArtist) => {
    if (!artist.tags || artist.tags.length === 0) return;
    setGenres((prev) => {
      const toAdd = artist.tags!.filter((tag) => !prev.includes(tag));
      return toAdd.length > 0 ? [...prev, ...toAdd] : prev;
    });
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!eventName.trim()) {
      newErrors.event_name = 'Event name is required';
    }

    if (venueId === '') {
      newErrors.venue_id = 'Venue is required';
    }

    if (!showDate) {
      newErrors.show_date = 'Show date is required';
    }

    if (!showStartDate && !showTime) {
      newErrors.show_time = 'Show time is required';
    }

    if (numPassPairs < 1 || numPassPairs > 5) {
      newErrors.num_pass_pairs = 'Number of pass pairs must be between 1 and 5';
    }

    if (autoClose && (!plannedCloseDate || !plannedCloseTime)) {
      newErrors.auto_close = 'Planned close date and time are required when auto-close is enabled';
    }

    if (plannedCloseDate && showDate) {
      const effectiveShowDate = isMultiDay && showStartDate ? showStartDate : showDate;
      const effectiveShowTime = isMultiDay ? '' : showTime;
      if (
        plannedCloseDate > effectiveShowDate ||
        (plannedCloseDate === effectiveShowDate &&
          (!effectiveShowTime ||
            (plannedCloseTime !== '' && plannedCloseTime >= effectiveShowTime)))
      ) {
        newErrors.planned_close_date = 'Planned close date/time must be before the show date/time';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async (publish: boolean) => {
    // Finalize any in-progress genre input before validating
    const finalGenres = genreInput.trim()
      ? [...new Set([...genres, genreInput.trim()])]
      : [...genres];
    if (genreInput.trim()) {
      setGenres(finalGenres);
      setGenreInput('');
    }

    setApiError(null);

    if (!validateForm()) {
      return;
    }

    setSubmitting(true);

    try {
      if (isEditing && id) {
        const updateData: ShowUpdate = {
          event_name: eventName.trim(),
          genre: finalGenres,
          venue_id: venueId as number,
          promoter_id: promoterId,
          show_date: showDate,
          show_time: showStartDate ? null : showTime,
          show_start_date: showStartDate || null,
          on_air_description: onAirDescription.trim() || null,
          caller_special_instructions: callerSpecialInstructions.trim() || null,
          age_restriction: ageRestriction,
          wheelchair_accessible: wheelchairAccessible,
          num_pass_pairs: numPassPairs,
          planned_close_date: plannedCloseDate || null,
          planned_close_time: plannedCloseTime || null,
          auto_close: autoClose,
          co_announce: coAnnounce,
          lottery_enabled: lotteryEnabled,
          lottery_window_hours: parseInt(lotteryWindowHours) || 24,
          dj_preassign_prohibition_days: djPreassignProhibitionDays.trim()
            ? parseInt(djPreassignProhibitionDays)
            : null,
          bands: bands.map(({ musicbrainz_id, band_name, start_pos, end_pos, artist_type, artist_country, artist_disambiguation, artist_tags }) => ({
            musicbrainz_id, band_name, start_pos, end_pos, artist_type, artist_country, artist_disambiguation, artist_tags,
          })),
        };
        const updatedShow = await showsAPI.update(parseInt(id), updateData);
        if (updatedShow.pass_adjustment &&
            (updatedShow.pass_adjustment.affected_djs.length > 0 ||
             updatedShow.pass_adjustment.affected_staff.length > 0)) {
          setPassAdjustment(updatedShow.pass_adjustment);
          return; // Stay on page until user dismisses the modal
        }
      } else {
        const createData: ShowCreate = {
          event_name: eventName.trim(),
          genre: finalGenres,
          venue_id: venueId as number,
          promoter_id: promoterId,
          show_date: showDate,
          show_time: showStartDate ? null : showTime,
          show_start_date: showStartDate || null,
          on_air_description: onAirDescription.trim() || null,
          caller_special_instructions: callerSpecialInstructions.trim() || null,
          age_restriction: ageRestriction,
          wheelchair_accessible: wheelchairAccessible,
          num_pass_pairs: numPassPairs,
          planned_close_date: plannedCloseDate || null,
          planned_close_time: plannedCloseTime || null,
          auto_close: autoClose,
          co_announce: coAnnounce,
          lottery_enabled: lotteryEnabled,
          lottery_window_hours: parseInt(lotteryWindowHours) || 24,
          dj_preassign_prohibition_days: djPreassignProhibitionDays.trim()
            ? parseInt(djPreassignProhibitionDays)
            : null,
          bands: bands.map(({ musicbrainz_id, band_name, start_pos, end_pos, artist_type, artist_country, artist_disambiguation, artist_tags }) => ({
            musicbrainz_id, band_name, start_pos, end_pos, artist_type, artist_country, artist_disambiguation, artist_tags,
          })),
        };
        const newShow = await showsAPI.create(createData);
        if (publish) {
          await showsAPI.publish(newShow.id);
        }
      }
      navigate('/promotions/shows');
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
        setApiError('Failed to save show');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!id) return;
    setShowDeleteConfirm(false);
    setSubmitting(true);
    setApiError(null);
    try {
      await showsAPI.delete(parseInt(id));
      navigate('/promotions/shows');
    } catch (err) {
      const error = err as APIError;
      setApiError(
        typeof error.detail === 'string' ? error.detail : 'Failed to delete show'
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="show-form-container">
      <div className="show-form-header">
        <h2>{isEditing ? 'Edit Show' : 'Create New Show'}</h2>
        <button
          onClick={() => navigate('/promotions/shows')}
          className="btn-secondary"
          disabled={submitting}
        >
          Cancel
        </button>
      </div>

      {apiError && <div className="error-message">{apiError}</div>}

      <form onSubmit={(e) => e.preventDefault()} className="show-form">
        <div className="form-group">
          <label htmlFor="event_name">
            Event Name <span className="required">*</span>
          </label>
          <p className="band-annotator-hint" style={{ margin: '0 0 0.35rem' }}>
            Type the show name here. Select any band or artist name to link it to a MusicBrainz record.
          </p>
          <BandAnnotator
            id="event_name"
            eventName={eventName}
            bands={bands}
            onEventNameChange={setEventName}
            onChange={setBands}
            onBandAdded={handleBandAdded}
            onBlur={handleEventNameBlur}
            hasError={!!errors.event_name}
            disabled={submitting}
          />
          {errors.event_name && (
            <span className="field-error">{errors.event_name}</span>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="genre-input">
            Genre
            {genreLookupInProgress && (
              <span style={{ marginLeft: '0.5rem', fontWeight: 'normal', color: '#666', fontSize: '0.85em' }}>
                looking up…
              </span>
            )}
          </label>
          <div className={`genre-tag-input${errors.genre ? ' input-error' : ''}`}>
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
              id="genre-input"
              list="genre-suggestions"
              value={genreInput}
              onChange={(e) => setGenreInput(e.target.value)}
              onKeyDown={handleGenreKeyDown}
              onBlur={() => { if (genreInput.trim()) addGenre(genreInput); }}
              placeholder={genres.length === 0 ? 'Type a genre and press Enter…' : ''}
              disabled={submitting}
              className="genre-text-input"
            />
            <datalist id="genre-suggestions">
              {knownGenres
                .filter((g) => !genres.includes(g))
                .map((g) => (
                  <option key={g} value={g} />
                ))}
            </datalist>
          </div>
          {errors.genre && <span className="field-error">{errors.genre}</span>}
        </div>

        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
            <label htmlFor="venue_id" style={{ margin: 0 }}>
              Venue <span className="required">*</span>
            </label>
            <div className="mine-toggle">
              <button
                type="button"
                className={showMineOnly ? 'btn-primary btn-small' : 'btn-secondary btn-small'}
                onClick={() => setShowMineOnly(true)}
                disabled={submitting}
              >
                My Venues
              </button>
              <button
                type="button"
                className={!showMineOnly ? 'btn-primary btn-small' : 'btn-secondary btn-small'}
                onClick={() => setShowMineOnly(false)}
                disabled={submitting}
              >
                All Venues
              </button>
            </div>
          </div>
          <select
            id="venue_id"
            value={venueId}
            onChange={handleVenueChange}
            className={errors.venue_id ? 'input-error' : ''}
            disabled={submitting}
          >
            <option value="">Select a venue...</option>
            {venues.map((venue) => (
              <option key={venue.id} value={venue.id}>
                {venue.name}
              </option>
            ))}
          </select>
          {errors.venue_id && (
            <span className="field-error">{errors.venue_id}</span>
          )}
        </div>

        {(() => {
          const selectedVenue = venueId !== '' ? venues.find((v) => v.id === venueId) : undefined;
          const showPromoterField =
            (selectedVenue?.shows_have_external_promoter ?? false) ||
            (isEditing && promoterId !== null);
          return showPromoterField && promotersList.length > 0 ? (
            <div className="form-group">
              <label htmlFor="promoter_id">Promoter</label>
              <select
                id="promoter_id"
                value={promoterId ?? ''}
                onChange={(e) => setPromoterId(e.target.value ? Number(e.target.value) : null)}
                disabled={submitting}
              >
                <option value="">
                  {venueId !== '' && venues.find((v) => v.id === venueId)?.promoter_id
                    ? `${venues.find((v) => v.id === venueId)?.promoter?.name ?? 'Venue default'} (venue default)`
                    : 'Venue is its own promoter'}
                </option>
                {promotersList.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <span className="field-hint">
                Which promoter handles winner notifications for this show.
              </span>
            </div>
          ) : null;
        })()}

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
                <label htmlFor="show_start_date">
                  Start Date <span className="required">*</span>
                </label>
                <input
                  type="date"
                  id="show_start_date"
                  value={showStartDate}
                  onChange={(e) => setShowStartDate(e.target.value)}
                  disabled={submitting}
                />
              </div>

              <div className="form-group">
                <label htmlFor="show_date">
                  End Date <span className="required">*</span>
                </label>
                <input
                  type="date"
                  id="show_date"
                  value={showDate}
                  onChange={(e) => setShowDate(e.target.value)}
                  className={errors.show_date ? 'input-error' : ''}
                  disabled={submitting}
                />
                {errors.show_date && (
                  <span className="field-error">{errors.show_date}</span>
                )}
              </div>
            </div>
          ) : (
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="show_date">
                  Show Date <span className="required">*</span>
                </label>
                <input
                  type="date"
                  id="show_date"
                  value={showDate}
                  onChange={(e) => handleShowDateChange(e.target.value)}
                  className={errors.show_date ? 'input-error' : ''}
                  disabled={submitting}
                />
                {errors.show_date && (
                  <span className="field-error">{errors.show_date}</span>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="show_time">
                  Show Time <span className="required">*</span>
                </label>
                <input
                  type="time"
                  id="show_time"
                  value={showTime}
                  onChange={(e) => handleShowTimeChange(e.target.value)}
                  className={errors.show_time ? 'input-error' : ''}
                  disabled={submitting}
                />
                {errors.show_time && (
                  <span className="field-error">{errors.show_time}</span>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="form-group">
          <div className="label-with-help">
            <label htmlFor="on_air_description">On-Air Description</label>
            <Tooltip text="Shown to DJs on the show detail page while they are on-air. Describe the show in a factual, value-neutral way. Supports Markdown formatting: headers, paragraphs, lists, blockquotes, bold/italic, and inline or block code. Links and images are not supported." />
          </div>
          <textarea
            id="on_air_description"
            value={onAirDescription}
            onChange={(e) => setOnAirDescription(e.target.value)}
            disabled={submitting}
            rows={3}
            placeholder="Optional on-air description of the show..."
          />
        </div>

        <div className="form-group">
          <div className="label-with-help">
            <label htmlFor="caller_special_instructions">Caller Special Instructions</label>
            <Tooltip text="Shown to DJs on the give away page when recording a winner — e.g. age requirements, ID at door, or venue parking info. Supports Markdown formatting: headers, paragraphs, lists, blockquotes, bold/italic, and inline or block code. Links and images are not supported." />
          </div>
          <textarea
            id="caller_special_instructions"
            value={callerSpecialInstructions}
            onChange={(e) => setCallerSpecialInstructions(e.target.value)}
            disabled={submitting}
            rows={3}
            placeholder="Optional instructions for DJs when recording the winner..."
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="age_restriction">
              Age Restriction <span className="required">*</span>
            </label>
            <select
              id="age_restriction"
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
            <div className="label-with-help">
              <label htmlFor="num_pass_pairs">
                Number of Pass Pairs <span className="required">*</span>
              </label>
              <Tooltip text="How many pass pairs to create for on-air giveaways. Each pair admits 2 people. Maximum 5 per show. An equal number of staff passes is also created." />
            </div>
            <input
              type="number"
              id="num_pass_pairs"
              value={numPassPairs}
              onChange={(e) => setNumPassPairs(parseInt(e.target.value) || 1)}
              min={1}
              max={5}
              className={errors.num_pass_pairs ? 'input-error' : ''}
              disabled={submitting}
            />
            {errors.num_pass_pairs && (
              <span className="field-error">{errors.num_pass_pairs}</span>
            )}
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

        <div className="form-group">
          <div style={{ fontWeight: 500, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
            Planned Close Date / Time (Pacific)
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="planned_close_date">Close Date</label>
              <input
                type="date"
                id="planned_close_date"
                value={plannedCloseDate}
                onChange={(e) => setPlannedCloseDate(e.target.value)}
                className={errors.auto_close || errors.planned_close_date ? 'input-error' : ''}
                disabled={submitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="planned_close_time">Close Time</label>
              <input
                type="time"
                id="planned_close_time"
                value={plannedCloseTime}
                onChange={(e) => setPlannedCloseTime(e.target.value)}
                className={errors.auto_close || errors.planned_close_date ? 'input-error' : ''}
                disabled={submitting}
              />
            </div>
          </div>
          <div className="form-group checkbox-group" style={{ marginTop: '0.25rem' }}>
            <label>
              <input
                type="checkbox"
                checked={autoClose}
                onChange={(e) => setAutoClose(e.target.checked)}
                disabled={submitting}
              />
              Automatically close show and email{' '}
              {promoterId !== null || (venueId !== '' && venues.find((v) => v.id === venueId)?.promoter_id != null)
                ? 'promoter'
                : 'venue'}{' '}
              owners at this time
            </label>
          </div>
          {errors.auto_close && (
            <span className="field-error">{errors.auto_close}</span>
          )}
          {errors.planned_close_date && (
            <span className="field-error">{errors.planned_close_date}</span>
          )}
        </div>

        <div style={{ borderTop: '1px solid var(--border-color)', marginTop: '0.5rem', paddingTop: '0.5rem' }}>
          <button
            type="button"
            onClick={() => setAdvancedOpen((o) => !o)}
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
            <span style={{ fontSize: '0.75em' }}>{advancedOpen ? '▼' : '▶'}</span>
            Advanced
          </button>

          {advancedOpen && (
            <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0' }}>
              <div className="form-group checkbox-group">
                <label>
                  <input
                    type="checkbox"
                    checked={lotteryEnabled}
                    onChange={(e) => setLotteryEnabled(e.target.checked)}
                    disabled={submitting}
                  />
                  Enable lottery for this show
                </label>
                <span className="field-hint">
                  During the lottery window, pass claims and DJ reservations are held as entries and
                  randomly drawn when the window closes.
                </span>
              </div>
              {lotteryEnabled && (
                <div className="form-group">
                  <label htmlFor="lotteryWindowHours">Lottery window (hours)</label>
                  <input
                    id="lotteryWindowHours"
                    type="number"
                    min="1"
                    max="168"
                    value={lotteryWindowHours}
                    onChange={(e) => setLotteryWindowHours(e.target.value)}
                    disabled={submitting}
                    style={{ width: '6rem' }}
                  />
                  <span className="field-hint">How many hours after publication the lottery window stays open (default: 24).</span>
                </div>
              )}

              <div className="form-group">
                <div className="label-with-help">
                  <label htmlFor="dj_preassign_prohibition_days">DJ Reservation Prohibition (days before close)</label>
                  <Tooltip text="Prevents DJs from reserving passes for shifts within this many days of the planned close date. If blank, there is no restriction." />
                </div>
                <input
                  type="number"
                  id="dj_preassign_prohibition_days"
                  value={djPreassignProhibitionDays}
                  onChange={(e) => setDjPreassignProhibitionDays(e.target.value)}
                  min={1}
                  disabled={submitting || !plannedCloseDate || !plannedCloseTime}
                  placeholder="e.g. 2"
                  style={{ width: '10rem' }}
                />
                <span className="field-hint" style={{ display: 'block', marginTop: '0.25rem' }}>
                  {(!plannedCloseDate || !plannedCloseTime)
                    ? 'Requires a planned close date and time to be set.'
                    : 'DJs cannot reserve passes for a shift date within this many days of the planned close date. Leave blank for no restriction.'}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="form-actions">
          {isEditing && (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="btn-danger"
              disabled={submitting}
            >
              Delete Show
            </button>
          )}
          <button
            type="button"
            onClick={() => navigate('/promotions/shows')}
            className="btn-secondary"
            disabled={submitting}
          >
            Cancel
          </button>
          {isEditing ? (
            <button
              type="button"
              className="btn-primary"
              disabled={submitting}
              onClick={() => handleSave(false)}
            >
              {submitting ? 'Saving...' : 'Update Show'}
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn-secondary"
                disabled={submitting}
                onClick={() => handleSave(false)}
              >
                {submitting ? 'Saving...' : 'Save Draft'}
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={submitting}
                onClick={() => handleSave(true)}
              >
                {submitting ? 'Publishing...' : 'Publish Show'}
              </button>
            </>
          )}
        </div>
      </form>

      {showDeleteConfirm && (
        <DeleteConfirmModal
          eventName={eventNameSnapshot}
          passes={showPasses}
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}

      {passAdjustment && (
        <PassAdjustmentModal
          eventName={eventName}
          adjustment={passAdjustment}
          onClose={() => {
            setPassAdjustment(null);
            navigate('/promotions/shows');
          }}
        />
      )}
    </div>
  );
};

export default ShowForm;
