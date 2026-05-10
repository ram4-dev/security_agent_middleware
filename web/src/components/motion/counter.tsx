"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "framer-motion";

type CounterProps = {
  to: number;
  /** seconds for the count animation */
  duration?: number;
  /** Number formatter — defaults to es-AR locale. */
  format?: (value: number) => string;
  /** When true, counter starts immediately on mount instead of waiting for IO. */
  immediate?: boolean;
};

export function Counter({
  to,
  duration = 1.6,
  format,
  immediate = false,
}: CounterProps) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement | null>(null);
  const inView = useInView(ref, { once: true, amount: 0.4 });
  const [n, setN] = useState(reduce || immediate ? to : 0);

  useEffect(() => {
    if (reduce) {
      setN(to);
      return;
    }
    if (!immediate && !inView) return;
    const start = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - start) / (duration * 1000));
      const eased = 1 - Math.pow(1 - k, 3);
      setN(Math.round(eased * to));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [to, duration, reduce, inView, immediate]);

  const formatter =
    format ?? ((value: number) => value.toLocaleString("es-AR"));

  return <span ref={ref}>{formatter(n)}</span>;
}
