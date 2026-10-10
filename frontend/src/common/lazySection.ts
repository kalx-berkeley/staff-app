import { lazy, type ComponentType } from 'react';

// Lazily loads one component from a code-split section, so users only download
// the pages for the sections they use. Components are loaded through their
// section's barrel so a whole section shares one chunk, and navigating within
// a section doesn't suspend again after the first load.
export function lazySection<M, K extends keyof M>(load: () => Promise<M>, name: K) {
  return lazy(() => load().then((m) => ({ default: m[name] as ComponentType })));
}

