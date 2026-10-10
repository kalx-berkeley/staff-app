import type { ReactNode } from 'react';
import { useAuth } from '../contexts/authHooks';
import { usePageTitle } from '../hooks/usePageTitle';

const SIGN_IN_HELP_URL =
  'https://docs.google.com/document/d/1RwVZaJwv-Z46pMYJhkNfvQjnZe6kSWw8vJz8MVZdW8g/edit';

export default function UnauthorizedPage() {
  usePageTitle('Access Not Available');
  const { user } = useAuth();
  const authHost = window.location.hostname.replace(/^staff\./, 'auth.');
  const logoutUrl = `https://${authHost}/redirect_uri?logout=https://${authHost}/`;

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
        maxWidth: 560,
        width: '100%',
        padding: '2.25rem 2.5rem',
        boxSizing: 'border-box',
      }}>
        <h1 style={{ margin: '0 0 0.5rem', fontSize: '1.5rem', color: '#111' }}>
          This Google account can't access the KALX Staff Site
        </h1>
        <p style={{ margin: '0 0 1.75rem', color: '#555', fontSize: '1rem', lineHeight: 1.55 }}>
          You're signed in as <strong style={{ wordBreak: 'break-all' }}>{user?.email}</strong>.
        </p>

        <Section color="#f5f5f5" border="#ddd" heading="Not KALX staff?">
          <p style={{ margin: 0 }}>
            This site is only for KALX 90.7 FM staff. There's nothing more you
            need to do.
          </p>
        </Section>

        <Section color="#fff8e1" border="#ffe082" heading="KALX staff? You're probably signed in with the wrong Google account.">
          <ol style={{ margin: 0, paddingLeft: '1.4rem', lineHeight: 1.6 }}>
            <Step>
              <strong>Find your KALX email address.</strong> It's the address
              your <strong>KALX Announce</strong> emails are delivered to.
            </Step>
            <Step>
              <a href={logoutUrl} style={{
                display: 'inline-block',
                background: '#1a73e8',
                color: '#fff',
                padding: '0.35rem 0.9rem',
                borderRadius: 5,
                textDecoration: 'none',
                fontWeight: 600,
              }}>
                Log out
              </a>
            </Step>
            <Step>
              <strong>Sign in to Google with that address.</strong> When Google
              asks you to choose an account, pick it (or choose "Use another
              account" to add it).
            </Step>
          </ol>
          <p style={{ margin: '1rem 0 0' }}>
            Need help signing in, or don't have a Google account for that
            address yet?{' '}
            <a href={SIGN_IN_HELP_URL} target="_blank" rel="noreferrer">
              Read the sign-in guide
            </a>
            .
          </p>
        </Section>

        <p style={{ margin: '1.25rem 0 0', fontSize: '0.85rem', color: '#666', lineHeight: 1.5 }}>
          Still blocked after signing in with your KALX Announce address? Email
          the Operations Manager so they can check your staff record.
        </p>
      </div>
    </div>
  );
}

function Step({ children }: { children: ReactNode }) {
  return <li style={{ marginBottom: '0.6rem' }}>{children}</li>;
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
      fontSize: '0.95rem',
      color: '#333',
    }}>
      <strong style={{ display: 'block', marginBottom: '0.6rem', fontSize: '1rem', color: '#111' }}>
        {heading}
      </strong>
      {children}
    </div>
  );
}
