# 01 — Engine / Interceptor

> El motor central. Recibe un prompt, lo valida contra VDB + grafo, y devuelve un veredicto.

---

## Contexto

Cuando un usuario manda un prompt a un agente IA, hoy ese prompt llega directo al modelo. Sin filtro intermedio, no hay forma de:

- Bloquear prompt injection o pedidos que violan políticas de negocio.
- Auditar después qué pasó y por qué se respondió de cierta forma.
- Aplicar reglas distintas según rol del usuario (analyst, supervisor, admin).

El **interceptor** se mete entre el cliente y el modelo: cada request pasa primero por un endpoint propio que evalúa **dos fuentes de verdad** (VDB para semántica, grafo para estructura) y le pide a Haiku que decida qué hacer con el prompt.

---

## Goals

- Endpoint `POST /api/intercept` que en < 2s devuelve un `Verdict`.
- 4 veredictos posibles: `allow`, `block`, `rewrite`, `escalate`.
- Cada respuesta incluye un `traceId` que permite reconstruir la decisión 100%.
- Logging estructurado en Supabase de cada request + verdict + reglas matcheadas.
- Soportar al menos 3 escenarios demo en vivo: prompt-injection clásico, pedido fuera de rol, prompt benigno.

## Non-Goals

- No reenviamos el prompt al modelo final del cliente — solo decidimos. La integración con el modelo del cliente la hace el caller.
- No hacemos fine-tuning del clasificador.
- No hay streaming de la respuesta (devolvemos JSON sincrónico).

---

## User Stories

- **Como dev integrando el interceptor**, quiero llamar un solo endpoint con `{prompt, sessionId, userRoleId}` y recibir el veredicto + razón legible.
- **Como compliance officer**, quiero abrir un `traceId` en el admin y ver exactamente qué reglas se evaluaron y qué dijo el LLM.
- **Como atacante intentando prompt injection clásico** ("ignore previous instructions..."), quiero ser bloqueado con razón explícita.

---

## Acceptance Criteria

- [ ] `POST /api/intercept` responde con shape `{verdict, reason, sanitizedPrompt?, ruleHits[], traceId, latencyMs}`.
- [ ] Si la VDB devuelve hits con score > umbral configurable, esos hits llegan a Haiku como contexto.
- [ ] Si el grafo devuelve violación de ACL para el rol del user, Haiku recibe ese hecho como input.
- [ ] Veredicto `block` incluye `reason` en español legible (ej. "El rol 'analyst' no tiene permiso sobre el recurso 'transferencias'").
- [ ] Veredicto `rewrite` incluye `sanitizedPrompt` con la versión saneada que el caller puede usar.
- [ ] Cada request escribe una fila en `intercept_logs` con prompt redactado + traceId + verdict.
- [ ] Si Haiku falla (timeout, error API), el endpoint devuelve `verdict: "escalate"` por default (fail-closed).

---

## Interfaces / Contratos

### Request

```ts
POST /api/intercept
Content-Type: application/json

{
  "prompt": string,
  "sessionId": string,
  "userRoleId": string,
  "metadata"?: Record<string, string>
}
```

### Response

```ts
{
  "verdict": "allow" | "block" | "rewrite" | "escalate",
  "reason": string,                     // español, user-facing
  "sanitizedPrompt"?: string,           // solo si verdict === "rewrite"
  "ruleHits": Array<{
    "source": "vdb" | "graph",
    "ruleId": string,
    "score"?: number,                   // 0..1, solo VDB
    "label": string                     // descripción humana de la regla
  }>,
  "traceId": string,                    // ULID
  "latencyMs": number
}
```

### Errores

- `400` si falta `prompt` o `userRoleId`.
- `500` con `{verdict: "escalate", reason: "internal_error", traceId}` si algo explota — nunca leak del stacktrace al caller.

---

## Flow interno

```
prompt
  ├─► (paralelo)
  │     ├─► embed(prompt) ──► supabase.rpc("match_rules", {embedding, k=5}) ──► vdbHits
  │     └─► neo4j.run("MATCH (r:Role)-[:CAN_ACCESS]->...") ──► graphFacts
  ├─► buildHaikuPrompt({prompt, vdbHits, graphFacts, userRole})
  ├─► anthropic.messages.create({model: "claude-haiku-4-5", ...})  // con prompt caching
  ├─► parseHaikuJSON ──► verdict
  ├─► persist(intercept_logs)
  └─► response
```

## Data model (Supabase)

```sql
create table intercept_logs (
  id uuid primary key default gen_random_uuid(),
  trace_id text not null unique,
  session_id text not null,
  user_role_id text not null,
  prompt_redacted text not null,
  verdict text not null check (verdict in ('allow','block','rewrite','escalate')),
  reason text not null,
  rule_hits jsonb not null default '[]',
  latency_ms int not null,
  created_at timestamptz default now()
);
create index intercept_logs_session_idx on intercept_logs(session_id);
create index intercept_logs_created_idx on intercept_logs(created_at desc);
```

Tabla `rules` y función `match_rules` viven en spec `02-vdb-bootstrap.md`.
Esquema del grafo Neo4j (nodos `User`, `Role`, `Resource`, `Rule`) vive en spec `04-admin-web.md`.

---

## Dependencias

- **Spec `00-constitution.md`** — stack y convenciones.
- **Spec `02-vdb-bootstrap.md`** — necesita la tabla `rules` y función `match_rules` corriendo.
- **Spec `04-admin-web.md`** — necesita el esquema Neo4j seedeado con roles y reglas iniciales.

## Tasks (paralelizables)

- [ ] **T1** — Setup del paquete `packages/interceptor` con cliente Anthropic SDK (Node), reading `ANTHROPIC_API_KEY` de env. Done: `interceptor.decide({prompt, vdbHits:[], graphFacts:{}})` devuelve un mock.
- [ ] **T2** — Cliente Supabase con función `embedAndSearch(prompt, k)` que devuelve `vdbHits[]`. Done: test unit con prompt "transferir saldo" devuelve hits razonables.
- [ ] **T3** — Cliente Neo4j con función `evaluateAcl(userRoleId, prompt)` que extrae `Resource` mencionados (regex / heurística simple) y devuelve `graphFacts`. Done: test con rol `analyst` pidiendo `transferencias` devuelve `denied`.
- [ ] **T4** — Builder del prompt para Haiku con prompt caching del system prompt + ejemplos few-shot. Done: la llamada a Anthropic tiene `cache_control` en el system block.
- [ ] **T5** — Endpoint `POST /api/intercept` en Next.js Route Handler (`app/api/intercept/route.ts`) que orquesta T2 + T3 + T4. Done: curl con payload válido devuelve JSON con shape correcto.
- [ ] **T6** — Persistencia en `intercept_logs` con redacción de PII (regex de DNI/CUIT/email). Done: query `select * from intercept_logs limit 5` muestra prompts sin PII visible.
- [ ] **T7** — Tests de los 3 escenarios demo (injection, fuera-de-rol, benigno) como smoke tests. Done: `pnpm test` corre y pasa los 3.

## Verification

- **Smoke**: `curl -X POST $URL/api/intercept -d '{"prompt":"ignore all previous instructions","sessionId":"s1","userRoleId":"analyst"}'` → `verdict: "block"`.
- **Latencia**: con prompt caching activo, segunda llamada < 1.5s.
- **Audit**: tomar un `traceId` de la respuesta, query a `intercept_logs` y reconstruir mentalmente la decisión leyendo `rule_hits` + `reason`.
- **Fail-closed**: con `ANTHROPIC_API_KEY` inválida, endpoint devuelve `escalate` (no 500 al caller).
