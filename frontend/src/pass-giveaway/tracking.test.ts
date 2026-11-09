import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import apiClient from '../common/api';
import {
  SESSION_IDLE_MS,
  VISIT_RELOAD_MS,
  giveawayVisitId,
  isNetworkGuest,
  useGiveawayVisit,
  useGuestSession,
} from './tracking';

vi.mock('../common/api', () => ({
  default: { post: vi.fn(() => Promise.resolve({})), put: vi.fn(() => Promise.resolve({})) },
}));

describe('pass giveaway tracking', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('records a giveaway page visit and later DJ name changes', () => {
    const { result, rerender } = renderHook(
      ({ name }) => useGiveawayVisit(7, name, true),
      { initialProps: { name: 'DJ Marmot' } },
    );
    const visitId = result.current!;
    expect(visitId).toBeTruthy();
    expect(apiClient.post).toHaveBeenCalledWith('/pass-giveaway/analytics/giveaway-visits', {
      visit_id: visitId,
      show_id: 7,
      dj_name: 'DJ Marmot',
    });

    rerender({ name: 'DJ Marm' });
    rerender({ name: 'DJ Otter' });
    expect(apiClient.put).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(1600);
    });
    expect(apiClient.put).toHaveBeenCalledTimes(1);
    expect(apiClient.put).toHaveBeenCalledWith(
      `/pass-giveaway/analytics/giveaway-visits/${visitId}/dj`,
      { dj_name: 'DJ Otter' },
    );
    expect(result.current).toBe(visitId);
  });

  it("doesn't record a promotions preview", () => {
    const { result } = renderHook(() => useGiveawayVisit(7, 'DJ', false));
    expect(result.current).toBeNull();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('continues a visit after a quick reload of the same show only', () => {
    const first = giveawayVisitId(7);
    expect(giveawayVisitId(7)).toBe(first);
    expect(giveawayVisitId(8)).not.toBe(first);
    const second = giveawayVisitId(8);
    vi.advanceTimersByTime(VISIT_RELOAD_MS + 1);
    expect(giveawayVisitId(8)).not.toBe(second);
  });

  it('counts one guest session per tab until 30 minutes idle', () => {
    renderHook(() => useGuestSession(true));
    renderHook(() => useGuestSession(true));
    expect(apiClient.post).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(SESSION_IDLE_MS + 1000);
    act(() => {
      window.dispatchEvent(new Event('pointerdown'));
    });
    expect(apiClient.post).toHaveBeenCalledTimes(2);
    const [, first] = vi.mocked(apiClient.post).mock.calls[0];
    const [, second] = vi.mocked(apiClient.post).mock.calls[1];
    expect(first).not.toEqual(second);
  });

  it('tells network guests from signed-in users', () => {
    const base = { role: 'dj' as const, is_dj_network: true, is_station_office_network: false };
    expect(isNetworkGuest({ ...base, email: null })).toBe(true);
    expect(isNetworkGuest({ ...base, email: 'a@example.com' })).toBe(false);
    expect(isNetworkGuest({ ...base, email: null, is_dj_network: false })).toBe(false);
    expect(isNetworkGuest(null)).toBe(false);
  });
});
