import type { WheelchairAccessible } from '../types';

// The Yes/No check boxes on the DJ's show sheet. Unknown is spelled out
// instead, since neither box would be right.
export default function WheelchairAccessibleChecks({ value }: { value: WheelchairAccessible }) {
  if (value === 'unknown') return <>Unknown</>;
  return (
    <>
      Yes {value === 'yes' ? '☑' : '☐'}
      {'   '}
      No {value === 'no' ? '☑' : '☐'}
    </>
  );
}
