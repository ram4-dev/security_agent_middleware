"use client";
/* eslint-disable react/jsx-no-comment-textnodes */

import { useState } from "react";

type Theme = "beam" | "ink" | "paper";
const COOKIE = "tranquera_theme";

const THEMES: { id: Theme; label: string; hint: string }[] = [
  { id: "beam", label: "beam", hint: "high contrast" },
  { id: "ink", label: "ink", hint: "default" },
  { id: "paper", label: "paper", hint: "monitor" },
];

export function ThemeSwitcher({ initial }: { initial: Theme }) {
  const [theme, setTheme] = useState<Theme>(initial);

  function pick(next: Theme) {
    if (next === theme) return;
    setTheme(next);
    // Persist for next SSR render and update the wrapper attribute live so
    // the choice applies without a reload.
    document.cookie = `${COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
    const el = document.querySelector<HTMLElement>("[data-admin-shell]");
    if (el) el.setAttribute("data-theme", next);
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-graphite">
        // tema
      </span>
      <div
        role="radiogroup"
        aria-label="tema"
        className="flex overflow-hidden border border-graphite-dark/25"
        style={{ borderRadius: "var(--radius)" }}
      >
        {THEMES.map((t) => {
          const active = theme === t.id;
          return (
            <button
              key={t.id}
              role="radio"
              aria-checked={active}
              type="button"
              onClick={() => pick(t.id)}
              title={`${t.label} · ${t.hint}`}
              className={`flex-1 px-2 py-1.5 font-mono text-[10px] uppercase tracking-wider transition-colors ${
                active
                  ? "bg-ink text-paper"
                  : "bg-paper text-graphite hover:bg-paper-soft/60 hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
