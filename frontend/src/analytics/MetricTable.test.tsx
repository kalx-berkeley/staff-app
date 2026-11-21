import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MetricTable from './MetricTable';

describe('MetricTable links', () => {
  it('links outside the analytics site with encoded values', () => {
    render(
      <MemoryRouter initialEntries={['/?preset=all_time']}>
        <MetricTable
          label="Similar names"
          columns={[
            {
              key: 'name',
              label: 'Name',
              format: 'text',
              link: '/pass-giveaway/promotions/admin?caller={name}#linked-callers',
              external: true,
            },
          ]}
          rows={[{ name: 'Jane & Jon Doe' }]}
        />
      </MemoryRouter>
    );
    expect(screen.getByRole('link', { name: 'Jane & Jon Doe' })).toHaveAttribute(
      'href',
      '/pass-giveaway/promotions/admin?caller=Jane%20%26%20Jon%20Doe#linked-callers'
    );
  });
});
