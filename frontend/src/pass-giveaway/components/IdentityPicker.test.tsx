import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderAndSettle } from '../../test/render';
import IdentityPicker from './IdentityPicker';
import type { Identity } from '../types';

const djAce: Identity = {
  name: 'DJ Ace',
  kind: 'persona',
  persona_id: 1,
  specialty_show_id: null,
  staff_name: 'Alex Smith',
};
const jazzShow: Identity = {
  name: 'Jazz Hour',
  kind: 'music',
  persona_id: null,
  specialty_show_id: 7,
};

const Harness = ({ onChange }: { onChange: (identity: Identity | null) => void }) => {
  const [value, setValue] = useState<Identity | null>(null);
  return (
    <IdentityPicker
      options={[djAce, jazzShow]}
      value={value}
      onChange={(identity) => {
        setValue(identity);
        onChange(identity);
      }}
      aria-label="Pre-assign to"
    />
  );
};

describe('IdentityPicker', () => {
  it('clears typed text that is not a DJ or show when the field loses focus', async () => {
    const onChange = vi.fn();
    await renderAndSettle(<Harness onChange={onChange} />);
    const input = screen.getByLabelText('Pre-assign to') as HTMLInputElement;

    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Not A Real DJ' } });
    expect(onChange).toHaveBeenLastCalledWith(null);
    fireEvent.blur(input);

    await waitFor(() => expect(input.value).toBe(''));
  });

  it('keeps a name picked from the list when the field loses focus', async () => {
    const onChange = vi.fn();
    await renderAndSettle(<Harness onChange={onChange} />);
    const input = screen.getByLabelText('Pre-assign to') as HTMLInputElement;

    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'ace' } });
    fireEvent.mouseDown(screen.getByText('DJ Ace'));
    fireEvent.blur(input);

    expect(onChange).toHaveBeenLastCalledWith(djAce);
    await waitFor(() => expect(screen.queryByRole('listitem')).not.toBeInTheDocument());
    expect(input.value).toBe('DJ Ace');
  });

  it('keeps a typed exact name when the field loses focus', async () => {
    const onChange = vi.fn();
    await renderAndSettle(<Harness onChange={onChange} />);
    const input = screen.getByLabelText('Pre-assign to') as HTMLInputElement;

    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'jazz hour' } });
    fireEvent.blur(input);

    expect(onChange).toHaveBeenLastCalledWith(jazzShow);
    await waitFor(() => expect(screen.queryByRole('listitem')).not.toBeInTheDocument());
    // A value picked by typing shows the option's own spelling once settled
    expect(input.value.toLowerCase()).toBe('jazz hour');
  });
});
