import { useEffect, useId, useRef, useState } from 'react';
import { DayPicker, type Matcher } from 'react-day-picker';
import 'react-day-picker/style.css';
import { parseDateValue, formatDateValue } from '../../utils';

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
  /**
   * Dates to flag as unavailable (e.g. a schedule mismatch). These are shown
   * struck through in the calendar popover but remain selectable — only
   * `min`/`max` are hard limits. Pair this with a warning message next to
   * the field for when the caller picks a flagged date anyway.
   */
  isDateDisabled?: (date: Date) => boolean;
}

/**
 * A date field: a native `<input type="date">` (typeable, with every browser's
 * own keyboard entry and built-in clear affordance) paired with a calendar
 * popover button for mouse users who'd rather browse. Both stay in sync with
 * the same `value`.
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
  const toggleRef = useRef<HTMLButtonElement>(null);
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

  const handleSelect = (date: Date | undefined) => {
    onChange(date ? formatDateValue(date) : '');
    setOpen(false);
    toggleRef.current?.focus();
  };

  return (
    <div className="date-picker-wrapper" style={style} ref={wrapperRef}>
      <input
        type="date"
        id={inputId}
        className={`date-picker-input ${className ?? ''}`}
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        aria-label={id ? undefined : placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      {value && !disabled && (
        <button
          type="button"
          className="date-picker-clear"
          aria-label="Clear date"
          title="Clear date"
          onClick={() => onChange('')}
        >
          ×
        </button>
      )}
      <button
        type="button"
        ref={toggleRef}
        className="date-picker-toggle"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label="Open calendar"
        title="Open calendar"
      >
        📅
      </button>
      {open && (
        <div className="date-picker-popover" role="dialog" aria-label="Choose a date">
          <DayPicker
            mode="single"
            selected={selectedDate}
            defaultMonth={selectedDate ?? minDate ?? new Date()}
            onSelect={handleSelect}
            disabled={disabledMatchers}
            modifiers={isDateDisabled ? { unavailable: isDateDisabled } : undefined}
            modifiersClassNames={{ unavailable: 'date-picker-day-unavailable' }}
            showOutsideDays
          />
          {isDateDisabled && (
            <p className="date-picker-legend">
              <span className="date-picker-legend-swatch" aria-hidden="true" />
              No on-air show scheduled — still selectable
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default DatePicker;
