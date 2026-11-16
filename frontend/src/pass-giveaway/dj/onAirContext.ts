/**
 * Who is on air, for every DJ page (decisions 18–27 of
 * docs/pass-giveaway/specs/spinitron-identity/plan.md).
 *
 * The server works out who is on air from the Spinitron schedule and recent
 * spins, and credits giveaways to them. OnAirProvider polls GET /api/dj/on-air, looks
 * again at each changeover, and keeps the early switch: in the last 10
 * minutes of a slot the DJ can switch to the next one, which lasts until it
 * starts (see onAirHeaders.ts).
 */

import { createContext, useContext } from 'react';
import type { OnAirIdentity, OnAirInfo } from '../types';

export interface OnAirState {
  /** Whether the first answer has come back. */
  loaded: boolean;
  info: OnAirInfo | null;
  /** Who the DJ pages credit: the next slot's identity after an early switch. */
  identity: OnAirIdentity | null;
  /** Changes whenever `identity` does, for refetching what depends on it. */
  identityKey: string;
  /** Whether the DJ switched early to the next slot. */
  switched: boolean;
  /** Switch to the next slot now (only while `info.can_switch_early`). */
  switchNow: () => void;
  /** Undo an early switch. */
  switchBack: () => void;
}

/** A key for *identity*: the same exactly when the server would credit the same. */
export function identityKey(identity: OnAirIdentity | null): string {
  return identity ? `${identity.persona_id ?? ''}|${identity.specialty_show_id ?? ''}` : 'none';
}

const NO_ONE: OnAirState = {
  loaded: false,
  info: null,
  identity: null,
  identityKey: identityKey(null),
  switched: false,
  switchNow: () => {},
  switchBack: () => {},
};

export const OnAirContext = createContext<OnAirState>(NO_ONE);

/** Who is on air, from the nearest `OnAirProvider` (DJLayout). */
export const useOnAir = (): OnAirState => useContext(OnAirContext);
