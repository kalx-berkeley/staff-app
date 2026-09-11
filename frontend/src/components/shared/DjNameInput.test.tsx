import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import DjNameInput from './DjNameInput';
import { autocompleteAPI, specialtyShowsAPI, onAirAPI } from '../../services/api';

vi.mock('../../services/api', () => ({
  autocompleteAPI: {
    getDJNames: vi.fn(),
  },
  specialtyShowsAPI: {
    list: vi.fn(),
  },
  onAirAPI: {
    getCurrent: vi.fn(),
  },
}));

describe('DjNameInput on-air sync', () => {
  beforeEach(() => {
    vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue([]);
    vi.mocked(specialtyShowsAPI.list).mockResolvedValue([]);
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('auto-populates the field when empty and a DJ is on air', async () => {
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue({
      current_dj_name: 'Murky Logic',
      current_show_ends_at: null,
      next_dj_name: null,
    });
    const handleChange = vi.fn();

    render(<DjNameInput value="" onChange={handleChange} />);

    await waitFor(() => expect(handleChange).toHaveBeenCalledWith('Murky Logic'));
  });

  it('leaves an empty field empty when no specific DJ is on air', async () => {
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue({
      current_dj_name: null,
      current_show_ends_at: null,
      next_dj_name: null,
    });
    const handleChange = vi.fn();

    render(<DjNameInput value="" onChange={handleChange} />);

    await waitFor(() => expect(onAirAPI.getCurrent).toHaveBeenCalled());
    expect(handleChange).not.toHaveBeenCalled();
  });

  it('does not overwrite a non-empty value on mount', async () => {
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue({
      current_dj_name: 'Murky Logic',
      current_show_ends_at: null,
      next_dj_name: null,
    });
    const handleChange = vi.fn();

    render(<DjNameInput value="Someone Else" onChange={handleChange} />);

    await waitFor(() => expect(onAirAPI.getCurrent).toHaveBeenCalled());
    expect(handleChange).not.toHaveBeenCalled();
  });

  it('shows a mismatch warning with a fix button when the name differs from on-air', async () => {
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue({
      current_dj_name: 'Murky Logic',
      current_show_ends_at: null,
      next_dj_name: null,
    });
    const handleChange = vi.fn();

    render(<DjNameInput value="Someone Else" onChange={handleChange} />);

    const fixButton = await screen.findByRole('button', { name: /use murky logic/i });
    fixButton.click();

    expect(handleChange).toHaveBeenCalledWith('Murky Logic');
  });

  it('does not show a mismatch warning when the name matches (case-insensitive)', async () => {
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue({
      current_dj_name: 'Murky Logic',
      current_show_ends_at: null,
      next_dj_name: null,
    });

    render(<DjNameInput value="murky logic" onChange={vi.fn()} />);

    await waitFor(() => expect(onAirAPI.getCurrent).toHaveBeenCalled());
    expect(screen.queryByText(/doesn't match the scheduled on-air dj/i)).not.toBeInTheDocument();
  });

  it('auto-advances to the next DJ and shows a notice when the current show ends', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const endsAt = new Date(Date.now() + 1000).toISOString();
    vi.mocked(onAirAPI.getCurrent)
      .mockResolvedValueOnce({
        current_dj_name: 'Murky Logic',
        current_show_ends_at: endsAt,
        next_dj_name: 'Next DJ',
      })
      .mockResolvedValueOnce({
        current_dj_name: 'Next DJ',
        current_show_ends_at: null,
        next_dj_name: null,
      });
    const handleChange = vi.fn();

    render(<DjNameInput value="Murky Logic" onChange={handleChange} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(handleChange).toHaveBeenCalledWith('Next DJ');
    expect(screen.getByText(/DJ name updated to Next DJ/i)).toBeInTheDocument();
  });

  it('clears the field (with a notice) when the schedule moves to a show with no specific DJ', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const endsAt = new Date(Date.now() + 1000).toISOString();
    vi.mocked(onAirAPI.getCurrent)
      .mockResolvedValueOnce({
        current_dj_name: 'Murky Logic',
        current_show_ends_at: endsAt,
        next_dj_name: null,
      })
      .mockResolvedValueOnce({
        current_dj_name: null,
        current_show_ends_at: null,
        next_dj_name: null,
      });
    const handleChange = vi.fn();

    render(<DjNameInput value="Murky Logic" onChange={handleChange} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(handleChange).toHaveBeenCalledWith('');
    expect(screen.getByText(/DJ name cleared/i)).toBeInTheDocument();
  });
});
