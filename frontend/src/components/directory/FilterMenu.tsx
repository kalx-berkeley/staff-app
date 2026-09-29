import { useEffect, useRef } from 'react';

interface FilterMenuProps {
  label: string;
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

// A dropdown of checkboxes for picking any number of values to filter by.
// Selecting nothing means no filtering.
const FilterMenu = ({ label, options, selected, onChange }: FilterMenuProps) => {
  const detailsRef = useRef<HTMLDetailsElement>(null);

  // Close when clicking outside or pressing Escape, like a native select.
  useEffect(() => {
    const details = detailsRef.current;
    if (!details) return;
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent ? event.key === 'Escape' : !details.contains(event.target as Node)) {
        details.open = false;
      }
    };
    document.addEventListener('click', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('click', close);
      document.removeEventListener('keydown', close);
    };
  }, []);

  const toggle = (option: string) => {
    onChange(
      selected.includes(option)
        ? selected.filter((value) => value !== option)
        : [...selected, option],
    );
  };

  return (
    <details className="filter-menu" ref={detailsRef}>
      <summary className={selected.length > 0 ? 'filter-menu-active' : undefined}>
        {label}
        {selected.length > 0 && <span className="filter-menu-count">{selected.length}</span>}
      </summary>
      <div className="filter-menu-options" role="group" aria-label={`Filter by ${label.toLowerCase()}`}>
        {options.map((option) => (
          <label key={option}>
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => toggle(option)}
            />
            {option}
          </label>
        ))}
        {selected.length > 0 && (
          <button type="button" className="filter-menu-clear" onClick={() => onChange([])}>
            Clear
          </button>
        )}
      </div>
    </details>
  );
};

export default FilterMenu;
