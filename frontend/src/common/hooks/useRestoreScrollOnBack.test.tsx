import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, fireEvent, screen } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter, Outlet, Route, Routes, useNavigate } from 'react-router-dom';
import { renderAndSettle } from '../../test/render';
import { useRestoreScrollOnBack } from './useRestoreScrollOnBack';

// The list says "Loading" until the test clicks "Finish loading", like the
// shows lists waiting for their fetch.
const List = () => {
  const [ready, setReady] = useState(false);
  const rootRef = useRestoreScrollOnBack(ready);
  const navigate = useNavigate();
  return (
    <div ref={rootRef}>
      <p>{ready ? 'List loaded' : 'Loading'}</p>
      <button onClick={() => setReady(true)}>Finish loading</button>
      <button onClick={() => navigate('/show')}>Open show</button>
    </div>
  );
};

const Show = () => {
  const navigate = useNavigate();
  return (
    <div>
      <p>Show page</p>
      <button onClick={() => navigate(-1)}>Back</button>
      <button onClick={() => navigate('/list')}>Open list</button>
    </div>
  );
};

// Like the pass giveaway layouts, whose <main> scrolls rather than the window.
const ScrollingLayout = () => (
  <main data-testid="layout" style={{ overflowY: 'auto' }}>
    <Outlet />
  </main>
);

const PlainLayout = () => <Outlet />;

// jsdom doesn't lay out or scroll, so scroll positions are faked: a plain
// value for the layout's scrollTop, and a scrollTo that sets window.scrollY.
const windowScrollTo = vi.fn((_x: number, y: number) => {
  window.scrollY = y;
});

let entryKey = 0;
const renderApp = async (inLayout: boolean) => {
  const result = await renderAndSettle(
    // A distinct key per test, since saved positions are module state.
    <MemoryRouter initialEntries={[{ pathname: '/list', key: `entry-${++entryKey}` }]}>
      <Routes>
        <Route element={inLayout ? <ScrollingLayout /> : <PlainLayout />}>
          <Route path="/list" element={<List />} />
          <Route path="/show" element={<Show />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
  if (!inLayout) {
    return {
      ...result,
      scrollUser: (y: number) => {
        window.scrollY = y;
        fireEvent.scroll(window);
      },
      position: () => window.scrollY,
    };
  }
  const layout = screen.getByTestId('layout');
  let scrollTop = 0;
  Object.defineProperty(layout, 'scrollTop', {
    get: () => scrollTop,
    set: (y: number) => {
      scrollTop = y;
    },
  });
  return {
    ...result,
    scrollUser: (y: number) => {
      scrollTop = y;
      fireEvent.scroll(layout);
    },
    position: () => scrollTop,
  };
};

const click = async (name: string) => {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name }));
  });
};

describe.each([
  ['the window', false],
  ['a scrolling layout element', true],
])('useRestoreScrollOnBack scrolling %s', (_name, inLayout) => {
  beforeEach(() => {
    vi.stubGlobal('scrollTo', windowScrollTo);
    window.scrollY = 0;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    windowScrollTo.mockClear();
  });

  it('restores the scroll position after the page loads when the user goes back', async () => {
    const { scrollUser, position } = await renderApp(inLayout);
    await click('Finish loading');
    scrollUser(640);

    await click('Open show');
    expect(await screen.findByText('Show page')).toBeInTheDocument();
    scrollUser(0);

    await click('Back');
    expect(await screen.findByText('Loading')).toBeInTheDocument();
    expect(position()).toBe(0);

    await click('Finish loading');
    expect(await screen.findByText('List loaded')).toBeInTheDocument();
    expect(position()).toBe(640);
  });

  it('ignores the short loading page scrolling to the top before the restore', async () => {
    const { scrollUser, position } = await renderApp(inLayout);
    await click('Finish loading');
    scrollUser(300);
    await click('Open show');
    await click('Back');

    // The browser clamps the still-loading page to the top.
    scrollUser(0);
    await click('Finish loading');
    expect(await screen.findByText('List loaded')).toBeInTheDocument();
    expect(position()).toBe(300);
  });

  it('leaves the scroll position alone when the page is opened with a new navigation', async () => {
    const { scrollUser, position } = await renderApp(inLayout);
    await click('Finish loading');
    scrollUser(500);
    await click('Open show');
    scrollUser(0);

    await click('Open list');
    await click('Finish loading');
    expect(await screen.findByText('List loaded')).toBeInTheDocument();
    expect(position()).toBe(0);
  });
});
