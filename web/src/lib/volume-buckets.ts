// Pad an hourly aggregation so every hour in [since, now] appears as a
// bucket — Postgres only returns rows for hours that actually had traffic,
// which makes the sparkline lie about the time axis (5 sparse hours over
// 7 days end up evenly spaced as if they were consecutive).

const HOUR_MS = 60 * 60 * 1000;

export type HourlyBucket = { hour: string; count: number };

export function padHourly(
  rows: { hour: Date; count: bigint | number }[],
  since: Date,
  now: Date = new Date(),
): HourlyBucket[] {
  // Snap both ends to the hour boundary. since is inclusive, now is the
  // last bucket the user is currently inside.
  const startMs = Math.floor(since.getTime() / HOUR_MS) * HOUR_MS;
  const endMs = Math.floor(now.getTime() / HOUR_MS) * HOUR_MS;
  const counts = new Map<number, number>();
  for (const r of rows) {
    counts.set(r.hour.getTime(), Number(r.count));
  }
  const out: HourlyBucket[] = [];
  for (let t = startMs; t <= endMs; t += HOUR_MS) {
    out.push({ hour: new Date(t).toISOString(), count: counts.get(t) ?? 0 });
  }
  return out;
}
