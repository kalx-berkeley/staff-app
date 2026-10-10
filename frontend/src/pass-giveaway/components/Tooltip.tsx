import { useState, useEffect, useRef } from 'react';

interface TooltipProps {
  text: string;
}

const Tooltip = ({ text }: TooltipProps) => {
  const [pinned, setPinned] = useState(false);
  const wrapperRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!pinned) return;
    const handleOutside = (e: PointerEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) {
        setPinned(false);
      }
    };
    document.addEventListener('pointerdown', handleOutside);
    return () => document.removeEventListener('pointerdown', handleOutside);
  }, [pinned]);

  return (
    <span className={`tooltip-wrapper${pinned ? ' tooltip-pinned' : ''}`} ref={wrapperRef}>
      <button
        type="button"
        className="tooltip-trigger"
        aria-label="More information"
        onFocus={() => setPinned(true)}
        onBlur={() => setPinned(false)}
        onClick={(e) => {
          e.stopPropagation();
          setPinned((v) => !v);
        }}
      >
        ?
      </button>
      <span className="tooltip-box" role="tooltip">
        {text}
      </span>
    </span>
  );
};

export default Tooltip;
