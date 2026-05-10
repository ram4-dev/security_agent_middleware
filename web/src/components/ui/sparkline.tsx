// Tiny inline sparkline. Pure SVG, no deps. Uses currentColor so callers
// can re-tone via Tailwind text-* classes.

type SparklineProps = {
  values: number[];
  className?: string;
  /** Render as a filled area instead of a line. Looks like a tiny histogram. */
  variant?: "line" | "bars";
  /** Aspect ratio width/height of the underlying viewBox. Defaults to 100×24. */
  width?: number;
  height?: number;
};

export function Sparkline({
  values,
  className = "",
  variant = "line",
  width = 100,
  height = 24,
}: SparklineProps) {
  if (values.length === 0) {
    return (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={`w-full ${className}`}
        preserveAspectRatio="none"
        aria-hidden
      />
    );
  }
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;

  if (variant === "bars") {
    const slot = width / values.length;
    const barW = Math.max(1, slot * 0.7);
    const pad = (slot - barW) / 2;
    return (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={`w-full ${className}`}
        preserveAspectRatio="none"
        aria-hidden
      >
        {values.map((v, i) => {
          const h = ((v - min) / range) * height;
          return (
            <rect
              key={i}
              x={i * slot + pad}
              y={height - h}
              width={barW}
              height={Math.max(1, h)}
              fill="currentColor"
            />
          );
        })}
      </svg>
    );
  }

  const step = width / Math.max(1, values.length - 1);
  const points = values
    .map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={`w-full ${className}`}
      preserveAspectRatio="none"
      aria-hidden
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
