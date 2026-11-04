import type { GuestFallback } from '../types';

interface GuestFallbackOption {
  value: GuestFallback;
  label: string;
}

/** Options that share the same tradeoffs, shown together. */
interface GuestFallbackGroup {
  options: GuestFallbackOption[];
  pro: string;
  con: string;
}

const ATTEND_ALONE: GuestFallbackOption = {
  value: 'attend_alone',
  label: "I'll still attend without them",
};

const RELEASE: GuestFallbackOption = {
  value: 'release',
  label: 'Release my pass too (cancel both)',
};

// The same choice for someone still waiting for their own pass.
const SKIP_UNTIL_BOTH: GuestFallbackOption = {
  value: 'release',
  label: "Skip me until there's a pass for both of us",
};

const WAIT: GuestFallbackOption = {
  value: 'wait',
  label: "Put them on the alternate list, and I'll attend either way",
};

const WAIT_THEN_RELEASE: GuestFallbackOption = {
  value: 'wait_then_release',
  label: "Put them on the alternate list, but release my pass if they don't have one when the show closes",
};

const noWaitGroup = (forAlternate: boolean): GuestFallbackGroup => ({
  options: [ATTEND_ALONE, forAlternate ? SKIP_UNTIL_BOTH : RELEASE],
  pro: "You'll know immediately if your guest can't attend.",
  con: "You won't be able to take advantage of a potential additional pass becoming available for them later.",
});

const WAIT_GROUP: GuestFallbackGroup = {
  options: [WAIT, WAIT_THEN_RELEASE],
  pro: 'Your guest might still get to go if another pass becomes available.',
  con: "You won't know if your guest can go until the show closes.",
};

interface GuestFallbackOptionsProps {
  /** Shared radio group name; must be unique on the page. */
  name: string;
  legend: string;
  value: GuestFallback;
  onChange: (value: GuestFallback) => void;
  disabled?: boolean;
  /** There's no pass free for the guest, so only the options that can wait apply. */
  waitOnly?: boolean;
  /** The form is for someone on the alternate list, who has no pass to release. */
  forAlternate?: boolean;
}

/** The choice of what happens if a +1 guest has no pass, with the tradeoffs of each group of options. */
const GuestFallbackOptions = ({
  name,
  legend,
  value,
  onChange,
  disabled = false,
  waitOnly = false,
  forAlternate = false,
}: GuestFallbackOptionsProps) => {
  const groups = waitOnly ? [WAIT_GROUP] : [noWaitGroup(forAlternate), WAIT_GROUP];

  return (
    <fieldset className="form-group radio-group">
      <legend>{legend}</legend>
      {waitOnly && (
        <p className="field-hint">
          There's no pass free for your guest right now, so they'd start on the alternate list.
        </p>
      )}
      {groups.map((group, index) => {
        const tradeoffsId = `${name}-tradeoffs-${index}`;
        return (
          <div key={tradeoffsId} className="guest-fallback-group">
            {group.options.map((option) => (
              <label key={option.value} className="radio-label">
                <input
                  type="radio"
                  name={name}
                  checked={value === option.value}
                  onChange={() => onChange(option.value)}
                  disabled={disabled}
                  aria-describedby={tradeoffsId}
                />
                {' '}{option.label}
              </label>
            ))}
            <p id={tradeoffsId} className="guest-fallback-tradeoffs">
              <strong>Pro:</strong> {group.pro}
              <br />
              <strong>Con:</strong> {group.con}
            </p>
          </div>
        );
      })}
    </fieldset>
  );
};

export default GuestFallbackOptions;
