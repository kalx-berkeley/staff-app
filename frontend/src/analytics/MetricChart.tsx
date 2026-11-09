import { useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatValue } from './format';
import MetricTable from './MetricTable';
import type { SeriesMetric } from './types';

// Series colours, distinguishable from each other and on white
const COLORS = ['#2f6fb3', '#d9822b', '#2e9e6a', '#9b59b6', '#c0392b'];

// A line or bar chart, with a toggle to the same numbers as a table.
export default function MetricChart({ metric }: { metric: SeriesMetric }) {
  const [asTable, setAsTable] = useState(false);

  if (metric.rows.length === 0) {
    return <p className="analytics-empty">Nothing in this time window.</p>;
  }

  const Chart = metric.chart === 'bar' ? BarChart : LineChart;
  const tick = (value: unknown) => formatValue(value, metric.x.format);

  return (
    <div className="analytics-chart">
      <div className="analytics-chart-toggle">
        <button
          type="button"
          className="btn-secondary btn-small"
          aria-pressed={asTable}
          onClick={() => setAsTable((t) => !t)}
        >
          {asTable ? 'Show chart' : 'Show table'}
        </button>
      </div>
      {asTable ? (
        <MetricTable columns={[metric.x, ...metric.series]} rows={metric.rows} label={metric.title} />
      ) : (
        <div className="analytics-chart-area" role="img" aria-label={`${metric.title} chart`}>
          <ResponsiveContainer width="100%" height={260}>
            <Chart data={metric.rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#e5e7eb" vertical={false} />
              <XAxis dataKey={metric.x.key} tickFormatter={tick} minTickGap={24} fontSize={12} />
              <YAxis allowDecimals={false} fontSize={12} width={40} />
              <Tooltip labelFormatter={tick} />
              {metric.series.length > 1 && <Legend />}
              {metric.series.map((s, i) =>
                metric.chart === 'bar' ? (
                  <Bar key={s.key} dataKey={s.key} name={s.label} fill={COLORS[i % COLORS.length]} maxBarSize={48} />
                ) : (
                  <Line
                    key={s.key}
                    dataKey={s.key}
                    name={s.label}
                    stroke={COLORS[i % COLORS.length]}
                    strokeWidth={2}
                    dot={metric.rows.length < 40}
                  />
                ),
              )}
            </Chart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
