// /admin/analytics — métricas agregadas de interactions del proxy.
/* eslint-disable react/jsx-no-comment-textnodes */
import { getAdminSession } from "@/lib/admin-session";
import { prisma } from "@/lib/prisma";
import { padHourly } from "@/lib/volume-buckets";
import { AnalyticsPanel } from "./_components/analytics-panel";

export const dynamic = "force-dynamic";

export default async function AnalyticsPage() {
  const session = await getAdminSession();
  if (!session) return null;

  const since7d = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const orgId = session.orgId;

  const [byAction, aggregate, hourlyRows, topPoliciesRows] = await Promise.all([
    prisma.interaction.groupBy({
      by: ["action"],
      where: { orgId, createdAt: { gte: since7d } },
      _count: { action: true },
      _avg: { latencyTotalMs: true },
    }),

    prisma.interaction.aggregate({
      where: { orgId, createdAt: { gte: since7d } },
      _avg: { latencyTotalMs: true },
      _count: { id: true },
    }),

    prisma.$queryRaw<{ hour: Date; count: bigint }[]>`
      SELECT
        date_trunc('hour', created_at) AS hour,
        COUNT(*)::bigint AS count
      FROM interactions
      WHERE org_id = ${orgId}
        AND created_at >= ${since7d}
      GROUP BY 1
      ORDER BY 1 ASC
    `,

    prisma.$queryRaw<{ slug: string; count: bigint }[]>`
      SELECT
        hit->>'slug' AS slug,
        COUNT(*)::bigint AS count
      FROM interactions,
           jsonb_array_elements(policy_hits::jsonb) AS hit
      WHERE org_id = ${orgId}
        AND created_at >= ${since7d}
        AND jsonb_array_length(policy_hits::jsonb) > 0
      GROUP BY 1
      ORDER BY 2 DESC
      LIMIT 8
    `,
  ]);

  const actionMap = Object.fromEntries(
    byAction.map((r) => [
      r.action,
      { count: r._count.action, avgLatencyMs: Math.round(r._avg.latencyTotalMs ?? 0) },
    ]),
  );

  const initial = {
    range: "7d",
    total: Number(aggregate._count.id),
    avgLatencyMs: Math.round(aggregate._avg.latencyTotalMs ?? 0),
    byAction: {
      BLOCK:  actionMap["BLOCK"]  ?? { count: 0, avgLatencyMs: 0 },
      REDACT: actionMap["REDACT"] ?? { count: 0, avgLatencyMs: 0 },
      WARN:   actionMap["WARN"]   ?? { count: 0, avgLatencyMs: 0 },
      LOG:    actionMap["LOG"]    ?? { count: 0, avgLatencyMs: 0 },
    },
    hourly: padHourly(hourlyRows, since7d),
    topPolicies: topPoliciesRows.map((r) => ({ slug: r.slug, count: Number(r.count) })),
  };

  return (
    <section>
      <header className="mb-8 flex flex-col gap-2">
        <span className="font-mono text-xs uppercase tracking-wider text-graphite">
          // analíticas
        </span>
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
          Lo que sucede en la organización.
        </h1>
        <p className="max-w-2xl text-graphite-dark">
          Métricas agregadas de cada request que pasó por el proxy. Seleccioná el rango de tiempo.
        </p>
      </header>
      <AnalyticsPanel initial={initial} />
    </section>
  );
}
