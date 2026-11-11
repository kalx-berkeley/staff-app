import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import TablerPassesSection from './TablerPassesSection';
import { passesAPI, showsAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { PassResponse, ShowResponse } from '../types';

vi.mock('../api', () => ({
  passesAPI: {
    claimTablerPass: vi.fn(),
    assignTablerPass: vi.fn(),
    releaseClaim: vi.fn(),
  },
  showsAPI: {
    listStaffPassClaimants: vi.fn(),
  },
}));

const tablerPass = (overrides: Partial<PassResponse>): PassResponse =>
  ({
    id: 10,
    show_id: 1,
    pass_type: 'tabler',
    status: 'available',
    staff_id: null,
    staff_name: null,
    staff_email: null,
    ...overrides,
  }) as PassResponse;

const makeShow = (passes: PassResponse[], overrides: Partial<ShowResponse> = {}): ShowResponse =>
  ({
    id: 1,
    status: 'published',
    co_announce: true,
    num_tabler_passes: passes.length,
    passes,
    ...overrides,
  }) as ShowResponse;

const pennyPass = tablerPass({
  id: 10,
  status: 'claimed',
  staff_id: 3,
  staff_name: 'Penny',
  staff_email: 'penny@kalx.test',
});

describe('TablerPassesSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("isn't shown on a show without tabler passes", async () => {
    const { container } = await renderAndSettle(
      <TablerPassesSection
        show={makeShow([], { co_announce: true, num_tabler_passes: 0 })}
        mode="staff"
        myEmail="sam@kalx.test"
        onChanged={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('shows everyone who is tabling, with no claim button for non-Publicity staff', async () => {
    await renderAndSettle(
      <TablerPassesSection
        show={makeShow([pennyPass, tablerPass({ id: 11 })])}
        mode="staff"
        myEmail="sam@kalx.test"
        canClaim={false}
        onChanged={vi.fn()}
      />,
    );
    expect(screen.getByText(/1 of 2 tabler passes claimed/i)).toBeInTheDocument();
    expect(screen.getByText('Penny')).toBeInTheDocument();
    expect(screen.getByText(/only publicity members can claim/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /claim a tabler pass/i })).not.toBeInTheDocument();
  });

  it('lets a Publicity member claim an open tabler pass', async () => {
    vi.mocked(passesAPI.claimTablerPass).mockResolvedValue(pennyPass);
    const onChanged = vi.fn().mockResolvedValue(undefined);
    await renderAndSettle(
      <TablerPassesSection
        show={makeShow([tablerPass({ id: 11 })])}
        mode="staff"
        myEmail="penny@kalx.test"
        canClaim
        onChanged={onChanged}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /claim a tabler pass/i }));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(passesAPI.claimTablerPass).toHaveBeenCalledWith(1);
    expect(await screen.findByRole('button', { name: /claim a tabler pass/i })).toBeEnabled();
  });

  it('tells a Publicity member why they cannot claim', async () => {
    await renderAndSettle(
      <TablerPassesSection
        show={makeShow([tablerPass({ id: 11 })])}
        mode="staff"
        myEmail="penny@kalx.test"
        canClaim
        blockedReason="You have a staff pass for this show."
        onChanged={vi.fn()}
      />,
    );
    expect(screen.getByText('You have a staff pass for this show.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /claim a tabler pass/i })).not.toBeInTheDocument();
  });

  it('lets the tabler release their own pass', async () => {
    vi.mocked(passesAPI.releaseClaim).mockResolvedValue(tablerPass({ id: 10 }));
    const onChanged = vi.fn().mockResolvedValue(undefined);
    await renderAndSettle(
      <TablerPassesSection
        show={makeShow([pennyPass])}
        mode="staff"
        myEmail="penny@kalx.test"
        canClaim
        onChanged={onChanged}
      />,
    );
    expect(screen.getByText(/penny \(you\)/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /release my tabler pass/i }));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(passesAPI.releaseClaim).toHaveBeenCalledWith(10);
    expect(await screen.findByRole('button', { name: /release my tabler pass/i })).toBeEnabled();
  });

  it('shows the server error when a claim fails', async () => {
    vi.mocked(passesAPI.claimTablerPass).mockRejectedValue({
      detail: 'All the tabler passes for this show have been claimed',
    });
    await renderAndSettle(
      <TablerPassesSection
        show={makeShow([tablerPass({ id: 11 })])}
        mode="staff"
        myEmail="penny@kalx.test"
        canClaim
        onChanged={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /claim a tabler pass/i }));
    expect(await screen.findByText(/have been claimed/i)).toBeInTheDocument();
  });

  it('lets promotions release any tabler and assign a staff member', async () => {
    vi.mocked(showsAPI.listStaffPassClaimants).mockResolvedValue([
      { id: 8, name: 'Sam Staff', email: 'sam@kalx.test' },
    ]);
    vi.mocked(passesAPI.assignTablerPass).mockResolvedValue(pennyPass);
    const onChanged = vi.fn().mockResolvedValue(undefined);
    await renderAndSettle(
      <TablerPassesSection
        show={makeShow([pennyPass, tablerPass({ id: 11 })])}
        mode="promotions"
        myEmail="pat@kalx.test"
        onChanged={onChanged}
      />,
    );
    expect(screen.getByRole('button', { name: /^release$/i })).toBeInTheDocument();

    const input = screen.getByLabelText(/give a tabler pass to/i);
    fireEvent.focus(input);
    await waitFor(() => expect(showsAPI.listStaffPassClaimants).toHaveBeenCalledWith(true));
    fireEvent.change(input, { target: { value: 'sam@kalx.test' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(passesAPI.assignTablerPass).toHaveBeenCalledWith(1, 8));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(await screen.findByLabelText(/give a tabler pass to/i)).toHaveValue('');
  });
});
