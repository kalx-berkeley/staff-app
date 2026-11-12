import { describe, expect, it } from 'vitest';

// Formatting dates outside common/dateTime.ts is how UTC times kept reaching
// the screen: each page picked its own time zone (or none). This test keeps
// all of it in one place.
const sources = import.meta.glob(['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}', '!../test/**'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

const FORBIDDEN = [
  /\.toLocaleString\(/,
  /\.toLocaleDateString\(/,
  /\.toLocaleTimeString\(/,
  /Intl\.DateTimeFormat/,
  /America\/Los_Angeles/,
  // The UTC date, which is tomorrow's in the evening
  /toISOString\(\)\.(split|slice|substring)\(/,
];

describe('date formatting', () => {
  it('only happens in common/dateTime.ts', () => {
    const offenders = Object.entries(sources)
      .filter(([path]) => path !== './dateTime.ts')
      .flatMap(([path, text]) =>
        text
          .split('\n')
          .map((line, i) => ({ line, i }))
          .filter(({ line }) => FORBIDDEN.some((re) => re.test(line)))
          .map(({ line, i }) => `${path}:${i + 1}: ${line.trim()}`),
      );
    expect(offenders, 'Use the helpers in common/dateTime.ts instead').toEqual([]);
  });
});
