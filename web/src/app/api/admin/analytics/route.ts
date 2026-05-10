// GET /api/admin/analytics?range=24h|7d|30d
import { getAdminSession } from "@/lib/admin-session";
import { prisma } from "@/lib/prisma";
import { padHourly } from "@/lib/volume-buckets";
import type { NextRequest } from "next/server";

const RANGES = { "24h": 1, "7d": 7, "30d": 30 } as const;
type Range = keyof typeof RANGES;

export async function GET(request: NextRequest) {
  const session = await getAdminSession();
  if (!session) return Response.json({ error: "unauthorized" }, { status: 401 });

  const rangeParam = (new URL(request.url).searchParams.get("range") ?? "7d") as Range;
  const days = RANGES[rangeParam] ?? 7;
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  const orgId = session.orgId;

  const [byAction, latencyRows, hourlyRows, topPoliciesRows] = await Promise.all([
    prisma.interaction.groupBy({
      by: ["action"],
      where: { orgId, createdAt: { gte: since } },
      _count: { action: true },
      _avg: { latencyTotalMs: true },
    }),

    prisma.interaction.aggregate({
      where: { orgId, createdAt: { gte: since } },
      _avg: { latencyTotalMs: true },
      _count: { id: true },
    }),

    prisma.$queryRaw<{ hour: Date; count: bigint }[]>`
      SELECT
        date_trunc('hour', created_at) AS hour,
        COUNT(*)::bigint AS count
      FROM interactions
      WHERE org_id = ${orgId}
        AND created_at >= ${since}
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
        AND created_at >= ${since}
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

  const hourly = padHourly(hourlyRows, since);

  const topPolicies = topPoliciesRows.map((r) => ({
    slug: r.slug,
    count: Number(r.count),
  }));

  return Response.json({
    range: rangeParam,
    total: Number(latencyRows._count.id),
    avgLatencyMs: Math.round(latencyRows._avg.latencyTotalMs ?? 0),
    byAction: {
      BLOCK: actionMap["BLOCK"] ?? { count: 0, avgLatencyMs: 0 },
      REDACT: actionMap["REDACT"] ?? { count: 0, avgLatencyMs: 0 },
      WARN: actionMap["WARN"] ?? { count: 0, avgLatencyMs: 0 },
      LOG: actionMap["LOG"] ?? { count: 0, avgLatencyMs: 0 },
    },
    hourly,
    topPolicies,
  });
}
