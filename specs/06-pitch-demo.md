# 06 — Pitch & Demo

> Cómo vendemos lo que construimos. 3 minutos, 1 demo en vivo, 1 ask.

---

## Contexto

En Platanus Hack 26 cada equipo tiene 3 minutos para pitchear ante jurados. La diferencia entre un proyecto técnico decente y uno **memorable** suele estar acá: el pitch.

El proyecto cae en la **Idea C (ProxyShield LATAM)** del `research/landscape.md`. Eso ya nos da la narrativa de mercado lista (regulación + gap multilingüe + dolor real en fintech). El trabajo de este spec es traducir esa narrativa en **un guion de 3 min + slides + demo script + plan B en caso de fallo de internet**.

---

## Goals

- Pitch de **3 minutos exactos** con tiempos marcados (problema 30s + producto 30s + demo 90s + métricas/ask 30s).
- Slides exportadas a PDF y al repo (`pitch/deck.pdf`).
- **Demo script step-by-step** que cualquiera del equipo pueda ejecutar (no solo el speaker principal).
- Video de 60s grabado del playground como backup en caso de internet caído.
- 1 frase memorable / hook que la gente repita después.

## Non-Goals

- Pitch de 10 min, demo larga, deep dive técnico — eso es para una segunda etapa post-hack.
- Material en inglés (track del hack es regional).
- Métricas inventadas — solo mostramos lo que realmente medimos.

---

## User Stories

- **Como speaker del pitch**, quiero saber qué digo segundo a segundo y qué pantalla mostrar en cada momento.
- **Como speaker de backup** (si el principal se enferma o le entra ansiedad), quiero poder leer el script y dar el mismo pitch.
- **Como jurado**, después de los 3 min quiero recordar **una sola cosa** del proyecto y querer entrar al GitHub.

---

## Acceptance Criteria

- [ ] `pitch/deck.pdf` versionado en el repo, ≤ 10 slides.
- [ ] `pitch/script.md` con guion segundo-a-segundo y pantalla a mostrar en cada bloque.
- [ ] `pitch/demo-runbook.md` con los pasos exactos del demo en vivo, con screenshots de qué tiene que verse en cada paso.
- [ ] Video backup `.mp4` ≤ 30MB grabado en local con OBS o Loom, cubriendo los 3 ejemplos del playground.
- [ ] Pitch completo en el ensayo final dura entre 2:50 y 3:05 (cronometrado por alguien del team distinto al speaker).
- [ ] Hook frase ≤ 12 palabras decidida y escrita en la primera slide.

---

## Interfaces / Contratos

### Estructura del pitch (slides)

| # | Slide | Tiempo | Pantalla / visual |
|---|---|---|---|
| 1 | Hook + nombre del proyecto + 1 frase | 0:00 – 0:15 | Slide |
| 2 | El problema en LATAM (PL 2338, S-0071, gap pt-BR/es-AR) | 0:15 – 0:45 | Slide con mapa LATAM + 3 leyes |
| 3 | Qué es el interceptor (1 diagrama) | 0:45 – 1:10 | Slide con el flow del whiteboard digitalizado |
| 4 | Demo en vivo — playground | 1:10 – 2:40 | Browser en `/playground` |
| 5 | Cómo funciona por dentro (VDB + grafo + Haiku) | 2:40 – 2:55 | Slide |
| 6 | Ask + repo + team | 2:55 – 3:00 | Slide |

### Demo en vivo (90s)

```
[1:10] Speaker: "Acá tienen el playground. Voy a actuar como un analista pidiendo cosas."
[1:15] Click "Pregunta benigna" → verdict ALLOW (verde).
       Speaker: "Pregunta normal, lo deja pasar. Tarda 800ms."
[1:30] Click "Prompt injection" → verdict BLOCK (rojo).
       Speaker: "Acá intentaron jailbreakear. Lo bloqueó porque matcheó esta regla en la VDB."
       (señala el ruleHit en pantalla)
[1:55] Click "Pedido fuera de rol" → verdict BLOCK (rojo).
       Speaker: "Esto es lo distinto: no es injection, es una request legítima... pero el rol 'analyst' no tiene
                permiso. Lo dijo el grafo."
       (señala el ruleHit del source: graph)
[2:20] Speaker: "Cada decisión queda auditable. Acá ven el traceId..."
       (cambiar a tab de Supabase con la fila visible o screenshot pre-cargado)
[2:40] Speaker: "Y eso es lo que va al regulador."
```

### Frase hook (candidatas — elegir una en task T2)

- "Validá cada prompt antes de que llegue al modelo."
- "El interceptor que el regulador LATAM va a pedir."
- "Doble validación: semántica y estructural. Auditable por diseño."

---

## Data model

N/A — todos artefactos son archivos en el repo bajo `pitch/`.

## Dependencias

- **Specs 01, 02, 03, 04, 05** — necesitan estar funcionando para que la demo no se rompa en vivo.
- `research/landscape.md` — fuente de los datos del slide 2.

## Tasks (paralelizables)

- [ ] **T1** — Estructura de slides en `pitch/deck.{slides|pdf}`. 6 slides con los títulos de la tabla. Done: PDF exportado, ≤ 10 slides.
- [ ] **T2** — Decidir frase hook (votación equipo) y escribirla en slide 1. Done: 1 frase elegida, ≤ 12 palabras.
- [ ] **T3** — `pitch/script.md` con guion segundo-a-segundo. Done: speaker hace ensayo y queda entre 2:50–3:05.
- [ ] **T4** — `pitch/demo-runbook.md` con pasos del demo + screenshots de cada paso esperado. Done: alguien que no programó puede correrlo siguiendo el doc.
- [ ] **T5** — Video backup grabado del playground (los 3 ejemplos). Done: archivo `.mp4` en `pitch/backup.mp4`, ≤ 30MB.
- [ ] **T6** — Diagrama del slide 3 (interceptor → VDB + grafo → Haiku → verdict) digitalizado del whiteboard. Done: imagen en `pitch/assets/architecture.png`.
- [ ] **T7** — Ensayo final de equipo: 2 vueltas cronometradas + feedback round. Done: acta en `pitch/rehearsal-notes.md` con cosas a mejorar.

## Verification

- Cronometrar el pitch completo 2 veces: ambas entre 2:50 y 3:05.
- Probar la demo en vivo con internet apagado → fallback al video graba en menos de 5s.
- Pedir a alguien fuera del equipo (otro hacker) que escuche el pitch y le pregunte: "¿qué hace el producto?". Si en una frase puede explicarlo, el pitch funciona.
- Slide 1 visible desde 5m de distancia (texto grande, contraste).
