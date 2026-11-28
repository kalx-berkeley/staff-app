import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import ExplanationPopover from './ExplanationPopover';
import { formatValue } from './format';
import Heatmap from './Heatmap';
import { BalanceBar } from './MetricTable';
import MetricTable from './MetricTable';
import { anchorId, sectionLink } from './timeWindow';
import type { Metric, StatMetric, TableMetric } from './types';

// Recharts is only downloaded when a page has a chart
const MetricChart = lazy(() => import('./MetricChart'));

// A "#" link to the metric's section, which also copies the section's full
// URL (window included) so it can be shared.
function SectionLink({ metric }: { metric: Metric }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const anchor = anchorId(metric.id);
  useEffect(() => () => clearTimeout(timer.current), []);

  const copy = () => {
    // The browser follows the link to the section; this copies it as well
    navigator.clipboard
      ?.writeText(sectionLink(anchor))
      .then(() => {
        setCopied(true);
        clearTimeout(timer.current);
        timer.current = setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {});
  };

  return (
    <>
      <a
        className="analytics-anchor"
        href={`#${anchor}`}
        onClick={copy}
        aria-label={`Link to "${metric.title}" (copies the link)`}
        title="Link to this section (copies the link)"
      >
        #
      </a>
      {copied && (
        <span className="analytics-anchor-copied" role="status">
          Link copied
        </span>
      )}
    </>
  );
}

function Title({ metric }: { metric: Metric }) {
  return (
    <h3 className="analytics-metric-title">
      {metric.title}
      <ExplanationPopover title={metric.title} explanation={metric.explanation} />
      <SectionLink metric={metric} />
    </h3>
  );
}

export function StatCard({ metric }: { metric: StatMetric }) {
  return (
    <div className="analytics-stat" id={anchorId(metric.id)}>
      <Title metric={metric} />
      <div className="analytics-stat-value">
        {metric.format === 'points' && typeof metric.value === 'number' ? (
          <BalanceBar value={metric.value} />
        ) : (
          formatValue(metric.value, metric.format)
        )}
      </div>
      {metric.note && <div className="analytics-stat-note">{metric.note}</div>}
    </div>
  );
}

// A table hidden behind a "Show" button until it's expanded.
function CollapsedTable({ metric }: { metric: TableMetric }) {
  const { hash } = useLocation();
  // A link to this section opens it
  const [open, setOpen] = useState(hash === `#${anchorId(metric.id)}`);
  const count = metric.rows.length;
  if (count === 0) return <p className="analytics-empty">None in this time window.</p>;
  return (
    <>
      <button
        type="button"
        className="btn-secondary btn-small"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? 'Hide' : `Show all ${count}`}
      </button>
      {open && (
        <MetricTable columns={metric.columns} rows={metric.rows} top={metric.top} label={metric.title} />
      )}
    </>
  );
}

// One metric of any kind except stats, which StatCard shows.
export default function MetricView({ metric }: { metric: Metric }) {
  if (metric.kind === 'stat') return <StatCard metric={metric} />;
  return (
    <section className="analytics-metric" id={anchorId(metric.id)}>
      <Title metric={metric} />
      {metric.kind === 'table' && metric.collapsed && <CollapsedTable metric={metric} />}
      {metric.kind === 'table' && !metric.collapsed && (
        <MetricTable columns={metric.columns} rows={metric.rows} top={metric.top} label={metric.title} />
      )}
      {metric.kind === 'series' && (
        <Suspense fallback={<p className="analytics-empty">Loading chart…</p>}>
          <MetricChart metric={metric} />
        </Suspense>
      )}
      {metric.kind === 'heatmap' && <Heatmap metric={metric} />}
    </section>
  );
}
