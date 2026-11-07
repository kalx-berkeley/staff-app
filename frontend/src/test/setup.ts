import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';
import { afterEach, beforeEach, vi, type MockInstance } from 'vitest';

// Sub-sites load their pages with lazy imports, and a file's first test waits for
// that import. It can take over a second when every test file runs in parallel,
// longer than the default one-second wait for findBy* and waitFor. A test that
// passes still finishes as soon as what it's waiting for appears.
configure({ asyncUtilTimeout: 5000 });

// Fail any test that triggers React's "not wrapped in act(...)" warning, so
// these get fixed when they're introduced instead of piling up as noise.
let actWarnings: string[] = [];
let errorSpy: MockInstance<typeof console.error>;

beforeEach(() => {
  actWarnings = [];
  const originalError = console.error;
  errorSpy = vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
    const [format, ...rest] = args.map(String);
    if (format?.includes('not wrapped in act(')) {
      // React passes the component name as a %s argument.
      actWarnings.push(format.split('\n')[0].replace('%s', rest[0] ?? '?'));
    }
    originalError(...args);
  });
});

afterEach(() => {
  // Otherwise the next test's originalError is this spy, which then calls itself
  errorSpy.mockRestore();
  const warnings = actWarnings;
  actWarnings = [];
  if (warnings.length > 0) {
    throw new Error(
      `React state updated outside act():\n  ${warnings.join('\n  ')}\n` +
        'Await whatever triggers the update (findBy*, waitFor, or renderAndSettle in src/test/render.tsx).',
    );
  }
});
