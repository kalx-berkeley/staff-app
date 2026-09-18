import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { usePageTitle } from './usePageTitle';

describe('usePageTitle', () => {
  it('sets the document title with the base app name appended', () => {
    renderHook(() => usePageTitle('Shows · Promotions'));
    expect(document.title).toBe('Shows · Promotions · Radio Pass Giveaway');
  });

  it('updates the title when the input changes', () => {
    const { rerender } = renderHook(({ title }) => usePageTitle(title), {
      initialProps: { title: 'Venues · Promotions' },
    });
    expect(document.title).toBe('Venues · Promotions · Radio Pass Giveaway');

    rerender({ title: 'Promoters · Promotions' });
    expect(document.title).toBe('Promoters · Promotions · Radio Pass Giveaway');
  });

  it('falls back to the base title when given an empty or missing title', () => {
    renderHook(() => usePageTitle(''));
    expect(document.title).toBe('Radio Pass Giveaway');

    renderHook(() => usePageTitle(undefined));
    expect(document.title).toBe('Radio Pass Giveaway');
  });
});
