import { Fragment } from 'react';
import type { DirectoryEntry } from './types';
import { DJ_INELIGIBLE_NOTES, djIneligibility } from './djEligibility';
import { spinitronUrl } from './directorySearch';

// A staff member's DJ names, each linking to its Spinitron page. Falls back to
// the plain DJ name when it can't be matched up with Spinitron personas.
// With greyIneligible (the table), DJs who can't sub right now are greyed out
// and unlinked; the detail panel links them and explains why instead.
const DjNames = ({ entry, greyIneligible = false }: { entry: DirectoryEntry; greyIneligible?: boolean }) => {
  const ineligible = djIneligibility(entry);
  if (greyIneligible && ineligible) {
    return (
      <span className="dj-names-ineligible" title={DJ_INELIGIBLE_NOTES[ineligible]}>
        {entry.dj_name}
      </span>
    );
  }
  if (entry.dj_personas.length === 0) return <>{entry.dj_name}</>;
  return (
    <>
      {entry.dj_personas.map((persona, index) => (
        <Fragment key={persona.id}>
          {index > 0 && ', '}
          <a href={spinitronUrl(persona.id)} target="_blank" rel="noreferrer">{persona.name}</a>
        </Fragment>
      ))}
    </>
  );
};

export default DjNames;
