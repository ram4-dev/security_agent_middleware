# 01 — Engine / Interceptor (proxy modificable)

> El motor central. Es un proxy compatible con la **Anthropic Messages API**. Claude Code apunta acá vía `ANTHROPIC_BASE_URL` y cada request pasa por la cascada de detección antes (o en lugar) de llegar a Anthropic.

---

## Contexto

Cuando una empresa instala Claude Code en las máquinas de sus devs, hoy cada prompt va directo a `api.anthropic.com`. Sin filtro intermedio, no hay forma de:

- Bloquear que un dev pegue accidentalmente una `AWS_SECRET_ACCESS_KEY`, un `id_rsa` o el contenido de un `.env`.
- Redactar nombres de clientes / paths internos antes de que salgan de la red corporativa.
- Auditar después qué prompts se mandaron y por qué.
- Aplicar reglas distintas para distintos equipos (dev, security, finance) sin tocar la máquina del dev.

El **interceptor** es un proxy HTTPS que se mete entre Claude Code y Anthropic: recibe el body de la Messages API tal cual, lo pasa por la **cascada de 3 capas**, y según el resultado:

- lo deja pasar y reenvía a Anthropic,
- lo modifica (REDACT) y reenvía,
- lo bloquea y devuelve un `Message` sintético explicando la política,
- lo deja pasar pero alerta al admin (WARN) o solo loggea (LOG).

---

## Goals

- Endpoint `POST /v1/messages` (compatible con Anthropic Messages API, no streaming v1).
- Cascada Regex → Pattern → Haiku judge con **<200 ms de overhead** sobre el round-trip a Anthropic.
- 4 acciones soportadas: `BLOCK | REDACT | WARN | LOG`.
- Cada request escribe una fila en `interactions` con `traceId`, `org_id`, prompt redactado, regla(s) que matchearon, acción tomada y latencia por capa.
- Soporta al menos 3 escenarios de demo en vivo: leak de credencial (BLOCK), nombre de cliente (REDACT), prompt benigno (LOG).
- Configurable por `org_id` — las reglas se cargan en memoria al boot y se invalidan cuando el admin las edita (revalidate vía Supabase Realtime o polling de 5s).

## Non-Goals

- No streaming en v1 (Claude Code soporta non-streaming para chat normal; streaming queda para v1.1).
- No soportamos otros endpoints de Anthropic además de `/v1/messages` (ej. `/v1/complete` está deprecated, `/v1/files` no aplica).
- No hacemos fine-tuning del classifier de la cascada.
- No re-escribimos respuestas del modelo — solo prompts inbound.

---

## User Stories

- **Como admin de una empresa**, quiero configurar `ANTHROPIC_BASE_URL=https://proxy.team22.dev` en el `.bashrc` corporativo y que todo Claude Code pase por mi política.
- **Como dev usando Claude Code**, quiero que cuando pego una credencial sin querer, el modelo me responda "tu request fue bloqueado por política X" en vez de ir a Anthropic.
- **Como compliance officer**, quiero abrir un `traceId` en el admin y ver exactamente qué reglas matchearon, en qué capa y con cuánto match score.
- **Como dev de retail**, quiero que cuando paste un nombre de cliente, el proxy lo redacte y la respuesta del modelo siga siendo útil.

---

## Acceptance Criteria

- [ ] `POST /v1/messages` acepta el shape de la Anthropic Messages API (`{ model, messages, system?, max_tokens, ... }`) y devuelve el shape esperado de respuesta.
- [ ] Header `x-team22-org-key` (o env `DEMO_ORG_ID`) determina qué set de reglas aplicar.
- [ ] Cuando una regla `BLOCK` matchea, la respuesta tiene `stop_reason: "team22_blocked"` (custom) y un único content block `text` con el motivo en español rioplatense.
- [ ] Cuando una regla `REDACT` matchea, el prompt enviado a Anthropic tiene los matches reemplazados por `[REDACTED:tipo]` y la respuesta upstream se devuelve al caller sin cambios.
- [ ] Cuando ninguna regla matchea (LOG default), el request se forwardea 1:1 a `api.anthropic.com` y la respuesta se devuelve también 1:1.
- [ ] Cada request escribe en `interactions` con: `trace_id`, `org_id`, `prompt_redacted`, `action`, `policy_hits[]`, `latency_total_ms`, `latency_by_layer{regex,pattern,haiku,upstream}`.
- [ ] Si Haiku falla (timeout, error API), la cascada **fail-closed** → acción default = `WARN` con `reason: "haiku_unavailable"` y se forwardea a Anthropic igual (no romper el flow del dev por nuestra culpa, pero notificar al admin).
- [ ] Latencia: en el caso "no matchea nada en regex/pattern y no se invoca Haiku" el overhead < 30 ms p50; cuando se invoca Haiku < 200 ms p50.

