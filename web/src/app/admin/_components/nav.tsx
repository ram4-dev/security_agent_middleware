"use client";
/* eslint-disable react/jsx-no-comment-textnodes */

import Link from "next/link";
import { usePathname } from "next/navigation";

export const NAV_ITEMS = [
  { href: "/admin/events", label: "eventos", caption: "lo que pasa" },
  { href: "/admin/rules", label: "reglas", caption: "qué controla" },
  { href: "/admin/team", label: "equipo", caption: "quién pasa" },
  { href: "/admin/suggestions", label: "sugerencias", caption: "por aprobar" },
  { href: "/admin/analytics", label: "analíticas", caption: "métricas" },
] as const;

export function AdminNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1" aria-label="navegación admin">
      {NAV_ITEMS.map((item) => {
        const active =
          pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            onClick={onNavigate}
            className={`group flex items-center gap-3 border-l-2 px-3 py-2.5 transition-colors ${
              active
                ? "border-ink bg-ink/[0.06] text-ink"
                : "border-transparent text-graphite hover:border-graphite-dark/40 hover:bg-ink/[0.03] hover:text-ink"
            }`}
            style={{ borderRadius: "0 var(--radius) var(--radius) 0" }}
          >
            <span
              aria-hidden
              className={`block h-1.5 w-1.5 transition-colors ${
                active ? "bg-ink" : "bg-graphite/30 group-hover:bg-graphite-dark"
              }`}
            />
            <span className="flex flex-col">
              <span className="text-base font-medium lowercase tracking-tight">
                {item.label}
              </span>
              <span className="font-mono text-[11px] uppercase tracking-wider text-graphite">
                // {item.caption}
              </span>
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
