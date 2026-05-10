// /admin — composite dashboard. The compliance officer's first stop:
// alignment score + 24 h KPIs + last 5 events + pending widgets.
/* eslint-disable react/jsx-no-comment-textnodes */
import Link from "next/link";

import { getAdminSession } from "@/lib/admin-session";
import { toEventDTO } from "@/lib/events";
import { prisma } from "@/lib/prisma";

import { type Action } from "@/components/ui";

export const dynamic = "force-dynamic";

// Same functional palette as analytics + events feed — keeps the
// compliance officer's mental model coherent across surfaces.
const ACTION_TONE: Record<Action, { tile: string; pill: string }> = {
  BLOCK:  { tile: "text-red-700",    pill: "bg-red-500/10 text-red-700" },
  REDACT: { tile: "text-amber-700",  pill: "bg-amber-500/10 text-amber-700" },
  WARN:   { tile: "text-orange-700", pill: "bg-orange-500/10 text-orange-700" },
  LOG:    { tile: "text-zinc-600",   pill: "bg-zinc-500/10 text-zinc-700" },
};

export default async function AdminHomePage() {
  const session = await getAdminSession();
  if (!session) return null;
  const { orgId } = session;
  const since24h = new Date(Date.now() - 24 * 60 * 60 * 1000);

  // Each query is wrapped so a single failure can't take down the whole
  // dashboard — the surface degrades gracefully and the user still sees
  // a useful page.
  const [
    byAction,
    aggregate,
    recentRows,
    pendingSuggestions,
    activeRulesCount,
    totalRulesCount,
    pendingMembersCount,
    activeMembersCount,
  ] = await Promise.all([
    prisma.interaction
      .groupBy({
        by: ["action"],
        where: { orgId, createdAt: { gte: since24h } },
        _count: { action: true },
      })
      .catch(() => [] as { action: string; _count: { action: number } }[]),
    prisma.interaction
      .aggregate({
        where: { orgId, createdAt: { gte: since24h } },
        _avg: { latencyTotalMs: true },
        _count: { id: true },
      })
      .catch(() => ({
        _avg: { latencyTotalMs: 0 },
        _count: { id: 0 },
      }) as { _avg: { latencyTotalMs: number | null }; _count: { id: number } }),
    prisma.interaction
      .findMany({
        where: { orgId },
        orderBy: { createdAt: "desc" },
        take: 5,
      })
      .catch(() => []),
    prisma.ruleSuggestion
      .count({ where: { orgId, status: "pending" } })
      .catch(() => 0),
    prisma.policy.count({ where: { orgId, isActive: true } }).catch(() => 0),
    prisma.policy.count({ where: { orgId } }).catch(() => 0),
    prisma.member
      .count({ where: { orgId, role: "dev", userId: null } })
      .catch(() => 0),
    prisma.member
      .count({ where: { orgId, role: "dev", userId: { not: null } } })
      .catch(() => 0),
  ]);

  const byActionMap: Record<string, number> = {};
  for (const row of byAction)
    byActionMap[row.action as string] = row._count.action;
  const total = Number(aggregate._count.id);
  const blocked = byActionMap.BLOCK ?? 0;
  const redacted = byActionMap.REDACT ?? 0;
  const warned = byActionMap.WARN ?? 0;
  const aligned = total - blocked;
  const score = total > 0 ? (aligned / total) * 100 : null;
  const avgLatency = Math.round(aggregate._avg.latencyTotalMs ?? 0);
  const events = recentRows.map(toEventDTO);

  return (
    <section className="flex flex-col gap-6 md:gap-8">
      <header className="flex flex-col gap-2">
        <span className="font-mono text-xs uppercase tracking-wider text-graphite">
          // inicio · últimas 24 h
        </span>
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          ¿Estamos alineados ahora?
        </h1>
        <p className="max-w-2xl text-sm text-graphite-dark md:text-base">
          {greetingFor(score, total)}
        </p>
      </header>

      <AlignmentHero
        score={score}
        total={total}
        aligned={aligned}
        blocked={blocked}
      />

      <div className="grid gap-px overflow-hidden border border-graphite-dark/20 bg-graphite-dark/15 md:grid-cols-4">
        <Kpi label="block · 24h" value={fmt(blocked)} tone={ACTION_TONE.BLOCK.tile} />
        <Kpi label="redact · 24h" value={fmt(redacted)} tone={ACTION_TONE.REDACT.tile} />
        <Kpi label="warn · 24h" value={fmt(warned)} tone={ACTION_TONE.WARN.tile} />
        <Kpi label="p50 latencia" value={`${avgLatency} ms`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <RecentEventsPanel events={events} />
        <PendingPanel
          pendingSuggestions={pendingSuggestions}
          activeRulesCount={activeRulesCount}
          totalRulesCount={totalRulesCount}
          pendingMembersCount={pendingMembersCount}
          activeMembersCount={activeMembersCount}
        />
      </div>
    </section>
  );
}

function greetingFor(score: number | null, total: number): string {
  if (total === 0) {
    return "Sin tráfico todavía. Cuando un dev mande el primer prompt vía proxy, aparece acá.";
  }
  if (score === null) return "Cargando datos…";
  if (score >= 95)
    return "Tráfico saludable. La mayoría de prompts pasa sin desvíos de policy.";
  if (score >= 80)
    return "Hay algunos desvíos detectados. Revisá las sugerencias y los eventos más recientes.";
  return "Atención: una porción significativa del tráfico se está bloqueando. Revisá las reglas y la cola de sugerencias.";
}

function fmt(n: number): string {
  return n.toLocaleString("es-AR");
}

// ---------------------------------------------------------------------------
// Alignment hero
// ---------------------------------------------------------------------------

function AlignmentHero({
  score,
  total,
  aligned,
  blocked,
}: {
  score: number | null;
  total: number;
  aligned: number;
  blocked: number;
}) {
  return (
    <div
      className="border border-graphite-dark/20 bg-paper p-5 md:p-6"
      style={{ borderRadius: "var(--radius)" }}
    >
      <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-graphite">
        // alineamiento · últimas 24 h
      </span>

      {score !== null ? (
        <div className="mt-4 flex flex-wrap items-end justify-between gap-4 md:mt-5">
          <div className="flex items-end gap-2">
            <span className="text-5xl font-semibold leading-none tracking-tighter text-ink sm:text-6xl md:text-7xl">
              {score.toFixed(1)}
            </span>
            <span className="pb-1.5 text-2xl font-medium leading-none text-graphite-dark md:text-3xl">
              %
            </span>
          </div>
          <p className="max-w-sm text-sm leading-relaxed text-graphite-dark">
            <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-ink">
              {fmt(aligned)} alineados / {fmt(total)} totales
            </span>
            <br />
            {blocked > 0
              ? `${fmt(blocked)} ${blocked === 1 ? "fue bloqueado" : "fueron bloqueados"} antes de llegar al modelo.`
              : "Ningún request fue bloqueado."}
          </p>
        </div>
      ) : (
        <p className="mt-4 font-mono text-xs text-graphite">
          // sin datos suficientes para calcular alineamiento
        </p>
      )}

      {score !== null ? (
        <div className="relative mt-4 h-1.5 w-full bg-paper-soft md:mt-5">
          <div
            className="absolute inset-y-0 left-0 bg-ink"
            style={{ width: `${Math.max(score, 1)}%` }}
          />
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI tile
// ---------------------------------------------------------------------------

function Kpi({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5 bg-paper p-4 md:p-5">
      <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-graphite">
        // {label}
      </span>
      <span
        className={`text-xl font-semibold tracking-tight md:text-2xl ${tone ?? "text-ink"}`}
      >
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent events panel — compact log strip
// ---------------------------------------------------------------------------

type EventDTO = ReturnType<typeof toEventDTO>;

function RecentEventsPanel({ events }: { events: EventDTO[] }) {
  return (
    <div
      className="flex flex-col border border-graphite-dark/20 bg-paper"
      style={{ borderRadius: "var(--radius)" }}
    >
      <header className="flex items-baseline justify-between border-b border-graphite-dark/15 px-5 py-3">
        <span className="font-mono text-xs uppercase tracking-[0.22em] text-graphite">
          // últimos eventos
        </span>
        <Link
          href="/admin/events"
          className="font-mono text-[11px] uppercase tracking-[0.22em] text-ink underline-offset-4 hover:underline"
        >
          ver feed completo →
        </Link>
      </header>
      {events.length === 0 ? (
        <p className="px-5 py-6 font-mono text-xs text-graphite">
          // sin eventos. mandá un request al proxy y va a aparecer acá.
        </p>
      ) : (
        <ul className="divide-y divide-graphite-dark/10">
          {events.map((e) => (
            <li key={e.id} className="flex flex-col gap-1.5 px-5 py-2.5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span
                  className={`px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider ${ACTION_TONE[e.action as Action].pill}`}
                >
                  {e.action}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-graphite">
                  {timeAgo(e.createdAt)} · {e.latencyTotalMs}ms ·{" "}
                  {e.policyHits?.[0]?.slug ?? "—"}
                </span>
              </div>
              <p className="line-clamp-1 font-mono text-xs text-graphite-dark">
                {previewPrompt(e.prompt)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function previewPrompt(prompt: string): string {
  let text = prompt;
  try {
    const parsed = JSON.parse(prompt) as {
      messages?: { role?: string; content?: unknown }[];
    };
    const lastUser = parsed.messages
      ?.slice()
      .reverse()
      .find((m) => m.role === "user");
    if (lastUser) {
      const content = lastUser.content;
      if (typeof content === "string") text = content;
      else if (Array.isArray(content)) {
        const block = (content as { type?: string; text?: string }[]).find(
          (b) => b.type === "text" && typeof b.text === "string",
        );
        if (block?.text) text = block.text;
      }
    }
  } catch {
    // not JSON, leave as is
  }
  text = text.replace(/\s+/g, " ").trim();
  return text.length > 120 ? `${text.slice(0, 117)}…` : text;
}

function timeAgo(iso: string): string {
  const t = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - t);
  if (diff < 60_000) return "ahora";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
  return `${Math.floor(diff / 86_400_000)}d`;
}

// ---------------------------------------------------------------------------
// Pending widgets — short list of things to act on
// ---------------------------------------------------------------------------

function PendingPanel({
  pendingSuggestions,
  activeRulesCount,
  totalRulesCount,
  pendingMembersCount,
  activeMembersCount,
}: {
  pendingSuggestions: number;
  activeRulesCount: number;
  totalRulesCount: number;
  pendingMembersCount: number;
  activeMembersCount: number;
}) {
  return (
    <div
      className="flex flex-col gap-px overflow-hidden border border-graphite-dark/20 bg-graphite-dark/15"
      style={{ borderRadius: "var(--radius)" }}
    >
      <PendingItem
        label="// sugerencias por aprobar"
        value={pendingSuggestions}
        href="/admin/suggestions"
        cta="revisar"
        emphasis={pendingSuggestions > 0}
      />
      <PendingItem
        label="// reglas activas"
        value={activeRulesCount}
        secondary={`${totalRulesCount} totales`}
        href="/admin/rules"
        cta="ver todas"
      />
      <PendingItem
        label="// devs"
        value={activeMembersCount}
        secondary={
          pendingMembersCount > 0
            ? `${pendingMembersCount} pendientes`
            : "todos vinculados"
        }
        href="/admin/team"
        cta="gestionar"
        emphasis={pendingMembersCount > 0}
      />
    </div>
  );
}

function PendingItem({
  label,
  value,
  secondary,
  href,
  cta,
  emphasis = false,
}: {
  label: string;
  value: number;
  secondary?: string;
  href: string;
  cta: string;
  emphasis?: boolean;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center justify-between bg-paper p-4 transition-colors hover:bg-paper-soft/40 md:p-5"
    >
      <div className="flex flex-col gap-1">
        <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-graphite">
          {label}
        </span>
        <div className="flex items-baseline gap-2">
          <span
            className={`text-xl tracking-tight md:text-2xl ${
              emphasis ? "font-bold text-ink" : "font-semibold text-ink"
            }`}
          >
            {value.toLocaleString("es-AR")}
          </span>
          {emphasis ? (
            <span aria-hidden className="block h-3 w-1 bg-ink" />
          ) : null}
          {secondary ? (
            <span className="font-mono text-[11px] text-graphite">
              · {secondary}
            </span>
          ) : null}
        </div>
      </div>
      <span
        aria-hidden
        className="font-mono text-[11px] uppercase tracking-[0.22em] text-graphite transition-colors group-hover:text-ink"
      >
        {cta} →
      </span>
    </Link>
  );
}
