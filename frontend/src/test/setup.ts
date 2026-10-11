import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, vi } from 'vitest';

// Fail any test that triggers React's "not wrapped in act(...)" warning, so
// these get fixed when they're introduced instead of piling up as noise.
let actWarnings: string[] = [];

beforeEach(() => {
  actWarnings = [];
  const originalError = console.error;
  vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
    const [format, ...rest] = args.map(String);
    if (format?.includes('not wrapped in act(')) {
      // React passes the component name as a %s argument.
      actWarnings.push(format.split('\n')[0].replace('%s', rest[0] ?? '?'));
    }
    originalError(...args);
  });
});

afterEach(() => {
  const warnings = actWarnings;
  actWarnings = [];
  if (warnings.length > 0) {
    throw new Error(
      `React state updated outside act():\n  ${warnings.join('\n  ')}\n` +
        'Await whatever triggers the update (findBy*, waitFor, or renderAndSettle in src/test/render.tsx).',
    );
  }
});
