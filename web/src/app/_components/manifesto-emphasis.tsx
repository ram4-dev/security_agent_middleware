// Subtle emphasis used in the manifesto: the word "alineados" gets an
// underline that draws itself once the manifesto enters the viewport.
"use client";

import { type ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

export function ManifestoEmphasis({ children }: { children: ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <span className="relative inline-block whitespace-nowrap">
      <span className="relative z-10">{children}</span>
      <motion.span
        aria-hidden
        className="absolute inset-x-0 -bottom-[10px] block h-[3px] origin-left bg-ink"
        initial={reduce ? { scaleX: 1 } : { scaleX: 0 }}
        whileInView={{ scaleX: 1 }}
        viewport={{ once: true, amount: 0.6 }}
        transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: 0.4 }}
      />
    </span>
  );
}
