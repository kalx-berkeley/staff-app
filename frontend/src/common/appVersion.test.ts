import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { reloadAfterChunkLoadError } from './appVersion';

describe('reloadAfterChunkLoadError', () => {
  const reload = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('location', { ...window.location, reload });
    reload.mockClear();
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('reloads, but not again straight after, so a lasting failure cannot loop', () => {
    reloadAfterChunkLoadError();
    expect(reload).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(30 * 1000);
    reloadAfterChunkLoadError();
    expect(reload).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(31 * 1000);
    reloadAfterChunkLoadError();
    expect(reload).toHaveBeenCalledTimes(2);
  });
});
