import { useEffect, useRef, type RefObject } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';

// Scroll positions by history entry (React Router's location.key). In memory,
// so they last for this tab's session of the SPA.
const savedPositions = new Map<string, number>();

// How long to keep retrying the restore while the page grows to its full
// height (a list rendering in a second pass, images loading).
const RESTORE_TIMEOUT_MS = 1000;

interface Scroller {
  target: EventTarget;
  get: () => number;
  set: (y: number) => void;
}

// The element that scrolls `el`: its nearest ancestor with its own scrollbar
// (such as the pass giveaway layouts' <main>), or else the window.
function findScroller(el: HTMLElement | null): Scroller {
  for (let node = el?.parentElement ?? null; node; node = node.parentElement) {
    if (node === document.body || node === document.documentElement) break;
    if (/(auto|scroll)/.test(getComputedStyle(node).overflowY)) {
      const scroller = node;
      return {
        target: scroller,
        get: () => scroller.scrollTop,
        set: (y) => {
          scroller.scrollTop = y;
        },
      };
    }
  }
  return {
    target: window,
    get: () => window.scrollY,
    set: (y) => window.scrollTo(0, y),
  };
}

/**
 * Brings a page back to where the user had scrolled it when they return with
 * the browser's back or forward button. Attach the returned ref to the page's
 * root element.
 *
 * The browser's own scroll restoration doesn't work for pages that fetch their
 * content after mounting: it scrolls while the page still says "Loading...",
 * so the page is too short and ends up at the top. (It also only handles the
 * window, not a scrolling element inside a layout.) This hook records the
 * scroll position of whatever scrolls the page, for each history entry, and on
 * a back/forward navigation scrolls back to it once `ready` is true (the
 * content has rendered). Navigating to the page any other way leaves the
 * scroll position alone.
 */
export function useRestoreScrollOnBack<T extends HTMLElement = HTMLDivElement>(
  ready: boolean,
): RefObject<T | null> {
  const rootRef = useRef<T | null>(null);
  const { key } = useLocation();
  const navigationType = useNavigationType();
  // Whether this entry still needs its position put back. Until it has been,
  // scroll events are the short loading page's, so they aren't recorded.
  const pendingRestore = useRef(navigationType === 'POP' && savedPositions.has(key));

  useEffect(() => {
    const scroller = findScroller(rootRef.current);
    const record = () => {
      if (!pendingRestore.current) savedPositions.set(key, scroller.get());
    };
    scroller.target.addEventListener('scroll', record, { passive: true });
    return () => scroller.target.removeEventListener('scroll', record);
  }, [key]);

  useEffect(() => {
    if (!ready || !pendingRestore.current) return;
    const scroller = findScroller(rootRef.current);
    const target = savedPositions.get(key) ?? 0;
    const deadline = performance.now() + RESTORE_TIMEOUT_MS;
    let frame = 0;

    const finish = () => {
      pendingRestore.current = false;
      cancelAnimationFrame(frame);
      window.removeEventListener('wheel', finish);
      window.removeEventListener('touchstart', finish);
      window.removeEventListener('keydown', finish);
    };
    // Stop retrying as soon as the user scrolls on their own.
    window.addEventListener('wheel', finish, { passive: true });
    window.addEventListener('touchstart', finish, { passive: true });
    window.addEventListener('keydown', finish);

    const attempt = () => {
      scroller.set(target);
      if (Math.abs(scroller.get() - target) < 1 || performance.now() > deadline) {
        finish();
      } else {
        frame = requestAnimationFrame(attempt);
      }
    };
    attempt();
    return finish;
  }, [ready, key]);

  return rootRef;
}