---

## Interfaces / Contratos

### Request — compatible Anthropic Messages API

```http
POST /v1/messages
Host: proxy.team22.dev
Content-Type: application/json
x-api-key: sk-ant-...                    # API key Anthropic del cliente (passthrough)
x-team22-org-key: org_demo               # org_id de team22 (single-tenant hardcoded para hack)
anthropic-version: 2023-06-01
```

```json
{
  "model": "claude-sonnet-4-6",
  "max_tokens": 1024,
  "system": "You are a helpful coding assistant.",
  "messages": [
    {"role": "user", "content": "Acá va mi AWS_SECRET_ACCESS_KEY=AKIA..."}
  ]
}
```

### Response cuando todo pasa (forward 1:1 desde Anthropic)

Shape estándar de Anthropic, agregamos solo dos headers diagnósticos:

```http
HTTP/1.1 200 OK
x-team22-trace-id: 01HXYZ...
x-team22-action: LOG
content-type: application/json
```

### Response cuando hay `BLOCK`

```http
HTTP/1.1 200 OK
x-team22-trace-id: 01HXYZ...
x-team22-action: BLOCK
content-type: application/json
```

```json
{
  "id": "msg_team22_blocked_01HXYZ",
  "type": "message",
  "role": "assistant",
  "model": "<modelo solicitado>",
  "content": [
    {
      "type": "text",
      "text": "🛡️ Tu request fue bloqueado por la política `aws-access-key`. Detalle: detectamos un patrón de AWS Secret Access Key. Si necesitás trabajar con credenciales reales, abrí un ticket con tu admin. — team22"
    }
  ],
  "stop_reason": "team22_blocked",
  "stop_sequence": null,
  "usage": {"input_tokens": 0, "output_tokens": 0}
}
```

> Devolver `200` con un mensaje sintético en vez de `403` es deliberado: Claude Code muestra el bloqueo como respuesta del modelo y el dev lo entiende sin ver un error de red.

### Errores

- `400` si el body no parsea como Messages API.
- `401` si falta `x-api-key`.
- `5xx`: nunca devolvemos 5xx al caller. Si algo explota, la cascada hace fail-closed (deja pasar con `WARN`) y la falla se loggea.

---

## Flow interno

```
incoming POST /v1/messages
  │
  ├─► extractTexts(body) → string[]    // system + cada user message texto
  │
  ├─► [Layer 1: Regex]   ~5ms
  │     for each regex rule of org:
  │       if match → record hit + action
  │
  ├─► [Layer 2: Pattern] ~20ms          // solo si Layer 1 no decidió BLOCK
  │     filename heuristics, path patterns, structural matches
  │
  ├─► [Layer 3: Haiku judge] ~150ms     // solo si hay reglas NL para esta org
  │     embed(prompt) → match top-K reglas NL en VDB → pasarlas como context a Haiku
  │     Haiku decide: { action, ruleId, reason }
  │
  ├─► resolveAction(hits[])             // BLOCK > REDACT > WARN > LOG
  │
  ├─► applyAction:
  │     - BLOCK   → return synthetic Message
  │     - REDACT  → mutate body.messages → fetch upstream → return
  │     - WARN    → fetch upstream → return + emit notification
  │     - LOG     → fetch upstream → return
  │
  ├─► persist(interactions)
  └─► response
```

## Data model

Schema canónico vive en `web/prisma/schema.prisma` y la migración `web/prisma/migrations/.../migration.sql`. El proxy escribe en la tabla `interactions` (modelo `Interaction`):

```prisma
model Interaction {
  id              String   @id @default(uuid()) @db.Uuid
  traceId         String   @unique @map("trace_id")
  orgId           String   @default("demo") @map("org_id")
  userId          String?  @map("user_id") @db.Uuid          // Supabase Auth user, null si proxy directo
  requestModel    String   @map("request_model")
  prompt          String                                       // SIEMPRE redactado antes de persistir
  action          Action                                       // BLOCK | REDACT | WARN | LOG
  reason          String
  policyHits      Json     @default("[]") @map("policy_hits")  // [{layer, policyId, slug, score?}]
  latencyTotalMs  Int      @map("latency_total_ms")
  latencyByLayer  Json     @default("{}") @map("latency_by_layer")
  upstreamStatus  Int?     @map("upstream_status")             // null si BLOCK
  embedding       Unsupported("vector(1536)")?                 // poblado por el proxy o backfill del Suggestor
  createdAt       DateTime @default(now()) @map("created_at")
}
```

