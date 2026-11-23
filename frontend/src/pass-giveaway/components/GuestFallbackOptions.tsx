import type { GuestFallback } from '../types';

/**
 * Where the choice is made. It changes what "your guest has no pass" means:
 * - claim: a claimed pass whose guest can be bumped by another staff member
 * - lottery: a lottery entry, whose guest might not get a pass in the draw
 * - alternate: someone on the alternate list, who has no pass of their own yet
 */
export type GuestFallbackContext = 'claim' | 'lottery' | 'alternate';

/** The two answers that make up a guest fallback. */
const attendsAlone = (value: GuestFallback): boolean =>
  value === 'attend_alone' || value === 'wait';
const guestWaits = (value: GuestFallback): boolean =>
  value === 'wait' || value === 'wait_then_release';

const toFallback = (attends: boolean, waits: boolean): GuestFallback => {
  if (waits) return attends ? 'wait' : 'wait_then_release';
  return attends ? 'attend_alone' : 'release';
};

const SECOND_QUESTION: Record<GuestFallbackContext, string> = {
  claim: 'If another staff member bumps your guest, what should happen?',
  lottery:
    "If your guest doesn't get a pass in the draw, or is bumped by another staff member later, what should happen?",
  alternate: 'If a pass opens up for you but not for your guest, what should happen?',
};

/** What happens, in one sentence, for the answers given. */
const summarize = (context: GuestFallbackContext, value: GuestFallback, waitOnly: boolean): string => {
  const attends = attendsAlone(value);
  if (waitOnly) {
    return attends
      ? "Your guest starts on the alternate list. You'll go to the show either way."
      : "Your guest starts on the alternate list. If they still don't have a pass when the show closes, your pass is released too.";
  }
  if (context === 'alternate') {
    if (value === 'attend_alone') return "If a pass opens up for you but not your guest, you'll get it and go without them.";
    if (value === 'release') return "If a pass opens up for you but not your guest, you'll be skipped until there's a pass for both of you.";
    if (value === 'wait') {
      return "If a pass opens up for you but not your guest, you'll get it and your guest goes on the alternate list. You'll go either way.";
    }
    return "If a pass opens up for you but not your guest, you'll get it and your guest goes on the alternate list. If they still don't have a pass when the show closes, your pass is released.";
  }
  const when = context === 'lottery' ? "If your guest doesn't get a pass or is bumped" : 'If your guest is bumped';
  if (value === 'attend_alone') return `${when}, we'll email you right away and you'll go without them.`;
  if (value === 'release') return `${when}, we'll release your pass too and email you right away.`;
  if (value === 'wait') return `${when}, they go on the alternate list. You'll go either way.`;
  return `${when}, they go on the alternate list. If they still don't have a pass when the show closes, your pass is released too.`;
};

interface GuestFallbackOptionsProps {
  /** Prefix for the radio group names and ids; must be unique on the page. */
  name: string;
  context: GuestFallbackContext;
  value: GuestFallback;
  onChange: (value: GuestFallback) => void;
  disabled?: boolean;
  /** There's no pass free for the guest, so they start on the alternate list and only the first question applies. */
  waitOnly?: boolean;
}

/**
 * The choice of what happens if a +1 guest has no pass, asked as two questions:
 * whether the staff member goes without their guest, and whether the guest
 * waits on the alternate list or the staff member is told right away.
 */
const GuestFallbackOptions = ({
  name,
  context,
  value,
  onChange,
  disabled = false,
  waitOnly = false,
}: GuestFallbackOptionsProps) => {
  const attends = attendsAlone(value);
  const waits = waitOnly || guestWaits(value);
  const notifyTradeoffsId = `${name}-notify-tradeoffs`;
  const waitTradeoffsId = `${name}-wait-tradeoffs`;

  return (
    <div className="guest-fallback">
      {waitOnly && (
        <p className="field-hint">
          There's no pass free for your guest right now, so they'd start on the alternate list.
        </p>
      )}
      <fieldset className="form-group radio-group">
        <legend>Will you go to the show if your guest can't?</legend>
        <label className="radio-label">
          <input
            type="radio"
            name={`${name}-attends`}
            checked={attends}
            onChange={() => onChange(toFallback(true, waits))}
            disabled={disabled}
          />
          Yes, I'll go without them
        </label>
        <label className="radio-label">
          <input
            type="radio"
            name={`${name}-attends`}
            checked={!attends}
            onChange={() => onChange(toFallback(false, waits))}
            disabled={disabled}
          />
          {context === 'alternate'
            ? "No, skip me until there's a pass for both of us"
            : "No, release my pass if my guest can't go"}
        </label>
      </fieldset>
      {!waitOnly && (
        <fieldset className="form-group radio-group">
          <legend>{SECOND_QUESTION[context]}</legend>
          <div className="guest-fallback-group">
            <label className="radio-label">
              <input
                type="radio"
                name={`${name}-waits`}
                checked={!waits}
                onChange={() => onChange(toFallback(attends, false))}
                disabled={disabled}
                aria-describedby={notifyTradeoffsId}
              />
              Let me know right away that my guest can't go
            </label>
            <p id={notifyTradeoffsId} className="guest-fallback-tradeoffs">
              <strong>Pro:</strong> You'll know right away, instead of waiting until the show closes to find out.
              <br />
              <strong>Con:</strong> Your guest can't get a pass that opens up later.
            </p>
          </div>
          <div className="guest-fallback-group">
            <label className="radio-label">
              <input
                type="radio"
                name={`${name}-waits`}
                checked={waits}
                onChange={() => onChange(toFallback(attends, true))}
                disabled={disabled}
                aria-describedby={waitTradeoffsId}
              />
              Put my guest on the alternate list
            </label>
            <p id={waitTradeoffsId} className="guest-fallback-tradeoffs">
              <strong>Pro:</strong> Your guest could still get a pass if one opens up before the show closes.
              <br />
              <strong>Con:</strong> You won't know whether your guest can go until the show closes.
            </p>
          </div>
        </fieldset>
      )}
      <p className="guest-fallback-summary" aria-live="polite">
        {summarize(context, value, waitOnly)}
      </p>
    </div>
  );
};

export default GuestFallbackOptions;
