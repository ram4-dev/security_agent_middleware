/* eslint-disable react/jsx-no-comment-textnodes */
import Link from "next/link";
import { type ReactNode } from "react";

type EmptyStateProps = {
  /** Caption rendered with the "// " prefix. */
  caption?: string;
  /** Concrete next-step instruction. */
  title: ReactNode;
  /** Optional inline action link or button. */
  cta?: { label: string; href?: string; onClick?: () => void };
  /** Optional decorative SVG (will be rendered at 32px). */
  icon?: ReactNode;
  className?: string;
};

export function EmptyState({
  caption,
  title,
  cta,
  icon,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-start gap-3 border border-graphite-dark/15 bg-paper-soft/30 p-6 text-graphite-dark ${className}`}
      style={{ borderRadius: "var(--radius)" }}
    >
      {icon ? <div className="text-graphite">{icon}</div> : null}
      {caption ? (
        <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-graphite">
          // {caption}
        </span>
      ) : null}
      <p className="text-sm leading-relaxed">{title}</p>
      {cta ? (
        cta.href ? (
          <Link
            href={cta.href}
            className="font-mono text-[11px] uppercase tracking-[0.22em] text-ink underline underline-offset-4 transition-colors hover:text-graphite-dark"
          >
            {cta.label} →
          </Link>
        ) : (
          <button
            type="button"
            onClick={cta.onClick}
            className="font-mono text-[11px] uppercase tracking-[0.22em] text-ink underline underline-offset-4 transition-colors hover:text-graphite-dark"
          >
            {cta.label} →
          </button>
        )
      ) : null}
    </div>
  );
}
