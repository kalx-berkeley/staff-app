import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen } from '@testing-library/react';
import { onAirAPI, passesAPI } from '../api';
import type { OnAirInfo, PassResponse } from '../types';
import { renderAndSettle } from '../../test/render';
import { pacificDateString } from '../../common/dateTime';
import OnAirBanner from './OnAirBanner';
import OnAirProvider from './OnAirProvider';
import { useOnAir } from './onAirContext';
import { savedSwitch } from './onAirHeaders';
import { persona, showIdentity } from './testOnAir';

vi.mock('../api', () => ({
  onAirAPI: { getCurrent: vi.fn() },
  passesAPI: { getMyGiveaways: vi.fn() },
}));

const inMinutes = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString();

const onAir = (overrides: Partial<OnAirInfo> = {}): OnAirInfo => ({
  current: persona(1, 'DJ One'),
  current_ends_at: inMinutes(5),
  next: persona(2, 'DJ Two'),
  next_starts_at: inMinutes(5),
  can_switch_early: false,
  ...overrides,
});

// Shows who the pages credit, to check the switch reaches them
const Credited = () => {
  const { identity } = useOnAir();
  return <p data-testid="credited">{identity?.name ?? 'no one'}</p>;
};

// The banner asks who is on air, then (when offering a switch) how many
// passes the next DJ has; let both answers land inside act()
const renderBanner = async () => {
  await renderAndSettle(
    <OnAirProvider>
      <OnAirBanner />
      <Credited />
    </OnAirProvider>,
  );
  await act(async () => {});
};

describe('OnAirBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });
  afterEach(() => localStorage.clear());

  it("shows who is on air and how to fix it if it isn't them", async () => {
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue(onAir());
    await renderBanner();

    expect(screen.getByLabelText('On air')).toHaveTextContent('On air: DJ One');
    expect(screen.getByText(/If this isn't you, create your Spinitron playlist/)).toBeInTheDocument();
    expect(screen.getByTestId('credited')).toHaveTextContent('DJ One');
    expect(screen.queryByRole('button', { name: /switch now/ })).not.toBeInTheDocument();
  });

  it('names a music show and its DJ', async () => {
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue(
      onAir({ current: showIdentity('music', 7, 'Take Five', { personaId: 1, name: 'DJ One' }) }),
    );
    await renderBanner();

    expect(screen.getByLabelText('On air')).toHaveTextContent(
      'On air: Take Five (Specialty Music Show) with DJ One',
    );
  });

  it('warns when no one is on air', async () => {
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue(onAir({ current: null }));
    await renderBanner();

    expect(screen.getByRole('alert')).toHaveTextContent('recorded as unattributed');
    expect(screen.getByTestId('credited')).toHaveTextContent('no one');
  });

  it('offers the next DJ a switch, with their passes for today, and a way back', async () => {
    const info = onAir({ can_switch_early: true });
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue(info);
    const today = pacificDateString();
    vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([
      { id: 1, status: 'available', preassigned_date: today },
      { id: 2, status: 'available', preassigned_date: '2099-01-01' },
      { id: 3, status: 'given_away', preassigned_date: today },
    ] as PassResponse[]);
    await renderBanner();

    expect(passesAPI.getMyGiveaways).toHaveBeenCalledWith(info.next_starts_at);
    fireEvent.click(
      await screen.findByRole('button', { name: "I'm DJ Two (1 pre-assigned pass) — switch now" }),
    );

    expect(screen.getByTestId('credited')).toHaveTextContent('DJ Two');
    expect(savedSwitch()).toBe(info.next_starts_at);
    expect(screen.queryByRole('button', { name: /switch now/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Switch back to DJ One' }));

    expect(screen.getByTestId('credited')).toHaveTextContent('DJ One');
    expect(savedSwitch()).toBeNull();
    // The offer is back
    expect(
      await screen.findByRole('button', { name: "I'm DJ Two (1 pre-assigned pass) — switch now" }),
    ).toBeInTheDocument();
  });

  it('keeps an early switch made in another tab', async () => {
    const info = onAir({ can_switch_early: true });
    localStorage.setItem('kalx_dj_switch_to', info.next_starts_at!);
    vi.mocked(onAirAPI.getCurrent).mockResolvedValue(info);
    await renderBanner();

    expect(screen.getByTestId('credited')).toHaveTextContent('DJ Two');
    expect(screen.getByRole('button', { name: 'Switch back to DJ One' })).toBeInTheDocument();
  });
});
