"use client";

import { type ReactNode } from "react";
import { motion, useReducedMotion, type Variants } from "framer-motion";

const EASE = [0.16, 1, 0.3, 1] as const;

const VARIANTS: Variants = {
  hidden: { opacity: 0, y: 18, filter: "blur(8px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.9, ease: EASE },
  },
};

type RevealProps = {
  children: ReactNode;
  delay?: number;
  className?: string;
  /** 0..1 — how much of the element must be in view to trigger. */
  amount?: number;
  /** Re-fire when scrolling back. Defaults to once. */
  once?: boolean;
  /** Distance the element rises from. Defaults to 18 (px). */
  y?: number;
};

export function Reveal({
  children,
  delay = 0,
  className,
  amount = 0.2,
  once = true,
  y = 18,
}: RevealProps) {
  const reduce = useReducedMotion();
  if (reduce) {
    return <div className={className}>{children}</div>;
  }
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { ...VARIANTS.hidden, y },
        visible: VARIANTS.visible,
      }}
      initial="hidden"
      whileInView="visible"
      viewport={{ once, amount }}
      transition={{ delay }}
    >
      {children}
    </motion.div>
  );
}
