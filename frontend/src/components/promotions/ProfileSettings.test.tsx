import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ProfileSettings from './ProfileSettings';
import { usersAPI } from '../../services/api';
import type { PromotionsStaffProfile } from '../../types';

vi.mock('../../services/api', () => ({
  usersAPI: {
    getProfile: vi.fn(),
  },
}));

describe('ProfileSettings', () => {
  const mockProfile: PromotionsStaffProfile = {
    name: 'John Doe',
    phone: '555-123-4567',
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

  it('should display profile name and phone after loading', async () => {
    vi.mocked(usersAPI.getProfile).mockResolvedValue(mockProfile);

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.queryByText('Loading profile...')).not.toBeInTheDocument();
    });

    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('555-123-4567')).toBeInTheDocument();
  });

  it('should display the Airtable notice', async () => {
    vi.mocked(usersAPI.getProfile).mockResolvedValue(mockProfile);

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.queryByText('Loading profile...')).not.toBeInTheDocument();
    });

    expect(screen.getByText(/managed in Airtable/i)).toBeInTheDocument();
  });

  it('should not render any editable inputs or save button', async () => {
    vi.mocked(usersAPI.getProfile).mockResolvedValue(mockProfile);

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.queryByText('Loading profile...')).not.toBeInTheDocument();
    });

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
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
      .mockResolvedValueOnce(mockProfile);

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
    vi.mocked(usersAPI.getProfile).mockResolvedValue({ name: '', phone: '' });

    render(<ProfileSettings />);

    await waitFor(() => {
      expect(screen.queryByText('Loading profile...')).not.toBeInTheDocument();
    });

    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2);
  });
});
