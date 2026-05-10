"use client";

import { useEffect, useRef } from "react";

const COLS = 40;
const ROWS = 22;
const VIEW_W = 1600;
const VIEW_H = 900;

const INFLUENCE_RADIUS = 180;
const MAX_OFFSET = 7;
const LERP = 0.12;
const SETTLE_EPSILON = 0.05;

// Ambient drift — the grid breathes on its own when the cursor is gone, so
// the hero never reads as static. Tuned to be barely perceptible.
const AMBIENT_AMP = 1.6; // pixels
const AMBIENT_FREQ_X = 0.0042;
const AMBIENT_FREQ_Y = 0.0058;
const AMBIENT_SPEED = 0.00045; // radians per ms

export function WaveTerrain({ className = "" }: { className?: string }) {
  const ref = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const svg = ref.current;
    if (!svg) return;

    const dx = VIEW_W / (COLS - 1);
    const dy = VIEW_H / (ROWS - 1);

    type Pt = { bx: number; by: number; cx: number; cy: number };
    const grid: Pt[][] = [];
    for (let r = 0; r < ROWS; r++) {
      const row: Pt[] = [];
      for (let c = 0; c < COLS; c++) {
        const bx = c * dx;
        const by = r * dy;
        row.push({ bx, by, cx: bx, cy: by });
      }
      grid.push(row);
    }

    const ns = "http://www.w3.org/2000/svg";
    const root = document.createElementNS(ns, "g");
    svg.appendChild(root);

    const hLines: SVGPathElement[] = [];
    const vLines: SVGPathElement[] = [];
    for (let r = 0; r < ROWS; r++) {
      const p = document.createElementNS(ns, "path");
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", "currentColor");
      p.setAttribute("stroke-width", "1");
      p.setAttribute("opacity", "0.05");
      root.appendChild(p);
      hLines.push(p);
    }
    for (let c = 0; c < COLS; c++) {
      const p = document.createElementNS(ns, "path");
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", "currentColor");
      p.setAttribute("stroke-width", "1");
      p.setAttribute("opacity", "0.04");
      root.appendChild(p);
      vLines.push(p);
    }

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

    let mouse: { x: number; y: number } | null = null;
    let raf = 0;

    const draw = (now: number) => {
      const t = now * AMBIENT_SPEED;
      for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
          const p = grid[r][c];
          // Ambient breathing — every node drifts on a slow sine field.
          // Skipped under reduce-motion via the early-return below.
          const ax = reduce.matches
            ? 0
            : Math.sin(p.bx * AMBIENT_FREQ_X + t) * AMBIENT_AMP;
          const ay = reduce.matches
            ? 0
            : Math.cos(p.by * AMBIENT_FREQ_Y + t * 0.85) * AMBIENT_AMP;
          let tx = p.bx + ax;
          let ty = p.by + ay;
          if (mouse) {
            const dxm = p.bx - mouse.x;
            const dym = p.by - mouse.y;
            const dist = Math.hypot(dxm, dym);
            if (dist > 0 && dist < INFLUENCE_RADIUS) {
              const influence = 1 - dist / INFLUENCE_RADIUS;
              const fall = influence * influence;
              const norm = 1 / dist;
              tx += dxm * norm * MAX_OFFSET * fall;
              ty += dym * norm * MAX_OFFSET * fall;
            }
          }
          p.cx += (tx - p.cx) * LERP;
          p.cy += (ty - p.cy) * LERP;
        }
      }

      for (let r = 0; r < ROWS; r++) {
        const row = grid[r];
        let d = `M${row[0].cx.toFixed(2)} ${row[0].cy.toFixed(2)}`;
        for (let c = 1; c < COLS; c++) {
          d += `L${row[c].cx.toFixed(2)} ${row[c].cy.toFixed(2)}`;
        }
        hLines[r].setAttribute("d", d);
      }
      for (let c = 0; c < COLS; c++) {
        let d = `M${grid[0][c].cx.toFixed(2)} ${grid[0][c].cy.toFixed(2)}`;
        for (let r = 1; r < ROWS; r++) {
          d += `L${grid[r][c].cx.toFixed(2)} ${grid[r][c].cy.toFixed(2)}`;
        }
        vLines[c].setAttribute("d", d);
      }

      if (reduce.matches) {
        raf = 0;
        return;
      }
      // Ambient drift means we always keep ticking when motion is allowed.
      raf = requestAnimationFrame(draw);
    };

    const ensureRunning = () => {
      if (!raf && !reduce.matches) raf = requestAnimationFrame(draw);
    };

    const onMove = (e: PointerEvent) => {
      const rect = svg.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      if (px < 0 || py < 0 || px > rect.width || py > rect.height) {
        if (mouse) {
          mouse = null;
          ensureRunning();
        }
        return;
      }
      mouse = {
        x: (px / rect.width) * VIEW_W,
        y: (py / rect.height) * VIEW_H,
      };
      ensureRunning();
    };
    const onLeave = () => {
      if (mouse) {
        mouse = null;
        ensureRunning();
      }
    };

    if (!reduce.matches) raf = requestAnimationFrame(draw);
    else draw(0); // single static paint for reduce-motion users
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerleave", onLeave);
    document.addEventListener("mouseleave", onLeave);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("mouseleave", onLeave);
      root.remove();
    };
  }, []);

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="xMidYMid slice"
      className={`pointer-events-none ${className}`}
      aria-hidden
    />
  );
}
