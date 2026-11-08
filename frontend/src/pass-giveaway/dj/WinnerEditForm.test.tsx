import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import WinnerEditForm from './WinnerEditForm';
import { passesAPI, venuePassesAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { PassResponse } from '../types';

vi.mock('../api', () => ({
  passesAPI: {
    getWinnerForEdit: vi.fn(),
    updateWinner: vi.fn(),
  },
  venuePassesAPI: {
    checkWinner: vi.fn(),
  },
}));

const pass = {
  id: 7,
  show_id: 3,
  pass_type: 'pair',
  status: 'given_away',
  recipient_name: 'Jnae Winner',
  recipient_phone: '5105550100',
  recipient_email: null,
  given_away_by_dj: 'DJ Test',
  given_away_at: new Date().toISOString(),
} as PassResponse;

const renderForm = (props: Partial<Parameters<typeof WinnerEditForm>[0]> = {}) => {
  const onSaved = vi.fn();
  const onCancel = vi.fn();
  const result = renderAndSettle(
    <WinnerEditForm
      pass={pass}
      venueId={2}
      djName=" DJ Test "
      requiresEmail={false}
      onSaved={onSaved}
      onCancel={onCancel}
      {...props}
    />
  );
  return { result, onSaved, onCancel };
};

describe('WinnerEditForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(passesAPI.getWinnerForEdit).mockResolvedValue({
      ...pass,
      recipient_email: 'jnae@example.com',
    });
  });

  it('loads the winner, including their email, for the DJ', async () => {
    const { result } = renderForm();
    await result;

    expect(passesAPI.getWinnerForEdit).toHaveBeenCalledWith(7, 'DJ Test');
    expect(screen.getByLabelText(/Winner Name/)).toHaveValue('Jnae Winner');
    expect(screen.getByLabelText(/Winner Phone/)).toHaveValue('(510) 555-0100');
    expect(screen.getByLabelText(/Winner Email/)).toHaveValue('jnae@example.com');
  });

  it('hides the email field when there is no email and the venue does not need one', async () => {
    vi.mocked(passesAPI.getWinnerForEdit).mockResolvedValue(pass);
    const { result } = renderForm();
    await result;

    expect(screen.queryByLabelText(/Winner Email/)).not.toBeInTheDocument();
  });

  it('saves the corrected details', async () => {
    const updated = { ...pass, recipient_name: 'Jane Winner' };
    vi.mocked(passesAPI.updateWinner).mockResolvedValue(updated);
    const { result, onSaved } = renderForm();
    await result;

    fireEvent.change(screen.getByLabelText(/Winner Name/), { target: { value: ' Jane Winner ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await vi.waitFor(() => expect(onSaved).toHaveBeenCalledWith(updated));
    expect(passesAPI.updateWinner).toHaveBeenCalledWith(7, {
      recipient_name: 'Jane Winner',
      recipient_phone: '(510) 555-0100',
      recipient_email: 'jnae@example.com',
      given_away_by_dj: 'DJ Test',
    });
  });

  it('requires an email when the venue does', async () => {
    const { result } = renderForm({ requiresEmail: true });
    await result;

    fireEvent.change(screen.getByLabelText(/Winner Email/), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(
      await screen.findByText('Winner email address is required by this venue')
    ).toBeInTheDocument();
    expect(passesAPI.updateWinner).not.toHaveBeenCalled();
  });

  it('checks a changed phone against the venue limit, ignoring this winner', async () => {
    vi.mocked(venuePassesAPI.checkWinner).mockResolvedValue({
      eligible: false,
      last_win_show: 'Earlier Show',
      last_win_date: '2099-12-24',
      days_since: 7,
      required_days: 30,
    });
    const { result } = renderForm();
    await result;

    const phone = screen.getByLabelText(/Winner Phone/);
    fireEvent.change(phone, { target: { value: '510-555-0199' } });
    fireEvent.blur(phone);

    expect(await screen.findByText('Earlier Show')).toBeInTheDocument();
    expect(venuePassesAPI.checkWinner).toHaveBeenCalledWith(2, '510-555-0199', 3, 7);
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/Override/));
    expect(await screen.findByRole('button', { name: 'Save' })).toBeEnabled();
  });

  it('does not check the phone when it is unchanged', async () => {
    const { result } = renderForm();
    await result;

    fireEvent.blur(screen.getByLabelText(/Winner Phone/));

    expect(venuePassesAPI.checkWinner).not.toHaveBeenCalled();
  });

  it('shows the error when the backend refuses', async () => {
    vi.mocked(passesAPI.getWinnerForEdit).mockRejectedValue({
      detail: 'The winner can only be edited within 4 hours of the giveaway.',
    });
    const { result } = renderForm();
    await result;

    expect(
      await screen.findByText('The winner can only be edited within 4 hours of the giveaway.')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  it('cancels', async () => {
    const { result, onCancel } = renderForm();
    await result;

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onCancel).toHaveBeenCalled();
  });
});
