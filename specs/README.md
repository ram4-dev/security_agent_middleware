# Specs — Platanus Hack 26 · Team 22

> Spec-Driven Development (SDD) para el interceptor de prompts.
> Inspirado en `arxiv.org/pdf/2602.00180`. Cada componente vive en su propio `.md`.

---

## Índice

| # | Componente | Archivo | Bloqueadores |
|---|---|---|---|
| 00 | Constitution (principios, stack, convenciones) | [00-constitution.md](./00-constitution.md) | — |
| 01 | Engine / Interceptor (motor central) | [01-engine-interceptor.md](./01-engine-interceptor.md) | 00, 02 |
| 02 | VDB Bootstrap (seed inicial al deploy) | [02-vdb-bootstrap.md](./02-vdb-bootstrap.md) | 00 |
| 03 | Landing Page | [03-landing-page.md](./03-landing-page.md) | 00 |
| 04 | Admin Web (dashboards + back office + roles) | [04-admin-web.md](./04-admin-web.md) | 00, 01 |
| 05 | User Web (playground del prompt) | [05-user-web.md](./05-user-web.md) | 00, 01 |
| 06 | Pitch & Demo | [06-pitch-demo.md](./06-pitch-demo.md) | todos |
| 07 | Requirements & Docs técnicos | [07-requirements-docs.md](./07-requirements-docs.md) | 00, 01 |

---

## Cómo agarrar una task

1. Abrí el spec del componente que te interesa.
2. Mirá la sección **Tasks** — cada item es ≤ 4h y tiene su criterio de "done".
3. Creá branch `feature/<spec-id>-<slug>` (ej. `feature/01-anthropic-client`).
4. **1 PR ↔ 1 task**. Mencioná en el PR description qué task del spec cerrás.
5. En el PR pegá un mini-checklist de la sección Acceptance Criteria del spec que tu task afecta.

## Reglas para escribir / modificar specs

- **Antes de codear**, si ves que un spec está incompleto o ambiguo, abrí PR al spec primero.
- No mezclar cambios de spec con cambios de código en el mismo PR.
- Si una task tarda más de 4h, partila — no extiendas el alcance.
- Los specs son fuente de verdad: si el código diverge, el código está mal (o el spec necesita update primero).

## Estado de los specs

Todos los specs están en estado **draft** hasta que arranque el kickoff de implementación. Marcá un spec como **`v1`** cuando todas sus acceptance criteria estén cubiertas por código mergeado a `main`.

## Track del hack

🛡️ **AI Security** — Platanus Hack 26 · Buenos Aires.
Ver `../research/landscape.md` para contexto de mercado y `../research/papers.md` para referencias técnicas.
