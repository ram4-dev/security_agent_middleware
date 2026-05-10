// Monochrome action indicator for landing/admin views OUTSIDE the live
// monitoring feed (`/admin/events`). Severity is communicated via type
// weight (LOG 400 → BLOCK 700) and a left bar that darkens with severity,
// per `identidad/design.md` § 6. The events feed is the only surface that
// adds functional color (amber WARN, crimson BLOCK).

export type Action = "LOG" | "WARN" | "REDACT" | "BLOCK";

const WEIGHT: Record<Action, string> = {
  LOG: "font-normal",
  WARN: "font-medium",
  REDACT: "font-semibold",
  BLOCK: "font-bold",
};

const INDICATOR: Record<Action, string> = {
  LOG: "bg-graphite",
  WARN: "bg-graphite-dark",
  REDACT: "bg-ink/80",
  BLOCK: "bg-ink",
};

type ActionPillProps = {
  action: Action;
  rule?: string;
  /** When true, render in a light-on-dark context (paper text on ink bg). */
  dark?: boolean;
};

export function ActionPill({ action, rule, dark = false }: ActionPillProps) {
  const labelColor = dark ? "text-paper" : "text-ink";
  const ruleColor = dark ? "text-paper/55" : "text-graphite";
  const ruleValue = dark ? "text-paper" : "text-ink";
  const indicator = dark
    ? action === "BLOCK"
      ? "bg-paper"
      : action === "REDACT"
        ? "bg-paper/80"
        : action === "WARN"
          ? "bg-paper/55"
          : "bg-paper/40"
    : INDICATOR[action];

  return (
    <div className="inline-flex items-center gap-3 font-mono text-xs uppercase tracking-wider">
      <span aria-hidden className={`h-4 w-1 ${indicator}`} />
      <span className={`${labelColor} ${WEIGHT[action]}`}>{action}</span>
      {rule ? (
        <span className={`${ruleColor} normal-case`}>
          → rule.id = <span className={ruleValue}>&quot;{rule}&quot;</span>
        </span>
      ) : null}
    </div>
  );
}
