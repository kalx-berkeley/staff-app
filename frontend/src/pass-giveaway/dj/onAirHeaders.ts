/**
 * What the DJ pages tell the backend about who is on air, on every request.
 *
 * - `X-DJ-Name`: the on-air identity's name. DJ studio guests aren't signed
 *   in, so the backend's log lines would only say "not-logged-in"; it shows
 *   this name instead (`backend/app/request_logging.py`). It's only a log
 *   label, never used for access or credit.
 * - `X-DJ-Switch-To`: after "switch now", the start of the next slot. The
 *   server decides who gets credit, and honours this only in the last 10
 *   minutes before that slot starts (`on_air_identity.dj_identity`). The DJ
 *   studio has one computer, so the switch is kept in localStorage and every
 *   tab sends it until the slot starts.
 *
 * @module onAirHeaders
 */

import type { InternalAxiosRequestConfig } from 'axios';

export const SWITCH_HEADER = 'X-DJ-Switch-To';
const SWITCH_KEY = 'kalx_dj_switch_to';
const NAME_KEY = 'kalx_dj_on_air_name';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch { /* localStorage unavailable: the switch lasts only this request */ }
}

/**
 * The start (ISO) of the slot the DJ switched to early, while it's still in
 * the future. Once that slot has started, the switch has done its job and is
 * forgotten.
 */
export function savedSwitch(now: number = Date.now()): string | null {
  const value = read(SWITCH_KEY);
  if (!value) return null;
  const start = Date.parse(value);
  if (Number.isNaN(start) || start <= now) {
    write(SWITCH_KEY, null);
    return null;
  }
  return value;
}

/** Remember an early switch to the slot starting at *startsAt*, or forget it (null). */
export function saveSwitch(startsAt: string | null): void {
  write(SWITCH_KEY, startsAt);
}

/** Remember the on-air identity's name for the X-DJ-Name log label (null for no one). */
export function saveOnAirName(name: string | null): void {
  write(NAME_KEY, name?.trim() || null);
}

/**
 * Add the on-air name and any early switch to a request.
 *
 * The name is URL-encoded because header values can't hold characters
 * outside Latin-1, which DJ names sometimes have.
 */
export const addOnAirHeaders = (
  config: InternalAxiosRequestConfig
): InternalAxiosRequestConfig => {
  const name = read(NAME_KEY)?.trim();
  if (name) config.headers.set('X-DJ-Name', encodeURIComponent(name));
  const switchTo = savedSwitch();
  if (switchTo && !config.headers.has(SWITCH_HEADER)) config.headers.set(SWITCH_HEADER, switchTo);
  return config;
};
