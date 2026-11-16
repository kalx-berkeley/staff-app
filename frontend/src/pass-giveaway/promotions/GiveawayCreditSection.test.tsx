import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { adminAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { GiveawayCreditItem, Identity } from '../types';
import GiveawayCreditSection from './GiveawayCreditSection';

vi.mock('../api', () => ({
  adminAPI: {
    getGiveaways: vi.fn(),
    getCreditIdentities: vi.fn(),
    recreditGiveaway: vi.fn(),
  },
}));

const DJ_ONE: Identity = {
  name: 'DJ One',
  kind: 'persona',
  persona_id: 11,
  specialty_show_id: null,
  staff_name: 'One',
};
const TAKE_FIVE: Identity = { name: 'Take Five', kind: 'music', persona_id: null, specialty_show_id: 3 };

const row = (overrides: Partial<GiveawayCreditItem> = {}): GiveawayCreditItem => ({
  pass_id: 5,
  show_id: 1,
  event_name: 'Test Band',
  venue_name: 'The Venue',
  show_date: '2099-12-31',
  recipient_name: 'Jane Caller',
  given_away_at: '2026-11-16T20:00:00Z',
  credited_to: 'Unattributed',
  persona_id: null,
  specialty_show_id: null,
  ...overrides,
});

describe('GiveawayCreditSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(adminAPI.getGiveaways).mockResolvedValue([row()]);
    vi.mocked(adminAPI.getCreditIdentities).mockResolvedValue([DJ_ONE, TAKE_FIVE]);
  });

  it('starts with the unattributed giveaways of the last 90 days', async () => {
    await renderAndSettle(<GiveawayCreditSection />);

    expect(adminAPI.getGiveaways).toHaveBeenCalledWith(true, 90);
    expect(screen.getByText('Jane Caller')).toBeInTheDocument();
    expect(screen.getByText('Unattributed')).toBeInTheDocument();
  });

  it('lists every giveaway when asked', async () => {
    await renderAndSettle(<GiveawayCreditSection />);

    fireEvent.click(screen.getByLabelText('Unattributed only'));

    await waitFor(() => expect(adminAPI.getGiveaways).toHaveBeenLastCalledWith(false, 90));
    expect(await screen.findByText('Jane Caller')).toBeInTheDocument();
  });

  it('re-credits a giveaway to a picked DJ or show', async () => {
    vi.mocked(adminAPI.recreditGiveaway).mockResolvedValue(
      row({ credited_to: 'Take Five', specialty_show_id: 3 }),
    );
    await renderAndSettle(<GiveawayCreditSection />);

    fireEvent.click(screen.getByRole('button', { name: 'Re-credit the Test Band giveaway' }));
    fireEvent.change(screen.getByLabelText('Credit the Test Band giveaway to'), {
      target: { value: 'take' },
    });
    fireEvent.mouseDown(await screen.findByText('Take Five'));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Take Five')).toBeInTheDocument();
    expect(adminAPI.recreditGiveaway).toHaveBeenCalledWith(5, TAKE_FIVE);
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument();
  });

  it('starts the picker at the current credit, and shows why a save failed', async () => {
    vi.mocked(adminAPI.getGiveaways).mockResolvedValue([
      row({ credited_to: 'DJ One', persona_id: 11 }),
    ]);
    vi.mocked(adminAPI.recreditGiveaway).mockRejectedValue({ detail: 'Pass not found' });
    await renderAndSettle(<GiveawayCreditSection />);

    fireEvent.click(screen.getByRole('button', { name: 'Re-credit the Test Band giveaway' }));
    expect(screen.getByLabelText('Credit the Test Band giveaway to')).toHaveValue('DJ One');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Pass not found')).toBeInTheDocument();
    expect(adminAPI.recreditGiveaway).toHaveBeenCalledWith(5, DJ_ONE);
  });
});
