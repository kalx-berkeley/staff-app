import { useNavigate } from 'react-router-dom';
import { formatCalendarDate } from '../../common/dateTime';
import type { ShowResponse } from '../types';

/** "19:00:00" as "7:00 PM" (a Pacific wall-clock time, so no time zone). */
const formatClockTime = (timeStr: string): string => {
  const [hours, minutes] = timeStr.split(':');
  const hour = parseInt(hours);
  return `${hour % 12 || 12}:${minutes} ${hour >= 12 ? 'PM' : 'AM'}`;
};

const closedWhen = (
  show: Pick<ShowResponse, 'status' | 'planned_close_date' | 'planned_close_time'>,
): string => {
  if (show.status === 'closed') return 'has closed';
  if (show.status !== 'published') return "isn't open";
  if (show.planned_close_date && show.planned_close_time) {
    const date = formatCalendarDate(show.planned_close_date, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
    });
    return `closed at ${formatClockTime(show.planned_close_time)} on ${date}`;
  }
  return 'has closed';
};

/**
 * Tops the DJ show and giveaway pages, in place of the giveaway buttons, when
 * the show's passes can't be given away (`isDjGiveawayClosed`). A DJ can still
 * land here from an old tab, Back or the address bar, so the page has to say
 * so plainly before they announce passes KALX doesn't have.
 */
const GiveawayClosedNotice = ({
  show,
}: {
  show: Pick<ShowResponse, 'event_name' | 'status' | 'planned_close_date' | 'planned_close_time'>;
}) => {
  const navigate = useNavigate();
  return (
    <div className="dj-giveaway-closed" role="alert">
      <h2>Don&apos;t announce this show on air</h2>
      <p>
        The pass giveaway for <strong>{show.event_name}</strong> {closedWhen(show)}. There are no
        passes left to give away, so listeners who call in can&apos;t win.
      </p>
      <div className="dj-preassigned-gate-actions">
        <button onClick={() => navigate('/dj/shows')} className="btn-primary">
          ← Pick a different show
        </button>
      </div>
    </div>
  );
};

export default GiveawayClosedNotice;
