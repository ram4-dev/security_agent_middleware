"use client";

import { motion, useReducedMotion } from "framer-motion";

type MarqueeProps = {
  items: string[];
  /** Seconds per full loop. Higher = slower. */
  speed?: number;
  className?: string;
  /** Direction: "ltr" content scrolls right→left (default), "rtl" reverses. */
  direction?: "ltr" | "rtl";
  /** Color of the bullet between items. Inherits text color by default. */
  bullet?: boolean;
};

export function Marquee({
  items,
  speed = 42,
  className = "",
  direction = "ltr",
  bullet = true,
}: MarqueeProps) {
  const reduce = useReducedMotion();
  const stream = [...items, ...items];
  const animate =
    direction === "ltr" ? { x: ["0%", "-50%"] } : { x: ["-50%", "0%"] };

  return (
    <div
      aria-hidden
      className={`pointer-events-none relative w-full overflow-hidden opacity-50 ${className}`}
    >
      <motion.div
        className="flex w-max gap-12 whitespace-nowrap"
        animate={reduce ? undefined : animate}
        transition={
          reduce
            ? undefined
            : { duration: speed, ease: "linear", repeat: Infinity }
        }
      >
        {stream.map((token, i) => (
          <span
            key={`${token}-${i}`}
            className="flex items-center gap-12 font-mono text-[11px] uppercase tracking-[0.28em]"
          >
            {bullet ? (
              <span className="h-1 w-1 rounded-full bg-current" />
            ) : null}
            {token}
          </span>
        ))}
      </motion.div>
    </div>
  );
}
