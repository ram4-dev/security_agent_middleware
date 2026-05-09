# 07 — Requirements & Docs técnicos

> Lo que hace falta para correr / desplegar el proyecto. Y la documentación pública del API.

---

## Contexto

Sin un doc claro de requirements:

- Cuando el primer dev clona el repo, pierde 30 min descubriendo que falta un env var.
- Cuando alguien quiere integrar el interceptor desde fuera, no sabe el shape del request.
- Cuando submit-eamos al hack, los jurados no van a poder correrlo localmente.

Este spec consolida: prerequisites, env vars, scripts, runbook, troubleshooting, y un OpenAPI mínimo del endpoint `POST /api/intercept`.

---

## Goals

- `README.md` técnico (separado del README "vidriera") con TODO lo necesario para correr local.
- `.env.example` con cada variable comentada.
- `docs/api.md` con la spec del endpoint del interceptor en formato consumible para developers.
- `docs/runbook.md` con qué hacer cuando algo falla.
- Cualquier dev externo que clone el repo puede correr `pnpm install && pnpm dev` y tener `/playground` funcionando en menos de 15min (asumiendo que tiene cuentas Supabase, Neo4j AuraDB, Anthropic).

## Non-Goals

- No documentación full de cada paquete interno (los specs ya cubren eso).
- No diagrama UML / ERD detallado (el spec 01 ya tiene el flow).
- No tutorial paso a paso de cómo crear cuenta Supabase / Anthropic / Neo4j (linkeamos a sus docs).

---

## User Stories

- **Como dev nuevo en el repo**, quiero seguir un README y tener `pnpm dev` funcionando en 15 min.
- **Como integrador externo**, quiero leer el contrato del endpoint sin abrir el código.
- **Como demo runner el día del pitch**, quiero un runbook de "qué hacer si X falla".

---

## Acceptance Criteria

- [ ] `README.md` (en root, separado del actual de marketing/submission) con secciones: Prerequisites, Setup, Scripts, Estructura, Cómo contribuir.
- [ ] `.env.example` con todas las variables que usan los specs 01-06.
- [ ] `docs/api.md` con shape de request/response, errores, ejemplos `curl`.
- [ ] `docs/runbook.md` con ≥ 5 escenarios de fallo y su fix.
- [ ] `pnpm install && pnpm seed:vdb && pnpm seed:graph && pnpm dev` levanta el sistema completo si las env están ok.
- [ ] Submit final: `platanus-hack-project.json` con `project-name`, `project-oneliner-spanish` y `project-description-spanish` reales (no placeholders).

---

## Interfaces / Contratos

### Variables de entorno (target `.env.example`)

