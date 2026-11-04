import type { GuestFallback } from '../types';

interface GuestFallbackOption {
  value: GuestFallback;
  label: string;
  pro: string;
  con: string;
}

const ATTEND_ALONE: GuestFallbackOption = {
  value: 'attend_alone',
  label: "I'll still attend without them",
  pro: 'You keep your pass.',
  con: "If your guest loses their pass, they won't automatically get another chance.",
};

const RELEASE: GuestFallbackOption = {
  value: 'release',
  label: 'Release my pass too (cancel both)',
  pro: 'If your guest loses their pass, you find out right away and can make other plans.',
  con: 'You lose your pass at that moment, even if another pass frees up later.',
};

// The same choice for someone still waiting for their own pass.
const SKIP_UNTIL_BOTH: GuestFallbackOption = {
  value: 'release',
  label: "Skip me until there's a pass for both of us",
  pro: "You only get a pass if there's one for your guest too.",
  con: "You're skipped until two passes are free at once, so you may never get one.",
};

const WAIT: GuestFallbackOption = {
  value: 'wait',
  label: "Put them on the alternate list, and I'll attend either way",
  pro: 'You keep your pass, and your guest can still get one until the show closes.',
  con: 'You may not know if your guest can come until the show closes, and staff get freed passes first.',
};

const WAIT_THEN_RELEASE: GuestFallbackOption = {
  value: 'wait_then_release',
  label: "Put them on the alternate list, but release my pass if they don't have one when the show closes",
  pro: 'You only go if you can go together, and your guest can still get a pass until the show closes.',
  con: 'You may not find out until the show closes, and you could lose your pass at that point, with no time to make other plans.',
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

/** The choice of what happens if a +1 guest has no pass, with each option's tradeoffs. */
const GuestFallbackOptions = ({
  name,
  legend,
  value,
  onChange,
  disabled = false,
  waitOnly = false,
  forAlternate = false,
}: GuestFallbackOptionsProps) => {
  const options = waitOnly
    ? [WAIT, WAIT_THEN_RELEASE]
    : [ATTEND_ALONE, forAlternate ? SKIP_UNTIL_BOTH : RELEASE, WAIT, WAIT_THEN_RELEASE];

  return (
    <fieldset className="form-group radio-group">
      <legend>{legend}</legend>
      {waitOnly && (
        <p className="field-hint">
          There's no pass free for your guest right now, so they'd start on the alternate list.
        </p>
      )}
      {options.map((option) => (
        <div key={option.value} className="guest-fallback-option">
          <label className="radio-label">
            <input
              type="radio"
              name={name}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              disabled={disabled}
            />
            {' '}{option.label}
          </label>
          <p className="guest-fallback-tradeoffs">
            <strong>Pro:</strong> {option.pro}
            <br />
            <strong>Con:</strong> {option.con}
          </p>
        </div>
      ))}
    </fieldset>
  );
};

export default GuestFallbackOptions;
