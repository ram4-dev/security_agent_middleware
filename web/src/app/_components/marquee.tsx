"use client";

import { motion } from "framer-motion";

type MarqueeProps = {
  items: string[];
  speed?: number; // seconds per full loop
  className?: string;
};

export function Marquee({ items, speed = 38, className = "" }: MarqueeProps) {
  const stream = [...items, ...items];
  return (
    <div
      aria-hidden
      className={`pointer-events-none relative w-full overflow-hidden ${className}`}
    >
      <motion.div
        className="flex w-max gap-12 whitespace-nowrap"
        animate={{ x: ["0%", "-50%"] }}
        transition={{
          duration: speed,
          ease: "linear",
          repeat: Infinity,
        }}
      >
        {stream.map((token, i) => (
          <span
            key={`${token}-${i}`}
            className="flex items-center gap-12 font-mono text-[11px] uppercase tracking-[0.28em] text-paper/45"
          >
            <span className="h-1 w-1 rounded-full bg-paper/35" />
            {token}
          </span>
        ))}
      </motion.div>
    </div>
  );
}
