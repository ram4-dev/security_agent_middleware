// Install terminal: command lives at the top with a copy-to-clipboard
// button; the output below typewrites itself once the terminal scrolls
// into view. Reduced-motion users get the full output immediately.
/* eslint-disable react/jsx-no-comment-textnodes */
"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "framer-motion";

const COMMAND = "npx tranquera setup";

const LOG = `  ▎ tranquera · login
  └─ app  https://tranquera.app

  · iniciando device flow…  ok

  Abrí el browser y aprobá:
      https://tranquera.app/cli/connect?code=KXZ2-RZ96

  · esperando aprobación…  ok

  ▎ tranquera · setup
  ├─ proxy   https://proxy.tranquera.app
  ├─ shell   zsh
  ├─ rc      ~/.zshrc
  └─ member  jaime@acme.com · org=acme

  · agregué la export a ~/.zshrc
  · verificando proxy…  ok

  Listo. Reabrí tu terminal y usá Claude Code igual que siempre.`;

const CHAR_MS = 8;

export function InstallTerminal() {
  const reduce = useReducedMotion();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const inView = useInView(containerRef, { once: true, amount: 0.3 });
  const [visible, setVisible] = useState(reduce ? LOG.length : 0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (reduce) {
      setVisible(LOG.length);
      return;
    }
    if (!inView) return;
    let i = 0;
    const id = setInterval(() => {
      i++;
      setVisible(i);
      if (i >= LOG.length) clearInterval(id);
    }, CHAR_MS);
    return () => clearInterval(id);
  }, [inView, reduce]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(COMMAND);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API may be blocked; degrade silently.
    }
  }

  const showing = LOG.slice(0, visible);
  const finished = visible >= LOG.length;

  return (
    <div
      ref={containerRef}
      className="overflow-hidden border border-graphite-dark/20 bg-ink"
      style={{ borderRadius: "var(--radius)" }}
    >
      <div className="flex items-center justify-between border-b border-paper/10 px-5 py-3 font-mono text-[11px] uppercase tracking-wider text-paper/55">
        <span>// terminal</span>
        <span className="hidden md:inline">// onboarding · ~ 30 segundos</span>
      </div>
      <div className="px-6 py-7 font-mono text-sm leading-relaxed text-paper md:px-10 md:py-9 md:text-base">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-baseline gap-3">
            <span className="text-paper/45">$</span>
            <span className="text-paper">{COMMAND}</span>
          </div>
          <button
            type="button"
            onClick={copy}
            aria-label="copiar comando"
            className="inline-flex items-center gap-2 border border-paper/20 px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider text-paper/65 transition-colors hover:border-paper/55 hover:text-paper"
            style={{ borderRadius: "var(--radius)" }}
          >
            <span aria-hidden className="block h-1.5 w-1.5 bg-paper/50" />
            {copied ? "copiado ✓" : "copiar"}
          </button>
        </div>
        <pre className="mt-5 whitespace-pre-wrap text-[13px] leading-relaxed text-paper/75 md:text-sm">
          {showing}
          {!finished ? (
            <span aria-hidden className="terminal-cursor inline-block h-[1em] w-[0.6ch] translate-y-[2px] bg-paper" />
          ) : null}
        </pre>
      </div>
    </div>
  );
}
