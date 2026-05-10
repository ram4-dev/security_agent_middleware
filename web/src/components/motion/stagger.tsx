"use client";

import { type ReactNode } from "react";
import { motion, useReducedMotion, type Variants } from "framer-motion";

const EASE = [0.16, 1, 0.3, 1] as const;

const ITEM_VARIANTS: Variants = {
  hidden: { opacity: 0, y: 18, filter: "blur(8px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.9, ease: EASE },
  },
};

type StaggerProps = {
  children: ReactNode;
  /** Seconds between children. */
  gap?: number;
  /** Initial delay before the first child plays. */
  delay?: number;
  className?: string;
  amount?: number;
  once?: boolean;
};

export function Stagger({
  children,
  gap = 0.1,
  delay = 0,
  className,
  amount = 0.2,
  once = true,
}: StaggerProps) {
  const reduce = useReducedMotion();
  if (reduce) {
    return <div className={className}>{children}</div>;
  }
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once, amount }}
      variants={{
        hidden: {},
        visible: {
          transition: { staggerChildren: gap, delayChildren: delay },
        },
      }}
    >
      {children}
    </motion.div>
  );
}

type StaggerItemProps = {
  children: ReactNode;
  className?: string;
  y?: number;
};

export function StaggerItem({ children, className, y = 18 }: StaggerItemProps) {
  const reduce = useReducedMotion();
  if (reduce) {
    return <div className={className}>{children}</div>;
  }
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { ...ITEM_VARIANTS.hidden, y },
        visible: ITEM_VARIANTS.visible,
      }}
    >
      {children}
    </motion.div>
  );
}
