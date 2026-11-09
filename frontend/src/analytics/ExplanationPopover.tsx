import { useEffect, useId, useRef, useState } from 'react';
import { formatValue } from './format';
import type { Explanation } from './types';

// The ⓘ button next to a metric's title, which shows how it's calculated.
export default function ExplanationPopover({
  title,
  explanation,
}: {
  title: string;
  explanation: Explanation;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <span className="analytics-explain" ref={ref}>
      <button
        type="button"
        className="analytics-explain-button"
        aria-label={`How "${title}" is calculated`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
      >
        ⓘ
      </button>
      {open && (
        <div className="analytics-explain-popover" id={id} role="dialog" aria-label={`How "${title}" is calculated`}>
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
        </div>
      )}
    </span>
  );
}
