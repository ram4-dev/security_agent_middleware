/* eslint-disable react/jsx-no-comment-textnodes */
import { type ReactNode } from "react";

type PaneProps = {
  children: ReactNode;
  /** "// caption" rendered above the title. */
  caption?: string;
  /** Optional right-aligned secondary caption (e.g. "// p95 · < 200ms"). */
  meta?: ReactNode;
  /** Padding scale. */
  padding?: "sm" | "md" | "lg";
  /** Use ink background with paper text. */
  dark?: boolean;
  /** Subtle hover lift — use when the whole pane is interactive. */
  hover?: boolean;
  className?: string;
};

const PAD: Record<NonNullable<PaneProps["padding"]>, string> = {
  sm: "p-4 md:p-5",
  md: "p-6",
  lg: "p-6 md:p-8",
};

export function Pane({
  children,
  caption,
  meta,
  padding = "md",
  dark = false,
  hover = false,
  className = "",
}: PaneProps) {
  const tone = dark
    ? "border-paper/15 bg-ink text-paper"
    : "border-graphite-dark/20 bg-paper text-ink";
  const hoverCls = hover ? "transition-transform hover:-translate-y-0.5" : "";
  const captionTone = dark ? "text-paper/55" : "text-graphite";

  return (
    <div
      className={`flex flex-col gap-4 border ${tone} ${PAD[padding]} ${hoverCls} ${className}`}
      style={{ borderRadius: "var(--radius)" }}
    >
      {caption || meta ? (
        <div className="flex items-baseline justify-between gap-3">
          {caption ? (
            <span
              className={`font-mono text-[11px] uppercase tracking-[0.28em] ${captionTone}`}
            >
              // {caption}
            </span>
          ) : (
            <span />
          )}
          {meta}
        </div>
      ) : null}
      {children}
    </div>
  );
}
