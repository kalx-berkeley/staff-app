import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import ProfileSettings from './ProfileSettings';
import { usersAPI, showsAPI } from '../../services/api';
import type { PromotionsStaffProfile, StaffProfile } from '../../types';

vi.mock('../../services/api', () => ({
  usersAPI: {
    getProfile: vi.fn(),
    getNotificationPreferences: vi.fn().mockResolvedValue({ email_enabled: true }),
    updateNotificationPreferences: vi.fn(),
    getGenrePreferences: vi.fn().mockResolvedValue({ genres: [] }),
    updateGenrePreferences: vi.fn(),
  },
  showsAPI: {
    listGenres: vi.fn().mockResolvedValue([]),
  },
}));

describe('ProfileSettings', () => {
  const mockPromotionsProfile: PromotionsStaffProfile = {
    name: 'John Doe',
    phone: '555-123-4567',
    is_sublist_dj: false,
  };

  const mockStaffProfile: StaffProfile = {
    name: 'Jane Smith',
    phone: '555-987-6543',
    dj_name: null,
    is_sublist_dj: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show loading state initially', () => {
    vi.mocked(usersAPI.getProfile).mockImplementation(
      () => new Promise(() => {})
    );

    render(<ProfileSettings />);

    expect(screen.getByText('Loading profile...')).toBeInTheDocument();
  });

  it('should display profile name and phone for a promotions profile', async () => {
    vi.mocked(usersAPI.getProfile).mockResolvedValue(mockPromotionsProfile);

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.queryByText('Loading profile...')).not.toBeInTheDocument();
    });

    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('555-123-4567')).toBeInTheDocument();
  });

  it('should display profile name and phone for a staff profile', async () => {
    vi.mocked(usersAPI.getProfile).mockResolvedValue(mockStaffProfile);

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.queryByText('Loading profile...')).not.toBeInTheDocument();
    });

    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.getByText('555-987-6543')).toBeInTheDocument();
  });

  it('should display the Airtable notice', async () => {
    vi.mocked(usersAPI.getProfile).mockResolvedValue(mockPromotionsProfile);

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.queryByText('Loading profile...')).not.toBeInTheDocument();
    });

    expect(screen.getByText(/managed in Airtable/i)).toBeInTheDocument();
  });

  it('should not render any editable inputs or save button in the read-only profile info section', async () => {
    vi.mocked(usersAPI.getProfile).mockResolvedValue(mockPromotionsProfile);

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.queryByText('Loading profile...')).not.toBeInTheDocument();
    });

    const profileInfo = document.querySelector('.profile-info') as HTMLElement;
    expect(profileInfo).not.toBeNull();
    expect(within(profileInfo).queryByRole('textbox')).not.toBeInTheDocument();
    expect(within(profileInfo).queryByRole('button')).not.toBeInTheDocument();
  });

  it('should show error state with retry button when load fails', async () => {
    vi.mocked(usersAPI.getProfile).mockRejectedValue({
      detail: 'Failed to load profile',
    });

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.getByText(/error:/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });

  it('should reload profile when retry button is clicked', async () => {
    vi.mocked(usersAPI.getProfile)
      .mockRejectedValueOnce({ detail: 'Failed to load profile' })
      .mockResolvedValueOnce(mockPromotionsProfile);

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
  });

  it('should display em-dash for missing name or phone', async () => {
    vi.mocked(usersAPI.getProfile).mockResolvedValue({ name: '', phone: '', is_sublist_dj: false });

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.queryByText('Loading profile...')).not.toBeInTheDocument();
    });

    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2);
  });

  describe('genre preferences', () => {
    beforeEach(() => {
      vi.mocked(usersAPI.getProfile).mockResolvedValue(mockPromotionsProfile);
    });

    it('should display existing genre preferences as tags', async () => {
      vi.mocked(usersAPI.getGenrePreferences).mockResolvedValue({ genres: ['rock', 'jazz'] });

      render(<ProfileSettings />);

      await waitFor(() => {
        expect(screen.getByText('rock')).toBeInTheDocument();
        expect(screen.getByText('jazz')).toBeInTheDocument();
      });
    });

    it('should add a genre and save it', async () => {
      vi.mocked(usersAPI.getGenrePreferences).mockResolvedValue({ genres: [] });
      vi.mocked(usersAPI.updateGenrePreferences).mockResolvedValue({ genres: ['blues'] });
      vi.mocked(showsAPI.listGenres).mockResolvedValue(['blues', 'rock']);

      render(<ProfileSettings />);

      await waitFor(() => {
        expect(screen.queryByText('Loading genre preferences...')).not.toBeInTheDocument();
      });

      const genreInput = screen.getByLabelText('Genres');
      fireEvent.change(genreInput, { target: { value: 'Blues' } });
      fireEvent.keyDown(genreInput, { key: 'Enter' });

      await waitFor(() => {
        expect(usersAPI.updateGenrePreferences).toHaveBeenCalledWith({ genres: ['blues'] });
      });
      expect(screen.getByText('blues')).toBeInTheDocument();

      // The field is briefly disabled while the save is in flight (which blurs
      // it), and should regain focus once saved instead of leaving the user to
      // click back in before typing the next genre.
      await waitFor(() => {
        expect(document.activeElement).toBe(genreInput);
      });
    });

    it('should remove a genre and save the change', async () => {
      vi.mocked(usersAPI.getGenrePreferences).mockResolvedValue({ genres: ['rock'] });
      vi.mocked(usersAPI.updateGenrePreferences).mockResolvedValue({ genres: [] });

      render(<ProfileSettings />);

      await waitFor(() => {
        expect(screen.getByText('rock')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: 'Remove rock' }));

      await waitFor(() => {
        expect(usersAPI.updateGenrePreferences).toHaveBeenCalledWith({ genres: [] });
      });
    });
  });
});
