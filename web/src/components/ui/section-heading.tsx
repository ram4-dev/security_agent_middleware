/* eslint-disable react/jsx-no-comment-textnodes */
import { type ReactNode } from "react";

type SectionHeadingProps = {
  /** Bracketed counter shown above the caption, e.g. "01" → renders [01]. */
  index?: string;
  /** Caption rendered with the "// " prefix. */
  tag: string;
  title: ReactNode;
  subtitle?: ReactNode;
  /** Center-align the heading block. */
  center?: boolean;
  /** Use light-on-dark text colors. */
  dark?: boolean;
  className?: string;
};

export function SectionHeading({
  index,
  tag,
  title,
  subtitle,
  center = false,
  dark = false,
  className = "",
}: SectionHeadingProps) {
  const align = center ? "items-center text-center" : "items-start";
  const subtitleColor = dark ? "text-paper/75" : "text-graphite-dark";

  return (
    <div className={`mb-12 flex max-w-3xl flex-col gap-3 ${align} ${className}`}>
      {index ? (
        <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-graphite">
          [{index}]
        </span>
      ) : null}
      <span className="font-mono text-xs uppercase tracking-wider text-graphite">
        // {tag}
      </span>
      <h2 className="text-3xl font-semibold leading-tight tracking-tight md:text-4xl">
        {title}
      </h2>
      {subtitle ? (
        <p
          className={`max-w-2xl text-base leading-relaxed md:text-lg ${subtitleColor}`}
        >
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}
