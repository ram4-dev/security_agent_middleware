# Specs — Tranquera (Platanus Hack 26 · Team 22)

> Spec-Driven Development (SDD) para **Tranquera** — el firewall de Claude Code corporativo.
> Cada componente vive en su propio `.md`.
>
> **Identidad de marca** (paleta, tipografía, voz, wordmark): [`../identidad/design.md`](../identidad/design.md). Input obligatorio para todo lo que tenga UI o copy.

---

## Visión rápida

Plataforma de enforcement de políticas de seguridad de datos para asistentes AI corporativos, focalizada inicialmente en **Claude Code**. Las empresas configuran `ANTHROPIC_BASE_URL` apuntando a nuestro proxy modificable; el proxy aplica reglas no-code en runtime con cascada Regex → Pattern → LLM judge multiprovider (<200 ms overhead); el admin no técnico arma reglas con un visual builder; un AI Suggestor propone reglas nuevas en base a logs. La expansión multi-provider vive en specs 12–16.

Las **4 layers** del producto:

```
Layer 4: AI Suggestor          (spec 08) ───────────────────────┐
Layer 3: Admin Backoffice       (spec 04) — visual rule builder │
Layer 2: Interceptor Engine     (spec 01) — proxy modificable   │
Layer 1: Claude Code (cliente)                                  │
                                                                ▼
       (compliance-ready, regulator-friendly, LATAM-first)
```

---

## Índice

| # | Componente | Archivo | Estado |
|---|---|---|---|
| 00 | Constitution (principios, stack, convenciones) | [00-constitution.md](./00-constitution.md) | living |
| 01 | Engine / Interceptor (proxy modificable) | [01-engine-interceptor.md](./01-engine-interceptor.md) | parcial avanzado: regex, NL multiprovider, REDACT/WARN/LOG/BLOCK y atribución por token; Layer 2 pattern runtime y VDB prefilter pendientes |
| 02 | VDB Bootstrap (reglas NL + embeddings) | [02-vdb-bootstrap.md](./02-vdb-bootstrap.md) | pendiente: seed VDB/embeddings/prefilter; hoy el judge evalúa reglas NL activas sin vector prefilter |
| 03 | Landing Page | [03-landing-page.md](./03-landing-page.md) | v1 aplicado; checklist interno pendiente de reconciliar |
| 04 | Admin Web | [04-admin-web.md](./04-admin-web.md) | parcial avanzado: auth, rules, events, team, dashboard home y suggestions landed; métricas API/dashboard formal, edit de sugerencias y WARN notif pendientes |
| 06 | Pitch & Demo | [06-pitch-demo.md](./06-pitch-demo.md) | pendiente: no se ve carpeta `pitch/` con deck/script/runbook/video |
| 07 | Requirements & Docs técnicos | [07-requirements-docs.md](./07-requirements-docs.md) | pendiente: faltan `README.dev.md`, `docs/api.md`, `docs/runbook.md` |
| 08 | AI Suggestor (Layer 4) | [08-ai-suggestor.md](./08-ai-suggestor.md) | parcial: API/cron y UI existen; faltan CLI, embeddings/backfill, clustering real e idempotencia por cluster_signature |
| 09 | Google Docs Policy Import | [09-google-workspace-import.md](./09-google-workspace-import.md) | implementado: form, API import, source_hint y badge `// gdoc` |
| 11 | Policy Packs (plantillas curadas) | [11-policy-packs.md](./11-policy-packs.md) | backlog (idea, sin tasks) |
| 12 | Provider Abstraction / Multi-provider Core | [12-provider-abstraction.md](./12-provider-abstraction.md) | parcial: metadata protocol/integration y ruta OpenAI-compatible; falta NormalizedRequest/registry formal y Responses API |
| 13 | OpenAI-compatible Adapter | [13-openai-compatible-adapter.md](./13-openai-compatible-adapter.md) | implementado salvo smokes/docs externos Aider y streaming-client formal |
| 14 | Harness Integrations | [14-harness-integrations.md](./14-harness-integrations.md) | parcial: opencode funciona vía OpenAI-compatible; faltan guías copiables, smoke scripts, Pi/Aider/LiteLLM/Codex/Gemini |
| 15 | Judge Provider Abstraction | [15-judge-provider-abstraction.md](./15-judge-provider-abstraction.md) | implementado y smoke OpenCode Go realizado localmente |
| 16 | Skill + Multi-provider Setup | [16-skill-multi-provider-setup.md](./16-skill-multi-provider-setup.md) | draft inicial: script modular para opencode/Anthropic creado; skill pendiente |
| 17 | Local Judge Runtime Integration | [17-local-judge-runtime.md](./17-local-judge-runtime.md) | nuevo: implementación pendiente |
| 18 | Local Judge Service | [18-local-judge-service.md](./18-local-judge-service.md) | nuevo: implementación pendiente |
| 19 | Local Judge Dataset & Evaluation | [19-local-judge-dataset-eval.md](./19-local-judge-dataset-eval.md) | parcial inicial: dataset smoke, validador, generador, benchmark/scoring y export SFT; teacher online y benchmarks reales pendientes |
| 20 | Local Judge Training Pipeline | [20-local-judge-training.md](./20-local-judge-training.md) | nuevo: implementación pendiente |
| 21 | Local Judge Deployment & Observability | [21-local-judge-deployment-observability.md](./21-local-judge-deployment-observability.md) | nuevo: implementación pendiente |

