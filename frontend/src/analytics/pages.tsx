import { Link, useParams, useSearchParams } from 'react-router-dom';
import TabPage from './TabPage';
import { windowQuery } from './timeWindow';

export function OverviewPage() {
  return (
    <TabPage
      tab="overview"
      heading="Overview"
      intro="Radio Pass Giveaway metrics for the whole station. Click ⓘ next to any metric to see how it's calculated."
    />
  );
}

export function VenuesPage() {
  return <TabPage tab="venues" heading="Venues" intro="Click a venue for its own page." />;
}

function BackLink({ to, label }: { to: string; label: string }) {
  const [search] = useSearchParams();
  return (
    <Link className="analytics-back" to={`${to}${windowQuery(search)}`}>
      ← {label}
    </Link>
  );
}

export function VenuePage() {
  const { venueId = '' } = useParams();
  return (
    <>
      <BackLink to="/venues" label="All venues" />
      <TabPage tab="venue" heading="Venue" params={{ venue_id: venueId }} />
    </>
  );
}

export function DjsPage() {
  return <TabPage tab="djs" heading="DJs" intro="Click a DJ for their own page." />;
}

export function DjPage() {
  const { djKey = '' } = useParams();
  return (
    <>
      <BackLink to="/djs" label="All DJs" />
      <TabPage tab="dj" heading="DJ" params={{ dj: djKey }} />
    </>
  );
}

export function RepsPage() {
  return (
    <TabPage
      tab="reps"
      heading="Promotions reps"
      intro="Expand a row to see the shows. Highlighted shows were posted by someone who isn't one of the show's owners."
    />
  );
}

export function ShortLinksPage() {
  const [search] = useSearchParams();
  const slug = search.get('slug');
  return (
    <TabPage tab="short_links" heading="Short links" params={slug ? { slug } : undefined} />
  );
}

export function UsagePage() {
  return <TabPage tab="usage" heading="Site usage" />;
}
