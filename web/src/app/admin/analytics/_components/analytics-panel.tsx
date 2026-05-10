"use client";
/* eslint-disable react/jsx-no-comment-textnodes */

import { useCallback, useEffect, useState } from "react";

type ActionStats = { count: number; avgLatencyMs: number };
type AnalyticsData = {
  range: string;
  total: number;
  avgLatencyMs: number;
  byAction: {
    BLOCK: ActionStats;
    REDACT: ActionStats;
    WARN: ActionStats;
    LOG: ActionStats;
  };
  hourly: { hour: string; count: number }[];
  topPolicies: { slug: string; count: number }[];
};

type Range = "24h" | "7d" | "30d";

const RANGE_LABELS: Record<Range, string> = {
  "24h": "últimas 24 h",
  "7d": "últimos 7 días",
  "30d": "últimos 30 días",
};

// Severity reads as bar weight + text weight, matching identidad/design.md
// § 6. Functional color is reserved for `/admin/events` (live monitoring).
const ACTION_STYLES: Record<string, { bar: string; text: string }> = {
  BLOCK:  { bar: "bg-ink",            text: "font-bold text-ink" },
  REDACT: { bar: "bg-ink/75",         text: "font-semibold text-ink" },
  WARN:   { bar: "bg-graphite-dark",  text: "font-medium text-ink" },
  LOG:    { bar: "bg-graphite",       text: "text-ink" },
};

type AlignmentLevel = "alto" | "moderado" | "bajo" | "crítico";

function getAlignmentLevel(score: number): AlignmentLevel {
  if (score >= 90) return "alto";
  if (score >= 70) return "moderado";
  if (score >= 50) return "bajo";
  return "crítico";
}

const ALIGNMENT_META: Record<
  AlignmentLevel,
  { label: string; description: string; weight: string }
> = {
  alto:     { label: "alineamiento alto",     description: "Los devs operan dentro de las políticas de la organización.",         weight: "font-medium" },
  moderado: { label: "alineamiento moderado", description: "Hay margen de mejora — revisá las políticas más activadas.",          weight: "font-semibold" },
  bajo:     { label: "alineamiento bajo",     description: "Un porcentaje significativo de requests está siendo bloqueado.",       weight: "font-bold" },
  crítico:  { label: "atención requerida",    description: "Más de la mitad de los requests no pasan las políticas vigentes.",    weight: "font-bold" },
};

