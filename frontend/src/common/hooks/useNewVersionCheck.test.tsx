import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import NewVersionBanner from '../components/NewVersionBanner';
import {
  CHECK_INTERVAL_MS,
  IDLE_BEFORE_RELOAD_AFTER_TYPING_MS,
  IDLE_BEFORE_RELOAD_MS,
} from './useNewVersionCheck';

const reload = vi.fn();

const deployVersion = (version: string | null) => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ version }), { status: 200 })),
  );
};

const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

const findNewVersion = async () => {
  render(<NewVersionBanner />);
  await advance(CHECK_INTERVAL_MS);
  expect(screen.getByRole('status')).toHaveTextContent('new version');
};

describe('NewVersionBanner', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubEnv('VITE_RELEASE_VERSION', 'v1');
    vi.stubEnv('VITE_COMMIT_SHA', '');
    vi.stubGlobal('location', { ...window.location, pathname: '/shows', reload });
    reload.mockClear();
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('stays quiet while the deployed version matches', async () => {
    deployVersion('v1');
    render(<NewVersionBanner />);

    await advance(IDLE_BEFORE_RELOAD_MS * 2);

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(reload).not.toHaveBeenCalled();
  });

  it('does not check at all in a build with no version', async () => {
    vi.stubEnv('VITE_RELEASE_VERSION', '');
    deployVersion('v2');
    render(<NewVersionBanner />);

    await advance(CHECK_INTERVAL_MS * 2);

    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    ['a failed request', async () => new Response('', { status: 503 })],
    ['a network error', async () => { throw new TypeError('offline'); }],
    ['a backend with no version set', async () => new Response('{"version":null}')],
  ])('ignores %s', async (_name, respond) => {
    vi.stubGlobal('fetch', vi.fn(respond));
    render(<NewVersionBanner />);

    await advance(IDLE_BEFORE_RELOAD_MS * 2);

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(reload).not.toHaveBeenCalled();
  });

  it('reloads an idle tab after a deploy', async () => {
    deployVersion('v2');
    await findNewVersion();
    expect(reload).not.toHaveBeenCalled();

    await advance(IDLE_BEFORE_RELOAD_MS);

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('waits while the user is active', async () => {
    deployVersion('v2');
    await findNewVersion();

    await advance(IDLE_BEFORE_RELOAD_MS - CHECK_INTERVAL_MS - 2000);
    fireEvent.pointerDown(window);
    await advance(CHECK_INTERVAL_MS + 3000);

    expect(reload).not.toHaveBeenCalled();
  });

  it('waits an hour before reloading over something typed on the page', async () => {
    deployVersion('v2');
    render(
      <>
        <NewVersionBanner />
        <input aria-label="Winner" />
      </>,
    );
    fireEvent.input(screen.getByLabelText('Winner'), { target: { value: 'Sam' } });

    await advance(IDLE_BEFORE_RELOAD_AFTER_TYPING_MS - 2000);

    expect(reload).not.toHaveBeenCalled();
    expect(screen.getByRole('status')).toHaveTextContent('new version');

    await advance(3000);

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('reloads on the next page change, even with something typed', async () => {
    deployVersion('v2');
    render(
      <>
        <NewVersionBanner />
        <input aria-label="Winner" />
      </>,
    );
    fireEvent.input(screen.getByLabelText('Winner'), { target: { value: 'Sam' } });
    await advance(CHECK_INTERVAL_MS);

    window.location.pathname = '/passes';
    await advance(1000);

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('reloads when the banner button is clicked', async () => {
    deployVersion('v2');
    await findNewVersion();

    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('does not reload again for a version a reload did not bring', async () => {
    deployVersion('v2');
    sessionStorage.setItem('kalx_reloaded_for_version', 'v2');
    render(<NewVersionBanner />);

    await advance(IDLE_BEFORE_RELOAD_MS * 2);

    expect(reload).not.toHaveBeenCalled();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('checks as soon as the tab becomes visible again', async () => {
    deployVersion('v2');
    render(<NewVersionBanner />);

    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(fetch).toHaveBeenCalledWith('/api/version', { cache: 'no-store' });
    expect(screen.getByRole('status')).toHaveTextContent('new version');
  });
});
