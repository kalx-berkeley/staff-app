import { useEffect, useId, useState } from 'react';
import type { FormEvent } from 'react';
import { directoryAPI } from './api';
import DjPersonaEditor from './DjPersonaEditor';
import StaffPhoto from './StaffPhoto';
import { errorMessage } from '../common/utils';
import type { DjPersona, Profile } from './types';

// Where staff ask for changes while the app can't write to Airtable yet.
export const EDIT_REQUEST_FORM_URL =
  'https://docs.google.com/forms/d/e/1FAIpQLSf7IIE8IrSPqODgGCLB1MZvFe2OlyCxfCHRYbSS5cGVs_QfQg/viewform';

const PHOTO_TYPES = ['image/jpeg', 'image/png'];
const MAX_PHOTO_BYTES = 5 * 1024 * 1024;

interface ProfileEditFormProps {
  profile: Profile;
  onSaved: (profile: Profile) => void;
}

interface Values {
  firstName: string;
  surname: string;
  pronouns: string;
  phone: string;
  personas: DjPersona[];
}

const initialValues = (profile: Profile): Values => ({
  firstName: profile.first_name ?? '',
  surname: profile.surname ?? '',
  pronouns: profile.entry.pronouns ?? '',
  phone: profile.entry.phone ?? '',
  personas: profile.entry.dj_personas,
});

const blankToNull = (value: string): string | null => value.trim() || null;

// The fields staff can change about themselves (and site admins about
// anyone). The whole form is greyed out until the app can write to Airtable
// (profile.can_edit), with a link to ask for changes another way.
const ProfileEditForm = ({ profile, onSaved }: ProfileEditFormProps) => {
  const idPrefix = useId();
  const [values, setValues] = useState<Values>(() => initialValues(profile));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: 'error' | 'success'; text: string } | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const disabled = !profile.can_edit;

  useEffect(() => {
    if (!photo) return;
    const url = URL.createObjectURL(photo);
    setPhotoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  const set = <K extends keyof Values>(key: K, value: Values[K]) =>
    setValues((current) => ({ ...current, [key]: value }));

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!values.firstName.trim()) {
      setMessage({ kind: 'error', text: 'First name is required' });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const saved = await directoryAPI.updateProfile(profile.entry.id, {
        first_name: values.firstName.trim(),
        surname: blankToNull(values.surname),
        pronouns: blankToNull(values.pronouns),
        phone: blankToNull(values.phone),
        dj_persona_ids: values.personas.map((p) => p.id),
      });
      setValues(initialValues(saved));
      setMessage({ kind: 'success', text: 'Saved' });
      onSaved(saved);
    } catch (err) {
      setMessage({ kind: 'error', text: errorMessage(err) });
    } finally {
      setSaving(false);
    }
  };

  const choosePhoto = (file: File | undefined) => {
    setPhotoError(null);
    if (!file) return;
    if (!PHOTO_TYPES.includes(file.type)) {
      setPhotoError('The photo must be a JPEG or PNG');
    } else if (file.size > MAX_PHOTO_BYTES) {
      setPhotoError('The photo must be 5 MB or smaller');
    } else {
      setPhoto(file);
    }
  };

  const uploadPhoto = async () => {
    if (!photo) return;
    setSaving(true);
    setPhotoError(null);
    try {
      const saved = await directoryAPI.uploadPhoto(profile.entry.id, photo);
      setPhoto(null);
      setPhotoPreview(null);
      onSaved(saved);
    } catch (err) {
      setPhotoError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const field = (name: string) => `${idPrefix}-${name}`;

  return (
    <form className="profile-edit" onSubmit={handleSubmit}>
      {disabled && (
        <p className="info-message">
          Editing isn't available here yet. To update these details, fill out{' '}
          <a href={EDIT_REQUEST_FORM_URL} target="_blank" rel="noreferrer">
            this form
          </a>
          .
        </p>
      )}
      <fieldset disabled={disabled || saving}>
        <legend className="visually-hidden">Your details</legend>
        <div className="profile-edit-grid">
          <div className="form-group">
            <label htmlFor={field('first')}>First name</label>
            <input
              id={field('first')}
              value={values.firstName}
              maxLength={100}
              required
              onChange={(e) => set('firstName', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label htmlFor={field('surname')}>Surname</label>
            <input
              id={field('surname')}
              value={values.surname}
              maxLength={100}
              onChange={(e) => set('surname', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label htmlFor={field('pronouns')}>Pronouns</label>
            <input
              id={field('pronouns')}
              value={values.pronouns}
              maxLength={40}
              placeholder="e.g. they/them"
              onChange={(e) => set('pronouns', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label htmlFor={field('phone')}>Phone</label>
            <input
              id={field('phone')}
              type="tel"
              value={values.phone}
              maxLength={40}
              placeholder="(510) 555-0100"
              onChange={(e) => set('phone', e.target.value)}
            />
          </div>
        </div>
        <div className="form-group">
          <span className="profile-edit-label">DJ name</span>
          <DjPersonaEditor
            personas={values.personas}
            onChange={(personas) => set('personas', personas)}
            disabled={disabled || saving}
          />
        </div>
        <div className="profile-edit-actions">
          <button type="submit" className="btn-primary">
            {saving ? 'Saving…' : 'Save changes'}
          </button>
          {message && (
            <span
              className={message.kind === 'error' ? 'field-warning' : 'profile-edit-saved'}
              role="status"
            >
              {message.text}
            </span>
          )}
        </div>

        <div className="form-group profile-photo-field">
          <label htmlFor={field('photo')}>Photo</label>
          <div className="profile-photo-row">
            {photoPreview ? (
              <img className="staff-photo staff-photo-medium" src={photoPreview} alt="New photo" />
            ) : (
              <StaffPhoto entry={profile.entry} size="medium" />
            )}
            <div>
              <input
                id={field('photo')}
                type="file"
                accept={PHOTO_TYPES.join(',')}
                onChange={(e) => choosePhoto(e.target.files?.[0])}
              />
              <p className="field-hint">A JPEG or PNG, up to 5 MB. It replaces your current photo.</p>
              <button
                type="button"
                className="btn-secondary btn-small"
                onClick={uploadPhoto}
                disabled={!photo}
              >
                Upload photo
              </button>
              {photoError && <p className="field-warning">{photoError}</p>}
            </div>
          </div>
        </div>
      </fieldset>
    </form>
  );
};

export default ProfileEditForm;
