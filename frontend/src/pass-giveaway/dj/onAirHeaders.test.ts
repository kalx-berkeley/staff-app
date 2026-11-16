import { afterEach, describe, expect, it } from 'vitest';
import { AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { SWITCH_HEADER, addOnAirHeaders, saveOnAirName, saveSwitch, savedSwitch } from './onAirHeaders';

const request = () => ({ headers: new AxiosHeaders() }) as InternalAxiosRequestConfig;
const inMinutes = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString();

describe('addOnAirHeaders', () => {
  afterEach(() => localStorage.clear());

  it("names the on-air identity for the backend's log lines, URL-encoded", () => {
    saveOnAirName(' DJ Café ');
    expect(addOnAirHeaders(request()).headers.get('X-DJ-Name')).toBe('DJ%20Caf%C3%A9');
    saveOnAirName(null);
    expect(addOnAirHeaders(request()).headers.has('X-DJ-Name')).toBe(false);
  });

  it('sends an early switch until its slot starts', () => {
    const next = inMinutes(5);
    saveSwitch(next);
    expect(addOnAirHeaders(request()).headers.get(SWITCH_HEADER)).toBe(next);

    saveSwitch(inMinutes(-1));
    expect(addOnAirHeaders(request()).headers.has(SWITCH_HEADER)).toBe(false);
    // Forgotten once the slot has started
    expect(savedSwitch()).toBeNull();
  });

  it("leaves a request's own switch header alone", () => {
    saveSwitch(inMinutes(5));
    const config = request();
    config.headers.set(SWITCH_HEADER, 'asked-for');
    expect(addOnAirHeaders(config).headers.get(SWITCH_HEADER)).toBe('asked-for');
  });
});
