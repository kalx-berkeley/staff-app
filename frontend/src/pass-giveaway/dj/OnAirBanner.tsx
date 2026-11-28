import { useEffect, useState } from 'react';
import { passesAPI } from '../api';
import type { OnAirIdentity } from '../types';
import { specialtyShowLabel } from '../utils';
import { pacificDateString } from '../../common/dateTime';
import { useOnAir } from './onAirContext';

/** "DJ Foo", or "Take Five (Specialty Music Show) with DJ Foo". */
export const IdentityName = ({ identity }: { identity: OnAirIdentity }) => {
  if (identity.kind === 'persona') return <strong>{identity.name}</strong>;
  return (
    <>
      <strong>{identity.name}</strong> ({specialtyShowLabel(identity.kind)})
      {identity.kind === 'music' && identity.persona_name && <> with {identity.persona_name}</>}
    </>
  );
};

/** The next slot's pass pairs pre-assigned for today, before switching to it. */
function useNextPreassignedCount(startsAt: string | null, enabled: boolean): number | null {
  const [count, setCount] = useState<number | null>(null);
  useEffect(() => {
    if (!enabled || !startsAt) {
      setCount(null);
      return;
    }
    let cancelled = false;
    const today = pacificDateString();
    passesAPI
      .getMyGiveaways(startsAt)
      .then((passes) => {
        if (cancelled) return;
        setCount(
          passes.filter((p) => p.status === 'available' && p.preassigned_date === today).length,
        );
      })
      .catch(() => !cancelled && setCount(null));
    return () => {
      cancelled = true;
    };
  }, [startsAt, enabled]);
  return count;
}

/**
 * Who is on air, at the top of every DJ page (decisions 19, 21 and 25):
 * the identity giveaways are credited to, a warning when it's no one, and in
 * the last 10 minutes of a slot an offer to switch to the next one.
 */
const OnAirBanner = () => {
  const { loaded, info, identity, switched, switchNow, switchBack } = useOnAir();
  const offerSwitch = !!info?.can_switch_early && !!info.next && !switched;
  const nextCount = useNextPreassignedCount(info?.next_starts_at ?? null, offerSwitch);

  if (!loaded) return null;

  return (
    <section className="dj-on-air" aria-label="On air">
      {identity ? (
        <>
          <div className="dj-on-air-name">
            On air: <IdentityName identity={identity} />
          </div>
          <p className="dj-on-air-hint">
            Giveaways and reservations are recorded for {identity.name}. If this isn&apos;t
            you, create your Spinitron playlist.
          </p>
        </>
      ) : info?.current_title ? (
        <div className="dj-on-air-warning" role="alert">
          Spinitron lists <strong>{info.current_title}</strong> with no DJ on air right now,
          so a giveaway will be recorded as unattributed and pre-assigned passes won&apos;t
          show. If you&apos;re live on air, create your Spinitron playlist.
        </div>
      ) : (
        <div className="dj-on-air-warning" role="alert">
          No DJ is on air in the Spinitron schedule right now, so a giveaway will be
          recorded as unattributed and pre-assigned passes won&apos;t show. If you&apos;re
          on air, create your Spinitron playlist.
        </div>
      )}

      {offerSwitch && info?.next && (
        <div className="dj-on-air-switch">
          <span>
            Up next: <IdentityName identity={info.next} />
          </span>
          <button type="button" className="btn-primary btn-small" onClick={switchNow}>
            I&apos;m {info.next.name}
            {nextCount !== null &&
              ` (${nextCount} pre-assigned pass${nextCount === 1 ? '' : 'es'})`}{' '}
            — switch now
          </button>
        </div>
      )}

      {switched && info?.next && (
        <div className="dj-on-air-switch">
          <span>Switched early to {info.next.name}.</span>
          <button type="button" className="dj-on-air-link" onClick={switchBack}>
            Switch back to {info.current?.name ?? 'the current slot'}
          </button>
        </div>
      )}
    </section>
  );
};

export default OnAirBanner;
