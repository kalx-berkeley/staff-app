/** Test helpers for DJ pages, which read who is on air from `OnAirContext`. */

import type { ReactNode } from 'react';
import type { OnAirIdentity } from '../types';
import { OnAirContext, identityKey, type OnAirState } from './onAirContext';

/** A persona identity, as the server returns it. */
export const persona = (personaId: number, name: string): OnAirIdentity => ({
  kind: 'persona',
  name,
  persona_id: personaId,
  persona_name: name,
  specialty_show_id: null,
});

/** A Specialty Music Show (with its DJ) or Talk & Info Show identity. */
export const showIdentity = (
  kind: 'music' | 'talk',
  showId: number,
  name: string,
  dj?: { personaId: number; name: string },
): OnAirIdentity => ({
  kind,
  name,
  persona_id: dj?.personaId ?? null,
  persona_name: dj?.name ?? null,
  specialty_show_id: showId,
});

/** Render *ui* with *identity* on air (null for no one). */
export const withOnAir = (
  ui: ReactNode,
  identity: OnAirIdentity | null,
  state: Partial<OnAirState> = {},
) => (
  <OnAirContext.Provider
    value={{
      loaded: true,
      info: null,
      identity,
      identityKey: identityKey(identity),
      switched: false,
      switchNow: () => {},
      switchBack: () => {},
      ...state,
    }}
  >
    {ui}
  </OnAirContext.Provider>
);
