import type { ReactNode } from 'react';
import { useAuth } from '../contexts/authHooks';

export default function UnauthorizedPage() {
  const { user } = useAuth();

  return (
    <div style={{
      fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
      margin: 0,
      minHeight: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'flex-start',
      background: '#f0f2f5',
      color: '#222',
      padding: '3rem 1rem',
      boxSizing: 'border-box',
    }}>
      <div style={{
        background: '#fff',
        borderRadius: 10,
        boxShadow: '0 2px 12px rgba(0,0,0,0.13)',
        maxWidth: 620,
        width: '100%',
        padding: '2.25rem 2.5rem',
      }}>
        <h1 style={{ margin: '0 0 0.5rem', fontSize: '1.6rem', color: '#111' }}>
          KALX Staff Site — Access Not Available
        </h1>
        <p style={{ margin: '0 0 1.75rem', color: '#555', fontSize: '1rem', lineHeight: 1.55 }}>
          You're signed in as <strong>{user?.email}</strong>, but this Google
          account doesn't have access to the KALX staff website.
        </p>

        <Section color="#fff8e1" border="#ffe082" heading="Are you a KALX staff member using the wrong Google account?">
          <p>
            It's possible that you are a KALX staff member, but you're currently
            logged into Google with a different account than the one on file.
            KALX staff access this site using the same Google identity (email
            address) that they use for the{' '}
            <strong>KALX Announce mailing list</strong>.
          </p>
          <p style={{ marginTop: '0.75rem' }}>
            To find out which email address you use for KALX Announce, check
            your subscription to that mailing list — that's the Google identity
            you should be using to log into this site.
          </p>
          <p style={{ marginTop: '0.75rem' }}>
            You can also test whether you're signed into the correct Google
            account by visiting the{' '}
            <a
              href="https://groups.google.com/a/lists.berkeley.edu/g/kalxannounce/"
              target="_blank"
              rel="noreferrer"
            >
              KALX Announce Google Group
            </a>
            . If you can access that group, you are currently signed in with the
            correct Google account for the mailing list.
          </p>
          <p style={{ marginTop: '0.75rem' }}>
            If you <em>can</em> access the KALX Announce Google Group but still
            cannot access this staff website, there may be a technical issue:
            your email address in the Google Group may be different from the
            email address stored in Airtable. Please email the{' '}
            <strong>Operations Manager</strong> to let them know, so they can
            investigate the discrepancy.
          </p>
        </Section>

        <Section color="#e8f4fd" border="#90caf9" heading="How to switch which Google account you're signed into">
          <p>
            To sign into this site with a different Google account, you must
            first log out of the KALX Staff Site, then switch your Google
            account:
          </p>
          <ol style={{ margin: '0.5rem 0 0', paddingLeft: '1.4rem', lineHeight: 1.8 }}>
            <li>
              <a href={`https://${window.location.hostname.replace(/^staff\./, 'auth.')}/redirect_uri?logout=https://${window.location.hostname.replace(/^staff\./, 'auth.')}/`}>
                Log out of the KALX Staff Site
              </a>
              {' '}— this clears your current session and takes you to Google's
              account page
            </li>
            <li>
              Click your profile picture or initial in the top-right corner of
              the page
            </li>
            <li>
              Select <strong>Switch account</strong> or{' '}
              <strong>Add another account</strong> from the menu
            </li>
            <li>
              Sign in with the email address you use for the KALX Announce
              mailing list
            </li>
            <li>Navigate back to this site</li>
          </ol>
        </Section>

        <Section color="#f3e5f5" border="#ce93d8" heading="Not a KALX staff member?">
          <p>
            This is a private internal site for KALX 90.7 FM staff members. If
            you are not a staff member, you don't have access.
          </p>
        </Section>
      </div>
    </div>
  );
}

function Section({
  color,
  border,
  heading,
  children,
}: {
  color: string;
  border: string;
  heading: string;
  children: ReactNode;
}) {
  return (
    <div style={{
      background: color,
      border: `1px solid ${border}`,
      borderRadius: 7,
      padding: '1.1rem 1.3rem',
      marginBottom: '1.1rem',
      lineHeight: 1.55,
      fontSize: '0.92rem',
      color: '#444',
    }}>
      <strong style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.95rem', color: '#222' }}>
        {heading}
      </strong>
      {children}
    </div>
  );
}