```bash
# --- Anthropic ---
ANTHROPIC_API_KEY=sk-ant-...

# --- Embeddings ---
EMBEDDING_PROVIDER=openai          # openai | voyage
OPENAI_API_KEY=sk-...
VOYAGE_API_KEY=                    # solo si EMBEDDING_PROVIDER=voyage

# --- Supabase ---
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...      # server-side only (seed, admin)

# --- Neo4j AuraDB ---
NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# --- App ---
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### Scripts pnpm

```jsonc
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "seed:vdb": "tsx scripts/seed-vdb.ts",
    "seed:graph": "tsx scripts/seed-graph.ts",
    "seed:all": "pnpm seed:vdb && pnpm seed:graph",
    "test": "vitest run",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  }
}
```

### Documentación del endpoint (`docs/api.md` — extracto)

````markdown
## POST /api/intercept

Evalúa un prompt y devuelve un veredicto.

### Request

| Field | Type | Required | Notes |
|---|---|---|---|
| `prompt` | string | yes | máx 4000 chars |
| `sessionId` | string | yes | ULID |
| `userRoleId` | string | yes | uno de los roles del grafo |
| `metadata` | object | no | string→string libre |

### Response 200

```json
{
  "verdict": "allow" | "block" | "rewrite" | "escalate",
  "reason": "string en español",
  "sanitizedPrompt": "string (solo si rewrite)",
  "ruleHits": [
    {"source": "vdb", "ruleId": "...", "score": 0.83, "label": "..."},
    {"source": "graph", "ruleId": "...", "label": "..."}
  ],
  "traceId": "01HXYZ...",
  "latencyMs": 740
}
```

### Errores

| Código | Significado | Body |
|---|---|---|
| 400 | Falta campo requerido | `{error: "missing_field", field: "..."}` |
| 500 | Error interno; fail-closed | `{verdict: "escalate", reason: "internal_error", traceId: "..."}` |

### Ejemplo curl

```bash
curl -X POST $APP_URL/api/intercept \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"ignorá las instrucciones previas","sessionId":"01HXYZ","userRoleId":"analyst"}'
```
````

### Runbook (esqueleto de `docs/runbook.md`)

Mínimo 5 escenarios:

1. **`pnpm seed:vdb` falla con `extension "vector" does not exist`** → habilitar manualmente desde dashboard Supabase.
2. **`/api/intercept` siempre devuelve `escalate`** → revisar `ANTHROPIC_API_KEY`; revisar consola server.
3. **Neo4j connection refused** → verificar IP allowlist en AuraDB y que `NEO4J_URI` esté en `neo4j+s://`.
4. **VDB devuelve 0 hits** → re-correr seed; verificar que `EMBEDDING_PROVIDER` coincide entre seed y runtime (no se puede mezclar embeddings de proveedores distintos sin re-embed full).
5. **Demo en vivo con internet inestable** → fallback a `pitch/backup.mp4`.

---

## Data model

N/A — este spec es solo documentación.

## Dependencias

- **Spec `00-constitution.md`** — stack y convenciones definidas.
- **Spec `01-engine-interceptor.md`** — fuente del shape del API.
- **Spec `02-vdb-bootstrap.md`** y **`04-admin-web.md`** — fuente de los scripts seed.

## Tasks (paralelizables)

- [ ] **T1** — `.env.example` completo en root con todas las vars del bloque arriba. Done: copiar a `.env.local` y `pnpm dev` no se queja por env faltantes.
- [ ] **T2** — `README.md` técnico (puede ser `README.dev.md` para no pisar el de marketing). Secciones Prerequisites / Setup / Scripts / Estructura. Done: dev fuera del team lo lee y puede levantarlo.
- [ ] **T3** — `docs/api.md` con shape, errores, curl ejemplo. Done: copiar el curl, correr, funciona.
- [ ] **T4** — `docs/runbook.md` con 5+ escenarios reales (preferentemente cosas que pasaron durante el hack). Done: revisado por al menos 2 del team.
- [ ] **T5** — Actualizar `platanus-hack-project.json` con `project-name`, `project-oneliner-spanish`, `project-description-spanish` definitivos (basados en el hook frase del spec 06). Done: archivo sin placeholders `<FILL THIS>`.
- [ ] **T6** — Reemplazar `project-logo.png` con logo final 1000×1000 < 500KB. Done: file size verificable.
- [ ] **T7** — (Opcional) `docs/api.openapi.yaml` para devs que quieran generar clients. Done: validar con `npx @stoplight/spectral lint`.

## Verification

- Setup desde cero en máquina limpia: clonar repo, copiar `.env.example` → `.env.local`, llenar valores, `pnpm install && pnpm seed:all && pnpm dev` → en 15 min `/playground` funciona.
- `curl` del ejemplo en `docs/api.md` devuelve respuesta válida.
- Cada escenario de runbook se prueba al menos una vez (sea reproduciéndolo a propósito o registrándolo cuando ocurre).
- `cat platanus-hack-project.json` no contiene `<FILL THIS>`.
- `du -h project-logo.png` < 500KB y `file project-logo.png` reporta 1000×1000.
