import { AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { afterEach, describe, expect, it } from 'vitest';
import { addDjNameHeader, DJ_NAME_KEY } from './djName';

const request = (): InternalAxiosRequestConfig => ({ headers: new AxiosHeaders() });

describe('addDjNameHeader', () => {
  afterEach(() => localStorage.clear());

  it('sends the remembered DJ name, URL-encoded', () => {
    localStorage.setItem(DJ_NAME_KEY, ' DJ Café ');
    expect(addDjNameHeader(request()).headers.get('X-DJ-Name')).toBe('DJ%20Caf%C3%A9');
  });

  it('sends no header without a DJ name', () => {
    localStorage.setItem(DJ_NAME_KEY, '  ');
    expect(addDjNameHeader(request()).headers.has('X-DJ-Name')).toBe(false);
  });
});
