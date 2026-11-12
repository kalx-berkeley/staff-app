/**
 * The DJ name typed into the DJ Name box, which the DJ pages remember in
 * localStorage, and the X-DJ-Name header that carries it to the backend.
 *
 * DJ studio guests aren't signed in, so the backend's log lines would only say
 * "not-logged-in". Every API request sends the remembered name instead, and the
 * backend shows it on log lines when nobody is signed in
 * (`backend/app/request_logging.py`). It's only a log label, never used for
 * access.
 *
 * @module djName
 */

import type { InternalAxiosRequestConfig } from 'axios';

/** The localStorage key holding the DJ Name box's last value. */
export const DJ_NAME_KEY = 'kalx_dj_name';

/**
 * Add the remembered DJ name to a request as the X-DJ-Name header.
 *
 * The name is URL-encoded because header values can't hold characters outside
 * Latin-1, which DJ names sometimes have.
 *
 * @param config - The outgoing axios request.
 * @returns The same request, with the header when a DJ name is remembered.
 */
export const addDjNameHeader = (
  config: InternalAxiosRequestConfig
): InternalAxiosRequestConfig => {
  let name = '';
  try {
    name = localStorage.getItem(DJ_NAME_KEY)?.trim() ?? '';
  } catch { /* localStorage unavailable — send no name */ }
  if (name) config.headers.set('X-DJ-Name', encodeURIComponent(name));
  return config;
};
