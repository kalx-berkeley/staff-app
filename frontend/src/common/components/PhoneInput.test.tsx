import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import PhoneInput from './PhoneInput';

/** A PhoneInput whose parent keeps the digits, as the forms do. */
const Harness = ({ initial = '', onChange }: { initial?: string; onChange?: (v: string) => void }) => {
  const [value, setValue] = useState(initial);
  return (
    <>
      <label htmlFor="phone">Phone</label>
      <PhoneInput
        id="phone"
        value={value}
        onChange={(v) => {
          setValue(v);
          onChange?.(v);
        }}
      />
      <button type="button" onClick={() => setValue('')}>
        Clear
      </button>
    </>
  );
};

const phoneInput = () => screen.getByLabelText('Phone') as HTMLInputElement;

describe('PhoneInput', () => {
  it('formats a number as it is typed and gives the parent only the digits', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    expect(phoneInput()).toHaveAttribute('type', 'tel');

    fireEvent.change(phoneInput(), { target: { value: '5106' } });
    expect(phoneInput()).toHaveValue('(510) 6');

    fireEvent.change(phoneInput(), { target: { value: '(510) 6421111' } });
    expect(phoneInput()).toHaveValue('(510) 642-1111');
    expect(onChange).toHaveBeenLastCalledWith('5106421111');
  });

  it('drops a pasted +1 and stops at 10 digits', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.change(phoneInput(), { target: { value: '+1 510 642 1111 99' } });
    expect(phoneInput()).toHaveValue('(510) 642-1111');
    expect(onChange).toHaveBeenLastCalledWith('5106421111');
  });

  it('shows a saved number formatted', () => {
    render(<Harness initial="5106421111" />);
    expect(phoneInput()).toHaveValue('(510) 642-1111');
  });

  it('keeps the caret after the same digit when formatting moves it', () => {
    render(<Harness initial="510642111" />);
    const input = phoneInput();
    expect(input).toHaveValue('(510) 642-111');
    input.focus();

    // Type a 9 after "(510) 6", which pushes the digits after it along
    fireEvent.change(input, { target: { value: '(510) 6942-111', selectionStart: 8 } });

    expect(input).toHaveValue('(510) 694-2111');
    expect(input.selectionStart).toBe(8);
  });

  it('deletes the digit before a space or bracket, rather than the formatting alone', () => {
    render(<Harness initial="5106421111" />);
    const input = phoneInput();
    input.focus();

    // Backspace just after "(510) " deletes the space, which formatting would put back
    fireEvent.input(input, {
      target: { value: '(510)642-1111', selectionStart: 5 },
      inputType: 'deleteContentBackward',
    });

    expect(input).toHaveValue('(516) 421-111');
    expect(input.selectionStart).toBe(3);
  });

  it('ignores letters without moving the caret', () => {
    render(<Harness initial="5106421111" />);
    const input = phoneInput();
    input.focus();
    fireEvent.change(input, { target: { value: '(51x0) 642-1111', selectionStart: 4 } });
    expect(input).toHaveValue('(510) 642-1111');
    expect(input.selectionStart).toBe(3);
  });

  it('shows a value the parent changes, such as clearing the form', () => {
    render(<Harness initial="5106421111" />);
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(phoneInput()).toHaveValue('');
  });
});
