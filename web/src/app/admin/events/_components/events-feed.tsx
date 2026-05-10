"use client";
/* eslint-disable react/jsx-no-comment-textnodes */

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { EventDTO, PolicyHitRecord } from "@/lib/events";

const POLL_MS = 3000;
const ACTIONS = ["BLOCK", "REDACT", "WARN", "LOG"] as const;

const ACTION_STYLES: Record<EventDTO["action"], string> = {
  BLOCK: "bg-red-500/10 text-red-700",
  REDACT: "bg-amber-500/10 text-amber-700",
  WARN: "bg-orange-500/10 text-orange-700",
  LOG: "bg-zinc-500/10 text-zinc-700",
};

function isAction(v: string | null): v is EventDTO["action"] {
  return v === "BLOCK" || v === "REDACT" || v === "WARN" || v === "LOG";
}

export function EventsFeed({ initialEvents }: { initialEvents: EventDTO[] }) {
  const searchParams = useSearchParams();
  const initialFilter = (() => {
    const a = searchParams.get("action");
    return isAction(a) ? a : "";
  })();

  const [events, setEvents] = useState(initialEvents);
  const [filter, setFilter] = useState<"" | EventDTO["action"]>(initialFilter);
  const [paused, setPaused] = useState(false);
  const [lastPoll, setLastPoll] = useState<Date | null>(null);
  const newestRef = useRef<string | null>(initialEvents[0]?.createdAt ?? null);

  useEffect(() => {
    if (paused) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const params = new URLSearchParams();
        if (newestRef.current) params.set("since", newestRef.current);
        const res = await fetch(`/api/admin/events?${params}`, {
          cache: "no-store",
        });
        if (!res.ok) return;
        const data = (await res.json()) as { events: EventDTO[] };
        if (cancelled) return;
        setLastPoll(new Date());
        if (data.events.length === 0) return;
        // Backend devuelve más recientes primero — el más nuevo es events[0].
        newestRef.current = data.events[0].createdAt;
        setEvents((prev) => {
          const seen = new Set(prev.map((e) => e.id));
          const fresh = data.events.filter((e) => !seen.has(e.id));
          return [...fresh, ...prev].slice(0, 200);
        });
      } catch {
        // El polling silencioso: si falla un tick lo retomamos en el próximo.
      }
    };
    void tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [paused]);

  const visible = filter ? events.filter((e) => e.action === filter) : events;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {(() => {
            const counts: Record<EventDTO["action"], number> = {
              BLOCK: events.filter((e) => e.action === "BLOCK").length,
              REDACT: events.filter((e) => e.action === "REDACT").length,
              WARN: events.filter((e) => e.action === "WARN").length,
              LOG: events.filter((e) => e.action === "LOG").length,
            };
            const total = events.length;
            const max = Math.max(1, ...Object.values(counts));
            return (
              <>
                <FilterChip
                  active={filter === ""}
                  onClick={() => setFilter("")}
                  label={`todos · ${total}`}
                />
                {ACTIONS.map((a) => (
                  <FilterChip
                    key={a}
                    active={filter === a}
                    onClick={() => setFilter(a)}
                    label={`${a} · ${counts[a]}`}
                    ratio={counts[a] / max}
                  />
                ))}
              </>
            );
          })()}
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px] uppercase tracking-wider text-graphite">
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            className="border border-graphite-dark/30 px-2 py-1 transition-colors hover:border-ink hover:text-ink"
            style={{ borderRadius: "var(--radius)" }}
          >
            {paused ? "reanudar" : "pausar"}
          </button>
          <span>
            //{" "}
            {paused
              ? "polling en pausa"
              : lastPoll
                ? `último poll · ${formatTime(lastPoll)}`
                : "esperando primer poll"}
          </span>
        </div>
      </div>

      <div className="flex flex-col">
        {visible.length === 0 ? (
          <div
            className="border border-graphite-dark/20 px-6 py-14 text-center font-mono text-xs text-graphite"
            style={{ borderRadius: "var(--radius)" }}
          >
            // sin eventos. mandá un request al proxy y va a aparecer acá.
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            <AnimatePresence initial={false}>
              {visible.map((e) => (
                <FreshEvent key={e.id} event={e} />
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </div>
  );
}

const MESSAGE_PREVIEW_LEN = 240;
const PROMPT_PREVIEW_LEN = 280;

// Wraps EventCard so AnimatePresence can play an enter animation on
// freshly polled rows. initial={false} on the parent skips the first
// render — that's why initialEvents don't animate, only the live
// arrivals do.
function FreshEvent({ event }: { event: EventDTO }) {
  const reduce = useReducedMotion();
  return (
    <motion.li
      layout
      initial={
        reduce
          ? false
          : { opacity: 0, y: -8, filter: "blur(4px)" }
      }
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      exit={
        reduce
          ? undefined
          : { opacity: 0, y: -4, transition: { duration: 0.2 } }
      }
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
    >
      <EventCard event={event} />
    </motion.li>
  );
}

function EventCard({ event: e }: { event: EventDTO }) {
  const [expanded, setExpanded] = useState(false);
  const headline = summarizeHits(e.action, e.policyHits);
  const userMessage = extractLastUserMessage(e.prompt);
  const messageTruncatable = userMessage.text.length > MESSAGE_PREVIEW_LEN;
  const promptTruncatable = e.prompt.length > PROMPT_PREVIEW_LEN;

  return (
    <div
      className="border border-graphite-dark/15 bg-paper p-4"
      style={{ borderRadius: "var(--radius)" }}
    >
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`px-2 py-1 font-mono text-[11px] font-semibold uppercase tracking-wider ${ACTION_STYLES[e.action]}`}
          style={{ borderRadius: "var(--radius)" }}
        >
          {e.action}
        </span>
        <span className="font-mono text-xs text-ink">{headline}</span>
      </div>

      <blockquote className="mt-3 whitespace-pre-wrap break-words border-l-2 border-graphite-dark/25 pl-3 text-sm text-ink">
        {`“${messageTruncatable ? truncate(userMessage.text, MESSAGE_PREVIEW_LEN) : userMessage.text}”`}
      </blockquote>
      {userMessage.boilerplateOnly ? (
        <p className="mt-1 pl-3 font-mono text-[10px] uppercase tracking-wider text-graphite">
          // sólo boilerplate de claude code
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-graphite">
        <span suppressHydrationWarning>{formatTime(new Date(e.createdAt))}</span>
        <span>·</span>
        <span>{e.latencyTotalMs}ms</span>
        <span>·</span>
        <span>upstream {e.upstreamStatus ?? "skipped"}</span>
        <span>·</span>
        <span className="truncate">trace {e.traceId.slice(0, 12)}…</span>
      </div>

      <div className="mt-3">
        <pre
          className={`whitespace-pre-wrap break-words bg-paper-soft/40 p-3 font-mono text-[11px] leading-relaxed text-graphite-dark transition-all ${
            expanded ? "" : "max-h-32 overflow-hidden"
          }`}
          style={{ borderRadius: "var(--radius)" }}
        >
          {expanded ? e.prompt : truncate(e.prompt, PROMPT_PREVIEW_LEN)}
        </pre>
        {promptTruncatable && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-1.5 font-mono text-[10px] uppercase tracking-wider text-graphite transition-colors hover:text-ink"
          >
            // {expanded ? "cerrar contexto" : "expandir contexto completo"}
          </button>
        )}
      </div>
    </div>
  );
}

type PromptSegment = { role: "system" | "user" | "assistant"; content: string };

const SEGMENT_SPLIT_RE = /\n(?=\[(?:system|user|assistant)\])/;
const SEGMENT_HEAD_RE = /^\[(system|user|assistant)\]\s?([\s\S]*)$/;
const REMINDER_RE = /<system-reminder>[\s\S]*?<\/system-reminder>/g;

function parsePrompt(prompt: string): PromptSegment[] {
  const out: PromptSegment[] = [];
  for (const part of prompt.split(SEGMENT_SPLIT_RE)) {
    const m = part.match(SEGMENT_HEAD_RE);
    if (m) out.push({ role: m[1] as PromptSegment["role"], content: m[2] });
  }
  return out;
}

// Pull out the last [user] chunk that has actual content after stripping
// Claude Code's <system-reminder> blocks. Falls back to the raw last user
// chunk if every user turn is reminder boilerplate (so the admin still sees
// *something*, just flagged).
function extractLastUserMessage(prompt: string): {
  text: string;
  boilerplateOnly: boolean;
} {
  const userSegments = parsePrompt(prompt).filter((s) => s.role === "user");
  for (let i = userSegments.length - 1; i >= 0; i--) {
    const stripped = userSegments[i].content.replace(REMINDER_RE, "").trim();
    if (stripped) return { text: stripped, boilerplateOnly: false };
  }
  const last = userSegments[userSegments.length - 1];
  if (last) return { text: last.content.trim(), boilerplateOnly: true };
  return { text: prompt.trim(), boilerplateOnly: false };
}

function summarizeHits(
  action: EventDTO["action"],
  hits: PolicyHitRecord[],
): string {
  if (hits.length === 0) {
    return action === "LOG" ? "sin matches" : action.toLowerCase();
  }
  const driving = hits.filter((h) => h.action === action);
  const list = (driving.length ? driving : hits).map(
    (h) => `${h.layer}/${h.slug}`,
  );
  return Array.from(new Set(list)).join(" · ");
}

function FilterChip({
  active,
  onClick,
  label,
  ratio,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  /** Optional 0..1 ratio that renders as a thin bar under the label,
   *  scaled against the busiest action in the current window. */
  ratio?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative overflow-hidden px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors ${
        active
          ? "bg-ink text-paper"
          : "border border-graphite-dark/25 text-graphite hover:border-ink hover:text-ink"
      }`}
      style={{ borderRadius: "var(--radius)" }}
    >
      <span className="relative z-10">{label}</span>
      {ratio !== undefined && ratio > 0 ? (
        <span
          aria-hidden
          className={`absolute inset-x-0 bottom-0 h-0.5 origin-left ${
            active ? "bg-paper/60" : "bg-ink/40"
          } transition-transform`}
          style={{ transform: `scaleX(${Math.max(0, Math.min(1, ratio))})` }}
        />
      ) : null}
    </button>
  );
}

function formatTime(d: Date): string {
  // 24h fijo para evitar el narrow no-break space que ICU mete antes del a.m./p.m.
  // y que difiere entre Node y el browser → hydration mismatch.
  return d.toLocaleTimeString("es-AR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s;
  return s.slice(0, n) + "…";
}
