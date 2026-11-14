import type { ChangeEvent } from 'react';
import { formatUsPhoneAsTyped, usPhoneDigits } from '../utils';

interface PhoneInputProps {
  id: string;
  /** The phone number's digits (at most 10), as the backend stores them. */
  value: string;
  /** Called with the digits typed so far, on every change. */
  onChange: (digits: string) => void;
  onBlur?: () => void;
  disabled?: boolean;
  placeholder?: string;
}

const isDigit = (char: string) => char >= '0' && char <= '9';

/** How many digits `text` has before index `end`. */
const digitsBefore = (text: string, end: number) =>
  [...text.slice(0, end)].filter(isDigit).length;

/** The index just after the `count`th digit in `text`. */
function indexAfterDigit(text: string, count: number): number {
  if (count <= 0) return 0;
  let seen = 0;
  for (let i = 0; i < text.length; i++) {
    if (isDigit(text[i]) && ++seen === count) return i + 1;
  }
  return text.length;
}

/**
 * A US phone number input that formats the number as it's typed or pasted
 * ("(510) 642-1111") and keeps the caret beside the digit it was next to.
 * The parent holds only the digits, so formatting never reaches the backend.
 */
const PhoneInput = ({ id, value, onChange, onBlur, disabled, placeholder }: PhoneInputProps) => {
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const input = e.currentTarget;
    let raw = input.value;
    let caret = input.selectionStart ?? raw.length;
    const { inputType } = e.nativeEvent as InputEvent;

    // Deleting only a space, dash or bracket would be undone by formatting,
    // leaving the caret stuck, so delete the digit beside it instead.
    if (inputType?.startsWith('delete') && usPhoneDigits(raw) === usPhoneDigits(value)) {
      const forward = inputType === 'deleteContentForward';
      let i = forward ? caret : caret - 1;
      while (i >= 0 && i < raw.length && !isDigit(raw[i])) i += forward ? 1 : -1;
      if (i >= 0 && i < raw.length) {
        raw = raw.slice(0, i) + raw.slice(i + 1);
        caret = i;
      }
    }

    const allDigits = raw.replace(/\D/g, '');
    let before = digitsBefore(raw, caret);
    // usPhoneDigits drops a leading country code 1
    if (allDigits.startsWith('1') && before > 0) before -= 1;
    const digits = usPhoneDigits(raw);
    const formatted = formatUsPhoneAsTyped(digits);

    // Write the formatted value and caret now, so the caret doesn't jump to
    // the end when React re-renders with the same text.
    input.value = formatted;
    const position = indexAfterDigit(formatted, Math.min(before, digits.length));
    input.setSelectionRange(position, position);
    if (digits !== value) onChange(digits);
  };

  return (
    <input
      type="tel"
      inputMode="tel"
      id={id}
      value={formatUsPhoneAsTyped(usPhoneDigits(value))}
      onChange={handleChange}
      onBlur={onBlur}
      disabled={disabled}
      placeholder={placeholder}
      autoComplete="off"
    />
  );
};

export default PhoneInput;
