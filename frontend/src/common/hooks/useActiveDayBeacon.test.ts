import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import apiClient from '../api';
import type { UserResponse } from '../types';
import { useActiveDayBeacon } from './useActiveDayBeacon';

vi.mock('../api', () => ({ default: { post: vi.fn(() => Promise.resolve({})) } }));

const staff: UserResponse = {
  email: 'staff@example.com',
  role: 'staff',
  is_dj_network: false,
  is_station_office_network: false,
};

describe('useActiveDayBeacon', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('reports each sub-site once a day', () => {
    renderHook(() => useActiveDayBeacon(staff, 'directory'));
    renderHook(() => useActiveDayBeacon(staff, 'directory'));
    renderHook(() => useActiveDayBeacon(staff, 'workforms'));
    expect(apiClient.post).toHaveBeenCalledTimes(2);
    expect(apiClient.post).toHaveBeenCalledWith('/analytics/beacon', { subsite: 'directory' });
  });

  it('skips guests, the unauthorized and impersonation', () => {
    renderHook(() => useActiveDayBeacon(null, 'home'));
    renderHook(() => useActiveDayBeacon({ ...staff, email: null, role: 'dj' }, 'home'));
    renderHook(() => useActiveDayBeacon({ ...staff, role: 'unauthorized' }, 'home'));
    renderHook(() =>
      useActiveDayBeacon({ ...staff, impersonating_email: 'x@example.com' }, 'home'),
    );
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
