import { type ReactNode } from "react";

type PillProps = {
  children: ReactNode;
  /** Mono-uppercase tag style by default. */
  variant?: "tag" | "soft";
  className?: string;
};

export function Pill({ children, variant = "tag", className = "" }: PillProps) {
  const base =
    variant === "tag"
      ? "inline-flex items-center gap-2 border border-graphite-dark/25 px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.22em] text-graphite-dark"
      : "inline-flex items-center gap-2 bg-paper-soft/60 px-3 py-1 text-xs text-ink";
  return (
    <span
      className={`${base} ${className}`}
      style={{ borderRadius: "var(--radius)" }}
    >
      {children}
    </span>
  );
}
