// `//` is a deliberate visual token from the design system (see
// identidad/design.md § 3, "Comments tipo código"), not stray JS comments.
/* eslint-disable react/jsx-no-comment-textnodes */
"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
  type MotionValue,
  type Variants,
} from "framer-motion";

import { WaveTerrain } from "@/components/wave-terrain";
import { Marquee } from "./marquee";

const REPO_URL = "https://github.com/platanus-hack/platanus-hack-26-ar-team-22";

const MARQUEE_TOKENS = [
  "regex · 5ms",
  "pattern · 20ms",
  "haiku · 150ms",
  "log",
  "warn",
  "redact",
  "block",
  "trace · 01HXYZK…",
  "p95 · < 200ms",
  "audit · live",
  "claude code · interceptor",
];

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

const lineMask: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.12, delayChildren: 0.15 },
  },
};

const lineRise: Variants = {
  hidden: { y: "110%", opacity: 0, filter: "blur(10px)" },
  visible: {
    y: "0%",
    opacity: 1,
    filter: "blur(0px)",
    transition: { duration: 1.0, ease: EASE_OUT },
  },
};

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14, filter: "blur(6px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.9, ease: EASE_OUT },
  },
};

export function Hero() {
  const reduce = useReducedMotion();
  const containerRef = useRef<HTMLElement | null>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"],
  });

  const backdropY = useTransform(scrollYProgress, [0, 1], ["0%", "18%"]);
  const headlineY = useTransform(scrollYProgress, [0, 1], ["0%", "-10%"]);
  const headlineOpacity = useTransform(
    scrollYProgress,
    [0, 0.5, 1],
    [1, 0.95, 0.5],
  );

  return (
    <section
      ref={containerRef}
      className="relative isolate flex min-h-svh w-full flex-col overflow-hidden bg-ink text-paper"
    >
      <HeroBackdrop reduce={!!reduce} y={backdropY} />

      <div className="relative mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 pb-10 pt-8 md:pb-14 md:pt-14">
        <HeroMeta />

        <motion.div
          style={
            reduce ? undefined : { y: headlineY, opacity: headlineOpacity }
          }
          className="flex flex-col"
        >
          <HeroHeadline />
          <HeroSub />
          <HeroCtas />
        </motion.div>

        <div className="mt-auto" />
        <HeroLiveBar />
      </div>

      <Marquee
        items={MARQUEE_TOKENS}
        speed={48}
        className="border-t border-paper/10 py-4"
      />
    </section>
  );
}

function HeroBackdrop({
  reduce,
  y,
}: {
  reduce: boolean;
  y: MotionValue<string>;
}) {
  return (
    <motion.div
      aria-hidden
      className="absolute inset-0 -z-10 overflow-hidden bg-ink"
      style={reduce ? undefined : { y }}
    >
      <WaveTerrain className="absolute inset-0 h-full w-full text-paper" />
      {/* Soft vignette anchors the type and cuts grid noise at edges. */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 50% 35%, transparent 0%, transparent 35%, rgba(0,0,0,0.55) 95%)",
        }}
      />
    </motion.div>
  );
}

function HeroMeta() {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={fadeUp}
      className="mb-8 flex flex-wrap items-baseline justify-between gap-3 md:mb-14"
    >
      <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-paper/55">
        <span aria-hidden className="mr-2 text-paper">
          +
        </span>
        sys.online // op.ready
      </span>
      <span className="hidden font-mono text-[11px] uppercase tracking-[0.28em] text-paper/55 md:inline-flex">
        tranquera · v1.0
      </span>
      <span className="inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.28em] text-paper/55">
        <span
          aria-hidden
          className="hero-dot block h-1.5 w-1.5 rounded-full bg-paper"
        />
        live · audit
      </span>
    </motion.div>
  );
}

function HeroHeadline() {
  return (
    <motion.h1
      variants={lineMask}
      initial="hidden"
      animate="visible"
      aria-label="tranquera. un paso controlado."
      className="flex flex-col"
    >
      <span className="block overflow-hidden text-[clamp(2.75rem,11vw,8.5rem)] font-semibold lowercase leading-[0.94] tracking-[-0.045em] text-paper">
        <motion.span variants={lineRise} className="block will-change-transform">
          tranquera.
        </motion.span>
      </span>
      <span className="mt-1 block overflow-hidden text-2xl font-medium leading-[1.05] tracking-[-0.02em] text-paper/75 md:mt-3 md:text-5xl">
        <motion.span variants={lineRise} className="block will-change-transform">
          un paso controlado.
        </motion.span>
      </span>
    </motion.h1>
  );
}

function HeroSub() {
  return (
    <motion.p
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      transition={{ duration: 0.9, delay: 0.55, ease: EASE_OUT }}
      className="mt-6 max-w-2xl text-base leading-relaxed text-paper/80 md:mt-8 md:text-lg"
    >
      La capa de alineamiento entre tu equipo y Claude Code. Los LLMs no tienen
      contexto organizacional por defecto — con Tranquera, siempre lo tienen.
    </motion.p>
  );
}

function HeroCtas() {
  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      transition={{ duration: 0.9, delay: 0.75, ease: EASE_OUT }}
      className="mt-6 flex flex-wrap items-center gap-4 md:mt-8"
    >
      <Link
        href="/admin/login"
        className="group relative inline-flex items-center justify-center overflow-hidden bg-paper px-7 py-3.5 font-medium text-ink transition-colors hover:bg-paper-soft"
        style={{ borderRadius: "var(--radius)" }}
      >
        <span>Entrar al admin</span>
        <span
          aria-hidden
          className="ml-2 transition-transform duration-300 group-hover:translate-x-1"
        >
          →
        </span>
      </Link>
      <Link
        href={REPO_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center justify-center border border-paper/70 px-7 py-3.5 font-medium text-paper transition-colors hover:border-paper hover:bg-paper hover:text-ink"
        style={{ borderRadius: "var(--radius)" }}
      >
        Ver en GitHub
      </Link>
    </motion.div>
  );
}

function HeroLiveBar() {
  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      transition={{ duration: 0.9, delay: 1.0, ease: EASE_OUT }}
      className="mt-10 grid grid-cols-2 gap-px overflow-hidden border border-paper/10 bg-paper/[0.06] md:mt-16 md:grid-cols-4"
      style={{ borderRadius: "var(--radius)" }}
    >
      <LiveStat label="trace · last" value="01HXYZK…" mono />
      <LiveStat label="p95 · cascade" value="9 ms" />
      <LiveStat label="verdicts · today" countTo={1247} />
      <LiveStat label="rules · active" countTo={42} />
    </motion.div>
  );
}

function LiveStat({
  label,
  value,
  countTo,
  mono,
}: {
  label: string;
  value?: string;
  countTo?: number;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5 bg-ink p-4 md:p-5">
      <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-paper/50">
        // {label}
      </span>
      <span
        className={`text-xl text-paper md:text-2xl ${
          mono ? "font-mono" : "font-semibold"
        } tracking-tight`}
      >
        {countTo !== undefined ? <CountUp to={countTo} /> : value}
      </span>
    </div>
  );
}

// Tiny easing-based counter — no extra lib. Counts up once on mount.
function CountUp({ to, duration = 1.6 }: { to: number; duration?: number }) {
  const reduce = useReducedMotion();
  const [n, setN] = useState(reduce ? to : 0);

  useEffect(() => {
    if (reduce) {
      setN(to);
      return;
    }
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
  }, [to, duration, reduce]);

  return <>{n.toLocaleString("es-AR")}</>;
}
