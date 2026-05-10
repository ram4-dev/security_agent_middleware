import Link from "next/link";
import { type ReactNode } from "react";

type Variant = "solid" | "outline" | "ghost";
type Tone = "ink" | "paper";
type Size = "sm" | "md" | "lg";

type CommonProps = {
  variant?: Variant;
  tone?: Tone;
  size?: Size;
  /** Renders a "→" after the label that slides on hover. */
  arrow?: boolean;
  className?: string;
  children: ReactNode;
};

type LinkProps = CommonProps & {
  href: string;
  external?: boolean;
  onClick?: never;
  type?: never;
  disabled?: never;
};

type NativeButtonProps = CommonProps & {
  href?: never;
  external?: never;
  type?: "button" | "submit" | "reset";
  onClick?: () => void;
  disabled?: boolean;
};

type ButtonProps = LinkProps | NativeButtonProps;

const SIZES: Record<Size, string> = {
  sm: "px-4 py-2 font-mono text-[11px] uppercase tracking-wider",
  md: "px-6 py-3 font-medium text-sm md:text-base",
  lg: "px-7 py-3.5 font-medium text-base md:text-lg",
};

const VARIANTS: Record<Variant, Record<Tone, string>> = {
  solid: {
    ink: "bg-ink text-paper hover:bg-graphite-dark",
    paper: "bg-paper text-ink hover:bg-paper-soft",
  },
  outline: {
    ink: "border border-ink text-ink hover:bg-ink hover:text-paper",
    paper: "border border-paper/70 text-paper hover:bg-paper hover:text-ink",
  },
  ghost: {
    ink: "text-ink hover:bg-ink/[0.06]",
    paper: "text-paper hover:bg-paper/10",
  },
};

const BASE =
  "group inline-flex items-center justify-center gap-2 transition-colors disabled:cursor-not-allowed disabled:opacity-60";

export function Button(props: ButtonProps) {
  const {
    variant = "solid",
    tone = "ink",
    size = "md",
    arrow = false,
    className = "",
    children,
  } = props;

  const cls = `${BASE} ${SIZES[size]} ${VARIANTS[variant][tone]} ${className}`;
  const content = (
    <>
      <span className="inline-flex items-center">{children}</span>
      {arrow ? (
        <span
          aria-hidden
          className="transition-transform duration-300 group-hover:translate-x-1"
        >
          →
        </span>
      ) : null}
    </>
  );
  const radius = { borderRadius: "var(--radius)" };

  if ("href" in props && props.href) {
    if (props.external) {
      return (
        <a
          href={props.href}
          target="_blank"
          rel="noopener noreferrer"
          className={cls}
          style={radius}
        >
          {content}
        </a>
      );
    }
    return (
      <Link href={props.href} className={cls} style={radius}>
        {content}
      </Link>
    );
  }

  return (
    <button
      type={props.type ?? "button"}
      onClick={props.onClick}
      disabled={props.disabled}
      className={cls}
      style={radius}
    >
      {content}
    </button>
  );
}
