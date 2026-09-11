import { useEffect, useId, useRef, useState } from 'react';
import { DayPicker, type Matcher } from 'react-day-picker';
import 'react-day-picker/style.css';
import { parseDateValue, formatDateValue } from '../../utils';

const formatDisplayValue = (date: Date): string =>
  date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

interface DatePickerProps {
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
  style?: React.CSSProperties;
  placeholder?: string;
  /** Extra dates to disable beyond the min/max range (e.g. a schedule mismatch). */
  isDateDisabled?: (date: Date) => boolean;
}

/**
 * A calendar-grid date field, replacing the browser's native `<input type="date">`
 * everywhere in the app so every date picker looks and behaves the same way.
 *
 * A real (visually hidden) native `<input type="date">` still backs the field —
 * it's what `id`/`<label htmlFor>` points to, so keyboard and screen-reader
 * users get normal native typing, and it's what existing form-level `required`/
 * validation wiring keeps working against. The visible calendar button is a
 * mouse-friendly popover on top of it, and is the only way to see the
 * `isDateDisabled` restriction rendered as greyed-out days — something a plain
 * native date input has no way to express for a non-contiguous set of dates.
 */
const DatePicker = ({
  value,
  onChange,
  min,
  max,
  disabled,
  id,
  className,
  style,
  placeholder = 'Select date…',
  isDateDisabled,
}: DatePickerProps) => {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const generatedId = useId();
  const inputId = id ?? generatedId;

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  const selectedDate = parseDateValue(value);
  const minDate = min ? parseDateValue(min) : undefined;
  const maxDate = max ? parseDateValue(max) : undefined;

  const disabledMatchers: Matcher[] = [];
  if (minDate) disabledMatchers.push({ before: minDate });
  if (maxDate) disabledMatchers.push({ after: maxDate });
  if (isDateDisabled) disabledMatchers.push(isDateDisabled);

  const handleSelect = (date: Date | undefined) => {
    onChange(date ? formatDateValue(date) : '');
    setOpen(false);
    triggerRef.current?.focus();
  };

  return (
    <div className="date-picker-wrapper" style={style} ref={wrapperRef}>
      <input
        type="date"
        id={inputId}
        className="visually-hidden"
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
      <button
        type="button"
        ref={triggerRef}
        className={`date-picker-trigger ${className ?? ''}`}
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={selectedDate ? undefined : placeholder}
      >
        <span className={selectedDate ? undefined : 'date-picker-placeholder'}>
          {selectedDate ? formatDisplayValue(selectedDate) : placeholder}
        </span>
        <span className="date-picker-icon" aria-hidden="true">
          📅
        </span>
      </button>
      {open && (
        <div className="date-picker-popover" role="dialog" aria-label="Choose a date">
          <DayPicker
            mode="single"
            selected={selectedDate}
            defaultMonth={selectedDate ?? minDate ?? new Date()}
            onSelect={handleSelect}
            disabled={disabledMatchers}
            showOutsideDays
          />
        </div>
      )}
    </div>
  );
};

export default DatePicker;