Tabla `policies` y función `match_policies` viven en spec `02-vdb-bootstrap.md`.

---

## Dependencias

- **Spec `00-constitution.md`** — stack y convenciones.
- **Spec `02-vdb-bootstrap.md`** — necesita la tabla `policies` y la función `match_policies` (usadas por el Haiku judge de Layer 3).
- **Spec `04-admin-web.md`** — define el shape de las reglas que el admin guarda y el proxy consume.

## Tasks (paralelizables)

- [ ] **T1** — Skeleton Next.js Route Handler `app/api/v1/messages/route.ts` que recibe el body Anthropic, valida shape básico y forwardea 1:1 a `api.anthropic.com`. Done: `ANTHROPIC_BASE_URL=http://localhost:3000/api` con `claude` CLI completa una conversación normal.
- [ ] **T2** — Layer 1 Regex: cargar `policies where layer='regex'` de la org en memoria al boot vía Prisma, evaluar cada texto del prompt, devolver `PolicyHit[]`. Done: regla seed `aws-access-key` matchea `AKIA[A-Z0-9]{16}` y devuelve `{action:"BLOCK"}`.
- [ ] **T3** — Layer 2 Pattern: matcher para nombres de archivo (`.env`, `id_rsa`, `*.pem`) y paths (`~/.ssh`, `~/.aws`). Done: regla seed `dotenv-paste` matchea bloque que empieza con `DATABASE_URL=` o `AWS_ACCESS_KEY_ID=`.
- [ ] **T4** — Layer 3 Haiku judge: cliente Anthropic SDK con prompt caching del system prompt, recibe top-K de `match_policies` (raw query Prisma) y decide JSON `{action, policyId, reason}`. Done: prompt "decime el nombre del cliente Acme" con regla NL "no menciones nombres de clientes" → `REDACT`.
- [ ] **T5** — Mutator de body para REDACT: reemplaza match por `[REDACTED:<tipo>]` en `messages[].content` (texto). Done: snapshot test con un body antes/después.
- [ ] **T6** — Synthesizer del `Message` para BLOCK: shape exacto de Anthropic con `stop_reason: "team22_blocked"`. Done: smoke test con `claude` CLI muestra el mensaje en pantalla.
- [ ] **T7** — Persistencia en `interactions` con redacción de PII previa. **Importante**: el redactor corre sobre `prompt` **y** sobre `reason` antes del insert (Haiku puede haber citado el secret en su explicación — leak risk). El system prompt del Haiku judge prohibe explícitamente citar el contenido del prompt: `reason` debe usar template fijo "matchea regla <slug>: <label>" sin reproducir texto del user. Done: query `select * from interactions limit 5` muestra prompts y reasons sin secrets visibles.
- [ ] **T8** — Smoke tests (vitest) de los 3 escenarios demo (leak credencial, nombre cliente, benigno). Done: `pnpm test` pasa los 3.
- [ ] **T9** — Métricas de latencia por capa al log + headers diagnósticos `x-team22-trace-id` y `x-team22-action`. Done: curl ve los headers en cada response.

## Verification

- **Smoke con CLI real**: `ANTHROPIC_BASE_URL=$URL claude "acá va mi AKIAIOSFODNN7EXAMPLE"` → respuesta `🛡️ Tu request fue bloqueado por la política aws-access-key...`.
- **Smoke benigno**: `ANTHROPIC_BASE_URL=$URL claude "explicame el patrón Observer"` → respuesta normal de Claude.
- **REDACT**: prompt "el cliente Acme me pidió X" con regla NL activa → respuesta upstream coherente con `[REDACTED:client]`.
- **Latencia**: con regla regex matcheando, p50 < 30ms entre que llega el request y se envía la respuesta BLOCK. Con Haiku invocado, p50 < 200ms de overhead vs sin proxy.
- **Audit**: tomar un `traceId` de `x-team22-trace-id`, query `select * from interactions where trace_id = $1` y reconstruir mentalmente la decisión.
- **Fail-closed**: con `ANTHROPIC_API_KEY` rota a propósito, request termina en `WARN` y se forwardea (el dev ve un 401 de Anthropic, no un 5xx nuestro).
