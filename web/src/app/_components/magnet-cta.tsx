// Solid-ink CTA with a magnetic hover — the label nudges toward the
// cursor while a slim arrow slides on hover. Used on the final CTA.
"use client";

import Link from "next/link";
import { type ReactNode, useRef } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
} from "framer-motion";

type MagnetCtaProps = {
  href: string;
  children: ReactNode;
  external?: boolean;
};

const STRENGTH = 8;

export function MagnetCta({ href, children, external = false }: MagnetCtaProps) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLAnchorElement | null>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 240, damping: 22, mass: 0.4 });
  const sy = useSpring(y, { stiffness: 240, damping: 22, mass: 0.4 });

  function onMove(e: React.MouseEvent) {
    if (reduce || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    x.set(((e.clientX - cx) / (rect.width / 2)) * STRENGTH);
    y.set(((e.clientY - cy) / (rect.height / 2)) * STRENGTH);
  }
  function onLeave() {
    x.set(0);
    y.set(0);
  }

  const inner = (
    <motion.span
      style={reduce ? undefined : { x: sx, y: sy }}
      className="group inline-flex items-center gap-2"
    >
      {children}
      <span
        aria-hidden
        className="transition-transform duration-300 group-hover:translate-x-1"
      >
        →
      </span>
    </motion.span>
  );

  const className =
    "inline-flex items-center justify-center bg-ink px-7 py-3.5 font-medium text-paper transition-colors hover:bg-graphite-dark";

  if (external) {
    return (
      <a
        ref={ref as React.RefObject<HTMLAnchorElement>}
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        onMouseMove={onMove}
        onMouseLeave={onLeave}
        className={className}
        style={{ borderRadius: "var(--radius)" }}
      >
        {inner}
      </a>
    );
  }

  return (
    <Link
      ref={ref as React.RefObject<HTMLAnchorElement>}
      href={href}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className={className}
      style={{ borderRadius: "var(--radius)" }}
    >
      {inner}
    </Link>
  );
}
