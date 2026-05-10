// Interactive cascade demo. A request token flows left→right through
// Regex → Pattern → Haiku, lighting up the layer that matches and
// short-circuiting before the more expensive layers run. Mirrors the
// real proxy semantics described in spec/01-engine-interceptor.md.
//
// The visualisation is auto-cycling through four canonical scenarios;
// the user can also click a chip at the top to jump to a specific one.
/* eslint-disable react/jsx-no-comment-textnodes */
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { ActionPill, type Action } from "@/components/ui";

type ExitLayer = 1 | 2 | 3;
type Verdict = "BLOCK" | "REDACT" | "WARN" | "LOG" | "PASS";

type Scenario = {
  id: string;
  label: string;
  prompt: string;
  exitLayer: ExitLayer | null; // null = goes through, no match
  verdict: Verdict;
  rule?: string;
};

const SCENARIOS: Scenario[] = [
  {
    id: "aws",
    label: "credencial",
    prompt: "ayudame con AKIAIOSFODNN7EXAMPLE",
    exitLayer: 1,
    verdict: "BLOCK",
    rule: "aws-access-key",
  },
  {
    id: "env",
    label: "filename",
    prompt: "no funciona mi .env de prod",
    exitLayer: 2,
    verdict: "BLOCK",
    rule: "dotenv-paste",
  },
  {
    id: "client",
    label: "cliente",
    prompt: "escribime un email para Acme Corp",
    exitLayer: 3,
    verdict: "REDACT",
    rule: "client-name",
  },
  {
    id: "ok",
    label: "limpio",
    prompt: "explicame cómo funciona git rebase",
    exitLayer: null,
    verdict: "PASS",
  },
];

type Stage =
  | "idle"
  | "regex-active"
  | "regex-done"
  | "pattern-active"
  | "pattern-done"
  | "haiku-active"
  | "haiku-done"
  | "verdict";

const LAYER_LATENCY = { regex: 5, pattern: 20, haiku: 150 } as const;

// ms to dwell on each stage transition. Tuned so the cascade reads
// without feeling slow — the actual proxy is ~10× faster.
const REGEX_DWELL = 600;
const PATTERN_DWELL = 700;
const HAIKU_DWELL = 1100;
const VERDICT_HOLD = 2400;

