import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { usePageTitle } from '../common/hooks/usePageTitle';
import ImpersonationNotice from '../common/components/ImpersonationNotice';
import MarkdownContent from '../common/components/MarkdownContent';
import { errorMessage, formatLeave } from '../common/utils';
import { directoryAPI } from './api';
import { DIRECTORY_TITLE } from './DirectoryPage';
import DjNames from './DjNames';
import EligibilityChecklist from './EligibilityChecklist';
import NewStaffBadge from './NewStaffBadge';
import ProfileEditForm from './ProfileEditForm';
import StaffPhoto from './StaffPhoto';
import WorkformsSummary from './WorkformsSummary';
import type { Profile } from './types';

// A staff member's profile: more than the directory shows everyone, their
// editable details, the Sublist DJ requirements and their recent workforms.
// At /me for your own; site admins can open anyone's at /:staffId/profile.
export default function ProfilePage() {
  const { staffId } = useParams();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setProfile(null);
    setLoadError(null);
    directoryAPI
      .getProfile(staffId ? Number(staffId) : 'me')
      .then((loaded) => {
        if (!cancelled) setProfile(loaded);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [staffId]);

  const heading = !profile
    ? 'Profile'
    : profile.is_self
      ? 'My profile'
      : `${profile.entry.name}’s profile`;
  usePageTitle(profile ? heading : null, DIRECTORY_TITLE);

  const entry = profile?.entry;
  const otherStaffId = profile && !profile.is_self ? profile.entry.id : null;

  return (
    <div className="directory-page profile-page">
      <header className="directory-header">
        <nav className="directory-subsites" aria-label="Staff sites">
          <Link to="/">← {DIRECTORY_TITLE}</Link>
        </nav>
        <div className="directory-title-row">
          <h1>{heading}</h1>
        </div>
        <ImpersonationNotice />
      </header>

      {loadError ? (
        <div className="error-message">{loadError}</div>
      ) : !profile || !entry ? (
        <p>Loading…</p>
      ) : (
        <>
          <section className="profile-section" aria-labelledby="profile-details">
            <div className="directory-detail-heading">
              <StaffPhoto entry={entry} size="medium" />
              <div>
                <h2 id="profile-details">
                  {entry.name}
                  <NewStaffBadge entry={entry} />
                </h2>
                {entry.pronouns && <div className="directory-pronouns">{entry.pronouns}</div>}
              </div>
            </div>
            <dl className="directory-detail-fields">
              <dt>Email</dt>
              <dd>{entry.email}</dd>

              <dt>Phone</dt>
              <dd>{entry.phone || '—'}</dd>

              <dt>DJ name</dt>
              <dd>{entry.dj_name ? <DjNames entry={entry} /> : '—'}</dd>

              <dt>Departments</dt>
              <dd>{entry.departments.length > 0 ? entry.departments.join(', ') : '—'}</dd>

              <dt>Status</dt>
              <dd>{entry.statuses.join(', ')}</dd>

              <dt>Titles and roles</dt>
              <dd>
                {entry.titles_and_roles ? (
                  <MarkdownContent className="directory-titles" content={entry.titles_and_roles} />
                ) : (
                  '—'
                )}
              </dd>

              <dt>Leave of absence</dt>
              <dd>{formatLeave(profile) || '—'}</dd>

              <dt>DJ Quiz</dt>
              <dd>{entry.dj_quiz_years.length > 0 ? entry.dj_quiz_years.join(', ') : '—'}</dd>
            </dl>
          </section>

          <section className="profile-section" aria-labelledby="profile-edit">
            <h2 id="profile-edit">Edit {profile.is_self ? 'your' : 'their'} details</h2>
            <ProfileEditForm key={entry.id} profile={profile} onSaved={setProfile} />
          </section>

          {profile.eligibility && (
            <section className="profile-section" aria-labelledby="profile-eligibility">
              <h2 id="profile-eligibility">Subbing DJ shifts</h2>
              <EligibilityChecklist eligibility={profile.eligibility} otherStaffId={otherStaffId} />
            </section>
          )}

          {profile.workforms && (
            <section className="profile-section" aria-labelledby="profile-workforms">
              <h2 id="profile-workforms">Workforms</h2>
              <WorkformsSummary months={profile.workforms} otherStaffId={otherStaffId} />
            </section>
          )}
        </>
      )}
    </div>
  );
}
