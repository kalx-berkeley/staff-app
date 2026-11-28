import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MetricView from './MetricView';
import type { TableMetric } from './types';

const metric: TableMetric = {
  id: 'venues_without_shows',
  title: 'Venues with no shows posted',
  kind: 'table',
  columns: [{ key: 'venue', label: 'Venue', format: 'text', link: null }],
  rows: [{ venue: 'The Fillmore' }, { venue: 'The Chapel' }],
  top: null,
  collapsed: true,
  explanation: { formula: 'f', date_basis: 'Show date', includes: null, excludes: null, data_since: null },
};

describe('MetricView collapsed tables', () => {
  it('hides the rows until expanded', () => {
    render(
      <MemoryRouter>
        <MetricView metric={metric} />
      </MemoryRouter>
    );
    expect(screen.queryByText('The Fillmore')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Show all 2' }));
    expect(screen.getByText('The Fillmore')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Hide' }));
    expect(screen.queryByText('The Fillmore')).not.toBeInTheDocument();
  });

  it('says so when there are none', () => {
    render(
      <MemoryRouter>
        <MetricView metric={{ ...metric, rows: [] }} />
      </MemoryRouter>
    );
    expect(screen.getByText('None in this time window.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Show all/ })).not.toBeInTheDocument();
  });
});
