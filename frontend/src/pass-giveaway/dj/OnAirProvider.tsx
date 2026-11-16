/** Provides who is on air to the DJ pages (see onAirContext.ts). */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { onAirAPI } from '../api';
import type { OnAirInfo } from '../types';
import { OnAirContext, identityKey, type OnAirState } from './onAirContext';
import { saveOnAirName, saveSwitch, savedSwitch } from './onAirHeaders';

/** How often to ask who is on air, in milliseconds. */
const POLL_MS = 30_000;

const sameInstant = (a: string | null, b: string | null) =>
  !!a && !!b && Date.parse(a) === Date.parse(b);

const OnAirProvider = ({ children }: { children: ReactNode }) => {
  const [info, setInfo] = useState<OnAirInfo | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [switchTo, setSwitchTo] = useState<string | null>(() => savedSwitch());
  const changeoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(() => {
    onAirAPI
      .getCurrent()
      .then((next) => {
        setInfo(next);
        setLoaded(true);
        // A switch is forgotten once its slot has started
        setSwitchTo(savedSwitch());
      })
      .catch(() => setLoaded(true));
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  // Look again right after the current slot ends and when the next starts
  useEffect(() => {
    if (changeoverTimer.current) clearTimeout(changeoverTimer.current);
    const times = [info?.current_ends_at, info?.next_starts_at]
      .map((t) => (t ? Date.parse(t) - Date.now() : NaN))
      .filter((ms) => ms > 0);
    if (times.length) changeoverTimer.current = setTimeout(refresh, Math.min(...times) + 1000);
    return () => {
      if (changeoverTimer.current) clearTimeout(changeoverTimer.current);
    };
  }, [info, refresh]);

  const switched = !!info?.next && sameInstant(switchTo, info.next_starts_at);
  const identity = (switched ? info?.next : info?.current) ?? null;
  const key = identityKey(identity);

  useEffect(() => {
    saveOnAirName(identity?.name ?? null);
    // The name only changes with the identity
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const value = useMemo<OnAirState>(
    () => ({
      loaded,
      info,
      identity,
      identityKey: key,
      switched,
      switchNow: () => {
        if (!info?.next_starts_at || !info.can_switch_early) return;
        saveSwitch(info.next_starts_at);
        setSwitchTo(info.next_starts_at);
      },
      switchBack: () => {
        saveSwitch(null);
        setSwitchTo(null);
      },
    }),
    // identity follows key
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [loaded, info, key, switched],
  );

  return <OnAirContext.Provider value={value}>{children}</OnAirContext.Provider>;
};

export default OnAirProvider;
