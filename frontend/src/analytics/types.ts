/** KALX Staff Analytics types, matching backend/app/common/services/analytics_metrics.py. */

export type MetricFormat =
  | 'number'
  | 'percent'
  | 'points'
  | 'days'
  | 'hours'
  | 'date'
  | 'datetime'
  | 'text'
  | 'phone';

/** How a metric is calculated, shown in its ⓘ popover. */
export interface Explanation {
  formula: string;
  date_basis: string;
  includes: string | null;
  excludes: string | null;
  /** For tracked metrics: the first day there's data for (YYYY-MM-DD). */
  data_since: string | null;
}

export interface MetricColumn {
  key: string;
  label: string;
  format: MetricFormat;
  /** A path in the analytics site with {field} placeholders filled from the row. */
  link: string | null;
}

export interface MetricRow {
  [key: string]: unknown;
  /** Too few shows or visits to rank. */
  _low_sample?: boolean;
  /** Highlighted. */
  _flag?: boolean;
  /** A nested table, shown when the row is expanded. */
  _details?: { columns: MetricColumn[]; rows: MetricRow[] };
}

interface MetricBase {
  id: string;
  title: string;
  explanation: Explanation;
}

export interface StatMetric extends MetricBase {
  kind: 'stat';
  value: number | string | null;
  format: MetricFormat;
  note: string | null;
}

export interface TableMetric extends MetricBase {
  kind: 'table';
  columns: MetricColumn[];
  rows: MetricRow[];
  /** Rows shown before "Show all", or null for all of them. */
  top: number | null;
}

export interface SeriesMetric extends MetricBase {
  kind: 'series';
  x: MetricColumn;
  series: MetricColumn[];
  rows: MetricRow[];
  chart: 'line' | 'bar';
}

export interface HeatmapCell {
  /** 0 is Monday. */
  weekday: number;
  hour: number;
  value: number;
}

export interface HeatmapMetric extends MetricBase {
  kind: 'heatmap';
  cells: HeatmapCell[];
}

export type Metric = StatMetric | TableMetric | SeriesMetric | HeatmapMetric;

export interface AnalyticsWindow {
  start: string;
  end: string;
  preset: string | null;
  label: string;
}

export interface TabResponse {
  window: AnalyticsWindow;
  title: string | null;
  metrics: Metric[];
}

export type AnalyticsTab =
  | 'overview'
  | 'venues'
  | 'venue'
  | 'djs'
  | 'dj'
  | 'reps'
  | 'short_links'
  | 'usage';
