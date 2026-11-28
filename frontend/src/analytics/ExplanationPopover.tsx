import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { formatValue } from './format';
import type { Explanation } from './types';

const POPOVER_WIDTH_REM = 22;

// An ⓘ button that opens a popover. The popover is fixed to the viewport, so a
// table's scrolling wrapper can't clip it; it closes on scroll, Escape or a
// click elsewhere.
export function InfoPopover({ label, children }: { label: string; children: ReactNode }) {
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const ref = useRef<HTMLSpanElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const id = useId();
  const open = position !== null;

  useEffect(() => {
    if (!open) return;
    const close = () => setPosition(null);
    const onPointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
    };
  }, [open]);

  const toggle = () => {
    if (open) {
      setPosition(null);
      return;
    }
    const rect = buttonRef.current?.getBoundingClientRect();
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const width = Math.min(POPOVER_WIDTH_REM * rem, window.innerWidth * 0.8);
    const left = Math.max(8, Math.min((rect?.left ?? 0) - 8, window.innerWidth - width - 8));
    setPosition({ top: (rect?.bottom ?? 0) + 4, left });
  };

  return (
    <span className="analytics-explain" ref={ref}>
      <button
        type="button"
        ref={buttonRef}
        className="analytics-explain-button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={toggle}
      >
        ⓘ
      </button>
      {position && (
        <div
          className="analytics-explain-popover"
          id={id}
          role="dialog"
          aria-label={label}
          style={{ top: position.top, left: position.left }}
        >
          {children}
        </div>
      )}
    </span>
  );
}

// The ⓘ button next to a metric's title, which shows how it's calculated.
export default function ExplanationPopover({
  title,
  explanation,
}: {
  title: string;
  explanation: Explanation;
}) {
  return (
    <InfoPopover label={`How "${title}" is calculated`}>
      <p>{explanation.formula}</p>
      <dl>
        <dt>Time window uses</dt>
        <dd>{explanation.date_basis}</dd>
        {explanation.includes && (
          <>
            <dt>Includes</dt>
            <dd>{explanation.includes}</dd>
          </>
        )}
        {explanation.excludes && (
          <>
            <dt>Leaves out</dt>
            <dd>{explanation.excludes}</dd>
          </>
        )}
        {explanation.data_since !== undefined && explanation.data_since !== null && (
          <>
            <dt>Tracked since</dt>
            <dd>{formatValue(explanation.data_since, 'date')}</dd>
          </>
        )}
      </dl>
    </InfoPopover>
  );
}
