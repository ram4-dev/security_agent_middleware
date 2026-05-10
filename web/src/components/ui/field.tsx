import { type ReactNode } from "react";

type FieldProps = {
  /** Visible label, also linked to the input via htmlFor. */
  label: ReactNode;
  /** Stable id used both as <input id> and <label for>. */
  htmlFor: string;
  /** Optional helper / hint text rendered under the input. */
  hint?: ReactNode;
  /** Render-prop returns the actual input/textarea/select. */
  children: (props: { id: string }) => ReactNode;
  /** Span both columns inside a 2-col grid. */
  full?: boolean;
  className?: string;
};

export function Field({
  label,
  htmlFor,
  hint,
  children,
  full = false,
  className = "",
}: FieldProps) {
  const colSpan = full ? "md:col-span-2" : "";
  return (
    <div className={`flex flex-col gap-2 ${colSpan} ${className}`}>
      <label
        htmlFor={htmlFor}
        className="font-mono text-[11px] uppercase tracking-[0.22em] text-graphite"
      >
        {label}
      </label>
      {children({ id: htmlFor })}
      {hint ? (
        <span className="font-mono text-[11px] leading-relaxed text-graphite">
          {hint}
        </span>
      ) : null}
    </div>
  );
}

/** Shared input className for use with Field. Mantiene el focus ring del DS. */
export const fieldInputClass =
  "w-full border border-graphite-dark/30 bg-paper px-3 py-2.5 font-sans text-sm text-ink transition-colors placeholder:text-graphite focus:border-ink focus:outline-none";

export const fieldTextareaClass = `${fieldInputClass} min-h-[120px] resize-y`;
