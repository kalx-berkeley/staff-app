import { useEffect, useId, useRef, useState } from 'react';
import { DayPicker, type Matcher } from 'react-day-picker';
import 'react-day-picker/style.css';
import { parseDateValue, formatDateValue, formatDateForDisplay, parseFreeformDate } from '../../utils';

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
 * A date field: free-typed text (`MM/DD/YYYY`, parsed as you type — no
 * browser-imposed mm/dd/yyyy sub-fields or native calendar icon) paired with
 * a calendar popover button for mouse users who'd rather browse. Both stay
 * in sync with the same `value`.
 *
 * Text that isn't a real, in-range date commits `''` upstream instead of the
 * typed text, so a caller's existing "value is required" check also rejects
 * bad manual entry — the invalid text stays visible (with an error style)
 * until it's fixed or cleared.
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
  placeholder = 'MM/DD/YYYY',
  isDateDisabled,
}: DatePickerProps) => {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(() => formatDateForDisplay(value));
  const [invalid, setInvalid] = useState(false);
  const lastCommittedRef = useRef(value);
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

  useEffect(() => {
    // Only resync from an externally-driven value change (e.g. the parent
    // resetting the field) — a change we committed ourselves already has
    // matching local text, including the '' committed while showing invalid
    // typed text, which must stay on screen rather than being wiped here.
    if (value !== lastCommittedRef.current) {
      lastCommittedRef.current = value;
      setText(formatDateForDisplay(value));
      setInvalid(false);
    }
  }, [value]);

  const selectedDate = parseDateValue(value);
  const minDate = min ? parseDateValue(min) : undefined;
  const maxDate = max ? parseDateValue(max) : undefined;

  const disabledMatchers: Matcher[] = [];
  if (minDate) disabledMatchers.push({ before: minDate });
  if (maxDate) disabledMatchers.push({ after: maxDate });

  const commit = (raw: string, nextValue: string, isInvalid: boolean) => {
    setText(raw);
    setInvalid(isInvalid);
    lastCommittedRef.current = nextValue;
    onChange(nextValue);
  };

  const handleTextChange = (raw: string) => {
    const parsed = parseFreeformDate(raw);
    if (parsed === null) {
      commit(raw, '', true);
      return;
    }
    // Format/real-date validity only — min/max stay advisory here (as they
    // were for the native date input this replaced), so each caller's own
    // range validation still runs downstream instead of being pre-empted.
    commit(raw, parsed, false);
  };

  const handleSelect = (date: Date | undefined) => {
    const iso = date ? formatDateValue(date) : '';
    commit(iso ? formatDateForDisplay(iso) : '', iso, false);
    setOpen(false);
    toggleRef.current?.focus();
  };

  return (
    <div className="date-picker-wrapper" style={style} ref={wrapperRef}>
      <input
        type="text"
        inputMode="numeric"
        id={inputId}
        className={`date-picker-input ${className ?? ''}`}
        value={text}
        placeholder={placeholder}
        disabled={disabled}
        aria-label={id ? undefined : placeholder}
        aria-invalid={invalid || undefined}
        title={invalid ? `Enter a valid date as ${placeholder}` : undefined}
        onChange={(e) => handleTextChange(e.target.value)}
      />
      {text && !disabled && (
        <button
          type="button"
          className="date-picker-clear"
          aria-label="Clear date"
          title="Clear date"
          onClick={() => commit('', '', false)}
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
