// On-demand POST endpoint to trigger the AI Suggestor for the current admin's org.
// POST /api/admin/suggestor/run
// Body: { lookbackDays?: number, dryRun?: boolean }

import type { NextRequest } from "next/server";
import { requireAdminRole } from "@/lib/admin-session";
import { runSuggestor } from "@/lib/suggestor";

export async function POST(request: NextRequest) {
  const auth = await requireAdminRole();
  if (!auth.ok) return auth.response;
  const session = auth.session;

  let lookbackDays: number | undefined;
  let dryRun: boolean | undefined;

  try {
    const body = await request.json().catch(() => ({})) as {
      lookbackDays?: unknown;
      dryRun?: unknown;
    };
    if (typeof body.lookbackDays === "number") lookbackDays = body.lookbackDays;
    if (typeof body.dryRun === "boolean") dryRun = body.dryRun;
  } catch {
    // body is optional — proceed with defaults
  }

  try {
    const result = await runSuggestor(session.orgId, { lookbackDays, dryRun });
    return Response.json({ ok: true, ...result });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Error interno del suggestor";
    console.error("[api/admin/suggestor/run]", err);
    return Response.json(
      { ok: false, error: message },
      { status: 500 }
    );
  }
}
