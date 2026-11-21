import { useEffect, useState } from 'react';
import { showsAPI } from './api';
import type { AgeCheck } from './types';

/**
 * The upcoming 21+ shows the signed-in staff member is, or might be, too
 * young for, by show ID (`showsAPI.getMyAgeChecks`). Empty until it loads, if
 * it fails, or when *enabled* is false (e.g. no staff profile).
 */
export function useMyAgeChecks(enabled: boolean): Record<number, AgeCheck> {
  const [checks, setChecks] = useState<Record<number, AgeCheck>>({});
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    showsAPI
      .getMyAgeChecks()
      .then((result) => {
        // Most staff have none; leaving the initial {} skips a re-render
        if (!cancelled && Object.keys(result).length > 0) setChecks(result);
      })
      .catch(() => {
        // Non-fatal: the server still refuses passes to staff under 21
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);
  return checks;
}
