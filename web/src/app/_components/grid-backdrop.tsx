// Subtle grid mesh that fades out at the edges. Pure CSS, server-safe.
// Used as a calm backdrop on light surfaces (login, future onboarding).

type Variant = "paper" | "ink";

type GridBackdropProps = {
  variant?: Variant;
  cell?: number; // grid cell size in px
  className?: string;
};

export function GridBackdrop({
  variant = "paper",
  cell = 48,
  className = "",
}: GridBackdropProps) {
  const lineColor =
    variant === "paper"
      ? "rgba(28, 27, 24, 0.07)"
      : "rgba(239, 237, 230, 0.06)";

  const fade = "radial-gradient(ellipse 75% 70% at center, black 0%, transparent 78%)";

  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 ${className}`}
      style={{
        backgroundImage: `linear-gradient(${lineColor} 1px, transparent 1px), linear-gradient(90deg, ${lineColor} 1px, transparent 1px)`,
        backgroundSize: `${cell}px ${cell}px`,
        backgroundPosition: "center center",
        WebkitMaskImage: fade,
        maskImage: fade,
      }}
    />
  );
}
