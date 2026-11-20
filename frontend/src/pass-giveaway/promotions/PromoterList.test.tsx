import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import PromoterList from './PromoterList';
import { promotersAPI } from '../api';
import { useReturnToList } from '../listUrlState';
import { renderAndSettle } from '../../test/render';
import type { PromoterResponse } from '../types';

vi.mock('../api', () => ({
  promotersAPI: { list: vi.fn() },
}));

const promoters = [
  { id: 1, name: 'Another Planet', owner_emails: [] },
  { id: 2, name: 'Goldenvoice', owner_emails: [] },
] as unknown as PromoterResponse[];

// Stands in for PromoterEdit: its Back button and the browser's Back.
const EditPage = () => {
  const navigate = useNavigate();
  const returnTo = useReturnToList('/promotions/promoters');
  return (
    <>
      <button onClick={() => navigate(returnTo)}>Back to Promoters</button>
      <button onClick={() => navigate(-1)}>Browser Back</button>
    </>
  );
};

describe('promotions PromoterList', () => {
  beforeEach(() => {
    vi.mocked(promotersAPI.list).mockResolvedValue(promoters);
  });

  afterEach(() => {
    cleanup();
  });

  it.each(['Back to Promoters', 'Browser Back'])(
    'keeps the filter after editing a promoter and going back (%s)',
    async (back) => {
      await renderAndSettle(
        <MemoryRouter initialEntries={['/promotions/promoters']}>
          <Routes>
            <Route path="/promotions/promoters" element={<PromoterList />} />
            <Route path="/promotions/promoters/:id/edit" element={<EditPage />} />
          </Routes>
        </MemoryRouter>,
      );
      fireEvent.change(screen.getByPlaceholderText('Filter promoters by name...'), {
        target: { value: 'planet' },
      });
      expect(screen.queryByText('Goldenvoice')).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
      fireEvent.click(await screen.findByRole('button', { name: back }));

      expect(await screen.findByText('Another Planet')).toBeInTheDocument();
      expect(screen.queryByText('Goldenvoice')).not.toBeInTheDocument();
      expect(screen.getByPlaceholderText('Filter promoters by name...')).toHaveValue('planet');
    },
  );
});