export function CascadeDemo() {
  const reduce = useReducedMotion();
  const [idx, setIdx] = useState(0);
  const [stage, setStage] = useState<Stage>("idle");
  const [paused, setPaused] = useState(false);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const scenario = SCENARIOS[idx];

  function clearTimers() {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  }

  function schedule(fn: () => void, ms: number) {
    const t = setTimeout(fn, ms);
    timersRef.current.push(t);
  }

  // Drive the stage machine for the active scenario.
  useEffect(() => {
    if (paused) return;
    if (reduce) {
      // Skip animation for reduced-motion users; just show the verdict.
      setStage("verdict");
      return;
    }
    clearTimers();
    setStage("idle");
    schedule(() => setStage("regex-active"), 250);
    schedule(() => {
      setStage("regex-done");
      if (scenario.exitLayer === 1) {
        schedule(() => setStage("verdict"), 200);
      } else {
        schedule(() => setStage("pattern-active"), 200);
      }
    }, 250 + REGEX_DWELL);

    if (scenario.exitLayer !== 1) {
      const tBase = 250 + REGEX_DWELL + 200;
      schedule(() => {
        setStage("pattern-done");
        if (scenario.exitLayer === 2) {
          schedule(() => setStage("verdict"), 200);
        } else {
          schedule(() => setStage("haiku-active"), 200);
        }
      }, tBase + PATTERN_DWELL);
    }

    if (scenario.exitLayer !== 1 && scenario.exitLayer !== 2) {
      const tBase = 250 + REGEX_DWELL + 200 + PATTERN_DWELL + 200;
      schedule(() => {
        setStage("haiku-done");
        schedule(() => setStage("verdict"), 200);
      }, tBase + HAIKU_DWELL);
    }

    return clearTimers;
  }, [idx, paused, reduce, scenario.exitLayer]);

  // Auto-advance to the next scenario after the verdict hold.
  useEffect(() => {
    if (stage !== "verdict" || paused) return;
    const t = setTimeout(() => {
      setIdx((i) => (i + 1) % SCENARIOS.length);
    }, VERDICT_HOLD);
    return () => clearTimeout(t);
  }, [stage, paused]);

  function pickScenario(i: number) {
    setPaused(false);
    setIdx(i);
  }

  const elapsed = useMemo(() => {
    let total = 0;
    if (
      stage === "regex-done" ||
      stage === "pattern-active" ||
      stage === "pattern-done" ||
      stage === "haiku-active" ||
      stage === "haiku-done" ||
      (stage === "verdict" && scenario.exitLayer !== null)
    ) {
      total += LAYER_LATENCY.regex;
    }
    if (
      stage === "pattern-done" ||
      stage === "haiku-active" ||
      stage === "haiku-done" ||
      (stage === "verdict" &&
        (scenario.exitLayer === 2 ||
          scenario.exitLayer === 3 ||
          scenario.exitLayer === null))
    ) {
      total += LAYER_LATENCY.pattern;
    }
    if (
      stage === "haiku-done" ||
      (stage === "verdict" &&
        (scenario.exitLayer === 3 || scenario.exitLayer === null))
    ) {
      total += LAYER_LATENCY.haiku;
    }
    return total;
  }, [stage, scenario.exitLayer]);

  const layerStates: Record<"regex" | "pattern" | "haiku", LayerState> = {
    regex: layerStateFor("regex", stage, scenario.exitLayer),
    pattern: layerStateFor("pattern", stage, scenario.exitLayer),
    haiku: layerStateFor("haiku", stage, scenario.exitLayer),
  };

  return (
    <div
      className="border border-graphite-dark/20 p-6 md:p-8"
      style={{ borderRadius: "var(--radius)" }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
        <span className="font-mono text-xs uppercase tracking-wider text-graphite">
          // cascada · interactiva
        </span>
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className={`block h-1.5 w-1.5 rounded-full transition-colors ${
              paused ? "bg-graphite/40" : "hero-dot bg-ink"
            }`}
          />
          <span className="font-mono text-xs uppercase tracking-wider text-ink">
            {paused ? "pausado · hover" : "running"} · {elapsed} ms / 200 ms p95
          </span>
        </div>
      </div>

      {/* Scenario chips */}
      <div className="mb-6 flex flex-wrap gap-2">
        {SCENARIOS.map((s, i) => {
          const active = i === idx;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => pickScenario(i)}
              className={`group inline-flex items-center gap-2 border px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] transition-colors ${
                active
                  ? "border-ink bg-ink text-paper"
                  : "border-graphite-dark/25 text-graphite hover:border-ink hover:text-ink"
              }`}
              style={{ borderRadius: "var(--radius)" }}
            >
              <span
                aria-hidden
                className={`h-1 w-1 rounded-full ${
                  active ? "bg-paper" : "bg-graphite/50"
                }`}
              />
              {s.label}
            </button>
          );
        })}
      </div>

      {/* Live request line */}
      <div className="mb-4 flex items-baseline gap-2 font-mono text-xs leading-relaxed text-ink md:text-sm">
        <span className="text-graphite">$ claude</span>
        <motion.span
          key={scenario.id}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
          className="break-words"
        >
          &quot;{scenario.prompt}&quot;
        </motion.span>
      </div>

      {/* Cascade row */}
      <div className="grid items-stretch gap-px overflow-hidden bg-graphite-dark/15 md:grid-cols-[1fr_auto_1fr_auto_1fr]">
        <LayerCell
          n="1"
          name="Regex"
          latency={`~${LAYER_LATENCY.regex} ms`}
          example="emails · tarjetas · AWS keys · JWTs"
          state={layerStates.regex}
        />
        <Connector active={layerStates.regex === "skipped"} />
        <LayerCell
          n="2"
          name="Pattern"
          latency={`~${LAYER_LATENCY.pattern} ms`}
          example=".env · id_rsa · *.pem · paths internos"
          state={layerStates.pattern}
        />
        <Connector active={layerStates.pattern === "skipped"} />
        <LayerCell
          n="3"
          name="Haiku judge"
          latency={`~${LAYER_LATENCY.haiku} ms`}
          example="reglas en lenguaje natural · contexto"
          state={layerStates.haiku}
        />
      </div>

      {/* Verdict bar */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-graphite-dark/15 pt-4">
        <span className="font-mono text-xs uppercase tracking-wider text-graphite">
          // veredicto
        </span>
        <motion.div
          key={`${scenario.id}-${stage}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{
            opacity: stage === "verdict" ? 1 : 0.35,
            y: stage === "verdict" ? 0 : 4,
          }}
          transition={{ duration: 0.4 }}
        >
          {scenario.verdict === "PASS" ? (
            <span className="inline-flex items-center gap-3 font-mono text-xs uppercase tracking-wider text-ink">
              <span aria-hidden className="h-4 w-1 bg-graphite/50" />
              <span>PASS</span>
              <span className="text-graphite">→ upstream · forwarded</span>
            </span>
          ) : (
            <ActionPill
              action={scenario.verdict as Action}
              rule={scenario.rule}
            />
          )}
        </motion.div>
      </div>

      <p className="mt-6 max-w-3xl font-mono text-xs leading-relaxed text-graphite">
        // si una capa más barata ya decidió, no se llama a la siguiente. costo
        y latencia importan.
      </p>
    </div>
  );
}

type LayerState = "idle" | "active" | "matched" | "skipped" | "passed";

function layerStateFor(
  layer: "regex" | "pattern" | "haiku",
  stage: Stage,
  exit: ExitLayer | null,
): LayerState {
  const order: Record<typeof layer, ExitLayer> = {
    regex: 1,
    pattern: 2,
    haiku: 3,
  };
  const myN = order[layer];

  // Map stage → layer being touched.
  const activeLayer: ExitLayer | null =
    stage === "regex-active" || stage === "regex-done"
      ? 1
      : stage === "pattern-active" || stage === "pattern-done"
        ? 2
        : stage === "haiku-active" || stage === "haiku-done"
          ? 3
          : null;

  if (stage === "idle") return "idle";

  if (stage === "verdict") {
    if (exit === null) {
      // PASS — every layer ran and skipped.
      return "skipped";
    }
    if (myN === exit) return "matched";
    if (myN < exit) return "skipped";
    return "idle";
  }

  if (activeLayer !== null && myN < activeLayer) return "skipped";
  if (
    activeLayer === myN &&
    (stage === "regex-active" || stage === "pattern-active" || stage === "haiku-active")
  ) {
    return "active";
  }
  if (activeLayer === myN && (stage === "regex-done" || stage === "pattern-done" || stage === "haiku-done")) {
    return exit === myN ? "matched" : "skipped";
  }
  return "idle";
}

function LayerCell({
  n,
  name,
  latency,
  example,
  state,
}: {
  n: string;
  name: string;
  latency: string;
  example: string;
  state: LayerState;
}) {
  const tone =
    state === "matched"
      ? "bg-paper border-l-4 border-ink shadow-[inset_0_0_0_1px_rgba(28,27,24,0.12)]"
      : state === "active"
        ? "bg-paper border-l-4 border-graphite-dark"
        : state === "skipped"
          ? "bg-paper opacity-55"
          : "bg-paper";

  const stateLabel: Record<LayerState, string> = {
    idle: "// idle",
    active: "// matching…",
    matched: "// match ✓",
    skipped: "// skipped",
    passed: "// passed",
  };

  return (
    <div className={`relative flex flex-col gap-2 p-5 transition-all duration-300 ${tone}`}>
      <div className="flex items-baseline justify-between gap-2 font-mono text-sm">
        <span className="flex items-baseline gap-2">
          <span className="text-graphite">capa {n}</span>
          <span className="text-base font-medium text-ink">{name}</span>
        </span>
        {state === "active" ? (
          <span aria-hidden className="block h-1 w-1 animate-pulse rounded-full bg-ink" />
        ) : null}
      </div>
      <span className="font-mono text-sm text-graphite-dark">{latency}</span>
      <p className="font-mono text-xs leading-relaxed text-graphite-dark">{example}</p>
      <span
        className={`font-mono text-[11px] uppercase tracking-wider ${
          state === "matched"
            ? "font-semibold text-ink"
            : state === "active"
              ? "text-ink"
              : "text-graphite"
        }`}
      >
        {stateLabel[state]}
      </span>
    </div>
  );
}

function Connector({ active }: { active: boolean }) {
  return (
    <div className="flex items-center justify-center bg-paper px-2 py-2 md:px-3">
      <svg
        viewBox="0 0 24 12"
        className={`h-3 w-6 transition-colors ${
          active ? "text-ink" : "text-graphite/50"
        }`}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        aria-hidden
      >
        <path d="M0 6 L20 6" strokeLinecap="round" />
        <path d="M16 2 L20 6 L16 10" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="sr-only">luego</span>
    </div>
  );
}
