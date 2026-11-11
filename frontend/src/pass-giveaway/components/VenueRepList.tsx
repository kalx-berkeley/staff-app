import type { VenueOwnerInfo } from '../types';

interface VenueRepListProps {
  reps: VenueOwnerInfo[];
}

/** A venue's KALX promotions reps, one per line, each with a mailto link. */
const VenueRepList = ({ reps }: VenueRepListProps) => {
  if (reps.length === 0) {
    return <span className="venue-reps-none">No rep</span>;
  }
  return (
    <ul className="venue-reps">
      {reps.map((rep) => (
        <li key={rep.email}>
          {rep.name && <span className="venue-rep-name">{rep.name}</span>}
          <a href={`mailto:${rep.email}`} className="venue-rep-email">
            {rep.email}
          </a>
        </li>
      ))}
    </ul>
  );
};

export default VenueRepList;
