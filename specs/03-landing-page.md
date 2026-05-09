# 03 — Landing Page

> Página pública. Vende el producto a jurados, VCs y curiosos del hack.

---

## Contexto

El equipo va a tener 3 minutos para pitchear y un repo público para que los jurados naveguen después. La landing es la primera impresión cuando alguien abre el link sin contexto.

Para el hack la landing tiene 3 trabajos:

1. Explicar **qué hace el producto** en 5 segundos.
2. Mostrar **por qué importa en LATAM** (gap regulatorio + casos reales).
3. Llevar al visitante al **playground** (`User Web` — spec 05) para que lo pruebe.

No es un sitio para SEO ni para conversión real — es un **showroom**.

---

## Goals

- Página pública en `/` con hero, 3 pasos, "por qué LATAM", CTA al playground.
- Cargar < 1.5s en LCP (es Next.js + estática, debería sobrar).
- Texto en español rioplatense, sin jerga corporativa innecesaria.
- Mobile-friendly al menos para iPhone reciente (no obsesionarse, demo va en desktop).

## Non-Goals

- No formulario de contacto / waitlist real.
- No blog / changelog / docs públicas.
- No internacionalización.
- No analytics complejo (Vercel Analytics on/off OK).

---

## User Stories

- **Como jurado** que recibe el link 30s antes del pitch, quiero entender de qué se trata sin scrollear.
- **Como visitante random**, quiero probar el producto en un click.
- **Como integrante del team** mostrando el repo a alguien fuera del hack, quiero que la URL pública les venda solo.

---

## Acceptance Criteria

- [ ] Ruta `/` renderiza hero con headline + subheadline + CTA primario "Probalo ahora" → `/playground`.
- [ ] Sección "Cómo funciona" con 3 pasos visuales (interceptor → VDB+grafo → veredicto).
- [ ] Sección "Por qué LATAM" cita al menos: PL 2338 (Brasil), S-0071/2025 (Argentina), gap multilingüe (XL-SafetyBench sin pt-BR).
- [ ] Footer con links al repo GitHub, equipo (5 nombres con sus GitHub) y Platanus Hack 26.
- [ ] Deploy en Vercel preview funciona en cada PR a la carpeta `apps/web/app/(landing)/`.
- [ ] Lighthouse Performance ≥ 90 en desktop.

---

## Interfaces / Contratos

### Rutas

| Ruta | Componente | Notas |
|---|---|---|
| `/` | Landing | Hero + cómo funciona + por qué LATAM + footer |
| `/playground` | (spec 05 — User Web) | CTA del hero apunta acá |
| `/admin` | (spec 04 — Admin Web) | No linkeado público; solo para login interno |

### Stack

- Next.js 16 App Router con `'use cache'` donde aplique.
- shadcn/ui (`Button`, `Card`).
- Tailwind con paleta del logo (definir en task T1).
- Imágenes: SVG inline o `next/image` con preload del hero.

### Copy del hero (draft inicial — afinar en task T2)

> **Headline**: "Validá cada prompt antes de que llegue al modelo."
>
> **Subheadline**: "Interceptor con doble validación — semántica (VDB) y estructural (grafo) — pensado para fintech LATAM. Auditable por diseño."
>
> **CTA primario**: "Probalo ahora →" (a `/playground`)
> **CTA secundario**: "Ver en GitHub" (a la URL del repo)

---

## Data model

Sin data model propio — landing es estática.

## Dependencias

- **Spec `00-constitution.md`** — stack y convenciones.
- **Spec `05-user-web.md`** — para que el CTA tenga destino.
- Logo final del proyecto (`project-logo.png` ya existe en root, reemplazar antes de submit).

## Tasks (paralelizables)

- [ ] **T1** — Setup `apps/web` con Next.js 16 + Tailwind + shadcn/ui. Definir paleta basada en el logo. Done: `pnpm dev` muestra "hello".
- [ ] **T2** — Hero + CTAs con copy final en español. Done: render visual aprobado por el equipo (screenshot en PR).
- [ ] **T3** — Sección "Cómo funciona" con 3 cards (Interceptor / Doble validación / Veredicto auditable). Done: cards con iconos y micro-copy.
- [ ] **T4** — Sección "Por qué LATAM" con bloque de citas a las 3 fuentes (PL 2338, S-0071, XL-SafetyBench gap). Done: links a las leyes / paper.
- [ ] **T5** — Footer con team (5 nombres + GH avatars) + link al repo + crédito Platanus Hack 26. Done: links funcionan.
- [ ] **T6** — Deploy en Vercel: configurar proyecto, dominio preview por PR. Done: URL pública compartible.
- [ ] **T7** — Lighthouse audit: hacer pasar Performance ≥ 90, Accessibility ≥ 90. Done: screenshot del Lighthouse en el PR.

## Verification

- Abrir la URL preview en navegador limpio (incógnito) y leer el hero en voz alta — ¿se entiende qué hace en 5s? Sí/no.
- Click en "Probalo ahora" lleva a `/playground` y carga sin errores.
- Mobile DevTools (iPhone 14): no hay overflow horizontal, los CTAs son tappeables.
- `lighthouse https://<preview>.vercel.app --view` → Performance ≥ 90.
