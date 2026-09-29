import { Fragment } from 'react';
import type { DirectoryEntry } from '../../types';
import { spinitronUrl } from './directorySearch';

// A staff member's DJ names, each linking to its Spinitron page. Falls back to
// the plain DJ name when it can't be matched up with Spinitron personas.
const DjNames = ({ entry }: { entry: DirectoryEntry }) => {
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
