import { useEffect, useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { usePageTitle } from '../common/hooks/usePageTitle';
import type { APIError } from '../common/types';
import { analyticsAPI } from './api';
import type { LayoutContext } from './AnalyticsLayout';
import MetricView, { StatCard } from './MetricView';
import { readWindow } from './timeWindow';
import type { AnalyticsTab, Metric, StatMetric, TabResponse } from './types';

export const ANALYTICS_TITLE = 'KALX Staff Analytics';

/** Consecutive stats share a row of cards; every other metric gets its own row. */
function groupMetrics(metrics: Metric[]): (Metric | StatMetric[])[] {
  const groups: (Metric | StatMetric[])[] = [];
  for (const metric of metrics) {
    const last = groups[groups.length - 1];
    if (metric.kind === 'stat') {
      if (Array.isArray(last)) last.push(metric);
      else groups.push([metric]);
    } else {
      groups.push(metric);
    }
  }
  return groups;
}

// One analytics page: fetches its tab's metrics for the window in the URL and
// shows them. Venue and DJ pages pass the venue or DJ as *params*.
export default function TabPage({
  tab,
  heading,
  params,
  intro,
}: {
  tab: AnalyticsTab;
  heading: string;
  params?: Record<string, string>;
  intro?: string;
}) {
  const [search] = useSearchParams();
  const { setResolvedWindow } = useOutletContext<LayoutContext>();
  const [data, setData] = useState<TabResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const windowKey = JSON.stringify(readWindow(search));
  const paramsKey = JSON.stringify(params ?? {});

  usePageTitle(data?.title ?? heading, ANALYTICS_TITLE);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    analyticsAPI
      .getTab(tab, JSON.parse(windowKey), JSON.parse(paramsKey))
      .then((response) => {
        if (cancelled) return;
        setData(response);
        setResolvedWindow(response.window);
      })
      .catch((err: APIError) => {
        if (cancelled) return;
        setError(typeof err?.detail === 'string' ? err.detail : 'Failed to load the metrics');
      });
    return () => {
      cancelled = true;
    };
  }, [tab, windowKey, paramsKey, setResolvedWindow]);

  return (
    <div className="analytics-tab">
      <h2>{data?.title ?? heading}</h2>
      {intro && <p className="field-hint">{intro}</p>}
      {error ? (
        <div className="error-message">{error}</div>
      ) : data === null ? (
        <p>Loading…</p>
      ) : data.metrics.length === 0 ? (
        <p className="analytics-empty">There's nothing to show here.</p>
      ) : (
        groupMetrics(data.metrics).map((group) =>
          Array.isArray(group) ? (
            <div className="analytics-stats" key={group[0].id}>
              {group.map((m) => (
                <StatCard key={m.id} metric={m} />
              ))}
            </div>
          ) : (
            <MetricView key={group.id} metric={group} />
          ),
        )
      )}
    </div>
  );
}
