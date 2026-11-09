import type { HeatmapMetric } from './types';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const HOURS = Array.from({ length: 24 }, (_, h) => h);

const hourLabel = (h: number) => (h === 0 ? '12a' : h < 12 ? `${h}a` : h === 12 ? '12p' : `${h - 12}p`);

// Hour-of-week counts: one row per weekday, one column per hour, darker for more.
export default function Heatmap({ metric }: { metric: HeatmapMetric }) {
  const values = new Map(metric.cells.map((c) => [`${c.weekday}-${c.hour}`, c.value]));
  const max = Math.max(0, ...metric.cells.map((c) => c.value));

  if (max === 0) {
    return <p className="analytics-empty">Nothing in this time window.</p>;
  }

  return (
    <div className="analytics-heatmap-wrapper">
      <table className="analytics-heatmap" aria-label={metric.title}>
        <thead>
          <tr>
            <th />
            {HOURS.map((h) => (
              <th key={h} scope="col">
                {h % 3 === 0 ? hourLabel(h) : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DAYS.map((day, d) => (
            <tr key={day}>
              <th scope="row">{day}</th>
              {HOURS.map((h) => {
                const value = values.get(`${d}-${h}`) ?? 0;
                return (
                  <td
                    key={h}
                    title={`${day} ${hourLabel(h)}: ${value}`}
                    style={{ background: value ? `rgba(47, 111, 179, ${0.15 + 0.85 * (value / max)})` : undefined }}
                  >
                    <span className="visually-hidden">{value}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