export function AnalyticsPanel({ initial }: { initial: AnalyticsData }) {
  const [data, setData] = useState(initial);
  const [range, setRange] = useState<Range>("7d");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (r: Range) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/analytics?range=${r}`, { cache: "no-store" });
      if (res.ok) setData(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(range); }, [range, load]);

  const blocked = data.byAction.BLOCK.count;
  const aligned = data.total - blocked;
  const alignmentScore = data.total > 0 ? (aligned / data.total) * 100 : null;
  const level = alignmentScore !== null ? getAlignmentLevel(alignmentScore) : null;
  const meta = level ? ALIGNMENT_META[level] : null;
  const maxAction = Math.max(...Object.values(data.byAction).map((a) => a.count), 1);

  return (
    <div className={`flex flex-col gap-8 transition-opacity ${loading ? "opacity-50" : ""}`}>

      {/* Range selector */}
      <div className="flex items-center gap-2">
        {(["24h", "7d", "30d"] as Range[]).map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => setRange(r)}
            className={`px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors ${
              range === r
                ? "bg-ink text-paper"
                : "border border-graphite-dark/25 text-graphite hover:border-ink hover:text-ink"
            }`}
            style={{ borderRadius: "var(--radius)" }}
          >
            {RANGE_LABELS[r]}
          </button>
        ))}
      </div>

      {/* Alignment hero */}
      <div
        className="border border-graphite-dark/15 bg-paper p-6 sm:p-8"
        style={{ borderRadius: "var(--radius)" }}
      >
        <p className="mb-6 font-mono text-[11px] uppercase tracking-wider text-graphite">
          // alineamiento organizacional
        </p>

        {alignmentScore !== null && meta ? (
          <div className="flex flex-col gap-5">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <span className="text-6xl font-semibold leading-none tracking-tighter text-ink sm:text-7xl md:text-8xl">
                {alignmentScore.toFixed(1)}
                <span className="text-3xl sm:text-4xl md:text-5xl">%</span>
              </span>
              <div className="flex flex-col gap-1 pb-1">
                <span
                  className={`inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-ink ${meta.weight}`}
                >
                  <span aria-hidden className={`h-3 w-1 ${level === "alto" ? "bg-graphite" : level === "moderado" ? "bg-graphite-dark" : level === "bajo" ? "bg-ink/75" : "bg-ink"}`} />
                  {meta.label}
                </span>
                <span className="max-w-xs font-mono text-[11px] text-graphite">
                  {meta.description}
                </span>
              </div>
            </div>

            {/* Progress bar */}
            <div className="flex flex-col gap-2">
              <div className="relative h-2 w-full bg-paper-soft" style={{ borderRadius: "2px" }}>
                <div
                  className="absolute inset-y-0 left-0 bg-ink transition-all duration-700"
                  style={{ width: `${alignmentScore}%`, borderRadius: "2px" }}
                />
              </div>
              <div className="flex justify-between font-mono text-[10px] text-graphite">
                <span>{aligned.toLocaleString("es-AR")} de {data.total.toLocaleString("es-AR")} requests alineados</span>
                <span>{blocked.toLocaleString("es-AR")} bloqueados</span>
              </div>
            </div>
          </div>
        ) : (
          <p className="py-8 text-center font-mono text-xs text-graphite">
            // sin datos suficientes para calcular alineamiento
          </p>
        )}
      </div>

      {/* Secondary KPIs */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard label="total requests" value={data.total.toLocaleString("es-AR")} />
        <KpiCard label="bloqueados" value={blocked.toLocaleString("es-AR")} />
        <KpiCard
          label="block rate"
          value={data.total > 0 ? `${((blocked / data.total) * 100).toFixed(1)}%` : "—"}
        />
        <KpiCard label="latencia prom." value={data.avgLatencyMs > 0 ? `${data.avgLatencyMs} ms` : "—"} />
      </div>

      {/* Action breakdown */}
      <div
        className="border border-graphite-dark/15 bg-paper p-5"
        style={{ borderRadius: "var(--radius)" }}
      >
        <p className="mb-4 font-mono text-[11px] uppercase tracking-wider text-graphite">
          // acción · distribución
        </p>
        <div className="flex flex-col gap-3">
          {(["BLOCK", "REDACT", "WARN", "LOG"] as const).map((action) => {
            const stats = data.byAction[action];
            const pct = (stats.count / maxAction) * 100;
            const style = ACTION_STYLES[action];
            return (
              <div key={action} className="flex items-center gap-3">
                <span className={`w-14 font-mono text-[11px] font-semibold uppercase ${style.text}`}>
                  {action}
                </span>
                <div className="relative h-2 flex-1 bg-paper-soft/60" style={{ borderRadius: "2px" }}>
                  <div
                    className={`absolute inset-y-0 left-0 ${style.bar} transition-all duration-500`}
                    style={{ width: `${pct}%`, borderRadius: "2px" }}
                  />
                </div>
                <span className="w-12 text-right font-mono text-[11px] text-graphite">
                  {stats.count.toLocaleString("es-AR")}
                </span>
                <span className="hidden w-20 text-right font-mono text-[11px] text-graphite sm:block">
                  ~{stats.avgLatencyMs} ms
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Top policies */}
      {data.topPolicies.length > 0 && (
        <div
          className="border border-graphite-dark/15 bg-paper p-5"
          style={{ borderRadius: "var(--radius)" }}
        >
          <p className="mb-4 font-mono text-[11px] uppercase tracking-wider text-graphite">
            // políticas · más activadas
          </p>
          <div className="flex flex-col gap-2">
            {data.topPolicies.map((p, i) => {
              const pct = (p.count / data.topPolicies[0].count) * 100;
              return (
                <div key={p.slug} className="flex items-center gap-3">
                  <span className="w-4 font-mono text-[11px] text-graphite">{i + 1}</span>
                  <span className="w-48 truncate font-mono text-[11px] text-ink">{p.slug}</span>
                  <div className="relative h-1.5 flex-1 bg-paper-soft/60" style={{ borderRadius: "2px" }}>
                    <div
                      className="absolute inset-y-0 left-0 bg-ink/50 transition-all duration-500"
                      style={{ width: `${pct}%`, borderRadius: "2px" }}
                    />
                  </div>
                  <span className="w-10 text-right font-mono text-[11px] text-graphite">
                    {p.count}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="flex flex-col gap-1 border border-graphite-dark/15 bg-paper p-4"
      style={{ borderRadius: "var(--radius)" }}
    >
      <span className="font-mono text-[10px] uppercase tracking-wider text-graphite">
        // {label}
      </span>
      <span className="text-2xl font-semibold tracking-tight text-ink">
        {value}
      </span>
    </div>
  );
}
