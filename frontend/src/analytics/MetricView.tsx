import { lazy, Suspense } from 'react';
import ExplanationPopover from './ExplanationPopover';
import { formatValue } from './format';
import Heatmap from './Heatmap';
import { BalanceBar } from './MetricTable';
import MetricTable from './MetricTable';
import type { Metric, StatMetric } from './types';

// Recharts is only downloaded when a page has a chart
const MetricChart = lazy(() => import('./MetricChart'));

function Title({ metric }: { metric: Metric }) {
  return (
    <h3 className="analytics-metric-title">
      {metric.title}
      <ExplanationPopover title={metric.title} explanation={metric.explanation} />
    </h3>
  );
}

export function StatCard({ metric }: { metric: StatMetric }) {
  return (
    <div className="analytics-stat">
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

// One metric of any kind except stats, which StatCard shows.
export default function MetricView({ metric }: { metric: Metric }) {
  if (metric.kind === 'stat') return <StatCard metric={metric} />;
  return (
    <section className="analytics-metric">
      <Title metric={metric} />
      {metric.kind === 'table' && (
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