> El antiguo spec `05-user-web.md` (playground multi-rol) fue retirado el 2026-05-09. El "user" final del producto es el dev que usa Claude Code real, no un playground separado.

> **Auth + multi-tenancy** (Auth.js v5 + Google OAuth + CLI device flow): no tiene spec dedicado, vive como sección dentro de `04-admin-web.md` (modelo de session, callback de org-resolution, tablas `cli_tokens`/`cli_device_codes`). Si se vuelve grande, partir a `09-auth-and-cli.md`.

> **Specialized Local Judge**: specs 17–21 bajan a implementación la propuesta conceptual de `docs/concepts/`: runtime en interceptor, servicio vLLM, dataset/evaluación, training y deployment/observabilidad. En estas specs `LOG` representa allow/pass público y `ESCALATE` es solo estado interno de fallback.

---

## Cómo agarrar una task

1. Abrí el spec del componente que te interesa.
2. Mirá la sección **Tasks** — cada item es ≤ 4 h y tiene su criterio de "done".
3. Creá branch `feature/<spec-id>-<slug>` (ej. `feature/01-proxy-skeleton`).
4. **1 PR ↔ 1 task**. Mencioná en el PR description qué task del spec cerrás.
5. En el PR pegá un mini-checklist de la sección Acceptance Criteria del spec que tu task afecta.

## Reglas para escribir / modificar specs

- **Antes de codear**, si ves que un spec está incompleto o ambiguo, abrí PR al spec primero.
- No mezclar cambios de spec con cambios de código en el mismo PR.
- Si una task tarda más de 4 h, partila — no extiendas el alcance.
- Los specs son fuente de verdad: si el código diverge, el código está mal (o el spec necesita update primero).

## Estado de los specs

El estado canónico vive en la tabla de índice de arriba. Muchos specs arrancaron como **draft**, pero varios ya están parciales o implementados; cuando una spec tenga todas sus acceptance criteria cubiertas por código mergeado a `main`, marcala como **`v1`** o **implementado** y reconciliá sus checklists internos.

## Track del hack

🛡️ **AI Security** — Platanus Hack 26 · Buenos Aires.
Ver `../research/landscape.md` para contexto de mercado (la idea elegida es una variante focalizada en Claude Code corporativo de la **Idea C** del landscape) y `../research/papers.md` para referencias técnicas.
