import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import PromoterForm from './PromoterForm';
import { promotersAPI } from '../api';
import type { PromoterResponse } from '../types';
import { renderAndSettle } from '../../test/render';

vi.mock('../api', () => ({
  promotersAPI: {
    create: vi.fn(),
    update: vi.fn(),
  },
  venuesAPI: {
    listPromotionsStaff: vi.fn().mockResolvedValue([]),
  },
}));

const makePromoter = (overrides: Partial<PromoterResponse> = {}): PromoterResponse => ({
  id: 1,
  name: 'Existing Promoter',
  show_sourcing_instructions: null,
  pass_call_instructions: null,
  requires_phone_number: false,
  email_address_requirement: 'none',
  requires_email_address: false,
  staff_guest_requires_name: false,
  hold_close_notifications: false,
  track_pass_call_in: false,
  deleted: false,
  owner_emails: [],
  contacts: [],
  ...overrides,
});

describe('PromoterForm contacts', () => {
  const onClose = vi.fn();
  const onSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the first contact's fields with no add button until something is typed", async () => {
    await renderAndSettle(<PromoterForm promoter={null} onClose={onClose} onSuccess={onSuccess} />);

    expect(screen.getAllByPlaceholderText('Name')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: /add another contact/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Title'), { target: { value: 'Publicist' } });
    fireEvent.click(screen.getByRole('button', { name: '+ Add Another Contact' }));

    expect(screen.getAllByPlaceholderText('Name')).toHaveLength(2);
  });

  it('shows the add button for a promoter that already has contacts', async () => {
    await renderAndSettle(
      <PromoterForm
        promoter={makePromoter({
          contacts: [{ id: 1, name: 'Pat', title: null, email: null, phone: null }],
        })}
        onClose={onClose}
        onSuccess={onSuccess}
      />
    );

    expect(screen.getByPlaceholderText('Name')).toHaveValue('Pat');
    expect(screen.getByRole('button', { name: '+ Add Another Contact' })).toBeInTheDocument();
  });

  it('keeps blank contacts out of what it saves', async () => {
    vi.mocked(promotersAPI.update).mockResolvedValue(makePromoter());

    await renderAndSettle(
      <PromoterForm promoter={makePromoter()} onClose={onClose} onSuccess={onSuccess} />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Update Promoter' }));

    await waitFor(() => {
      expect(promotersAPI.update).toHaveBeenCalledWith(1, expect.objectContaining({ contacts: [] }));
    });
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it('leaves empty fields when the only contact is removed', async () => {
    await renderAndSettle(<PromoterForm promoter={null} onClose={onClose} onSuccess={onSuccess} />);

    fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: 'pat@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));

    expect(screen.getByPlaceholderText('Email')).toHaveValue('');
    expect(screen.queryByRole('button', { name: /add another contact/i })).not.toBeInTheDocument();
  });
});
