# 00 — Constitution

> Principios, stack y convenciones que **todos los specs heredan**.
> Cualquier excepción a esta constitution se discute en grupo antes de codear.

---

## Producto

**Nombre**: **Tranquera** *(palabra rioplatense para la portera rural — deja pasar lo que corresponde, redacta lo sensible, cierra cuando hay que cerrar)*.
**Tagline canónico (institucional)**: *Un paso controlado entre la intención y la respuesta.*
**Categoría B2B (sales/landing)**: *Firewall de Claude Code corporativo.*
**Posicionamiento**: aduana silenciosa, no escudo. No se vende como "AI safety" — se vende como **control y trazabilidad**.

> Identidad visual completa (paleta, tipografía, voz, action pills, logo): ver [`../identidad/design.md`](../identidad/design.md).

---

## Visión del producto

Construir una **plataforma de enforcement de políticas de seguridad de datos para asistentes AI corporativos**, focalizada en **Claude Code**. Una empresa instala Claude Code en las máquinas de sus devs y configura `ANTHROPIC_BASE_URL` apuntando a nuestro interceptor. Desde ese momento:

1. Cada request de Claude Code pasa por el **proxy** (Layer 2), que es **modificable**: puede dejar pasar, redactar, bloquear o solo loggear.
2. **Admins no técnicos** definen reglas con un **visual rule builder** en el back-office (Layer 3) — sin escribir regex a mano.
3. El proxy aplica las reglas en runtime con una **cascada en 3 capas** (Regex → Pattern → Haiku judge) que mantiene **<200 ms de overhead** sobre el round-trip a Anthropic.
4. Después de N días de uso, un **AI Suggestor** (Layer 4) detecta patrones recurrentes en los logs y propone nuevas reglas que el admin aprueba o descarta.

Target inicial: **empresas LATAM que dan Claude Code a sus devs y necesitan evidencia auditable de que datos sensibles (PII, credenciales, paths internos, código propietario) no están saliendo en cada prompt** — driver regulatorio: LGPD (Brasil), Habeas Data (Argentina), LFPDPPP (México). Ver `research/landscape.md` § Idea C.

---

## Las 4 capas

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4 — AI Suggestor                                     │
│  Después de N días, sugiere reglas nuevas a partir de logs. │
│  Approval queue en el admin.  (spec 08)                     │
└─────────────────────────────────────────────────────────────┘
                            ▲
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3 — Admin Backoffice (Web UI)                        │
│  - Visual rule builder (no-code)                            │
│  - Dashboards: real-time events, what-if, riesgo evitado    │
│  - User & role management                                   │
│  - Approval queue de reglas auto-sugeridas  (spec 04)       │
└─────────────────────────────────────────────────────────────┘
                            ▲ rules synced
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2 — Interceptor Engine (proxy modificable)           │
│  - Compatible con Anthropic Messages API                    │
│  - Cascada: Regex (~5ms) → Pattern (~20ms) → Haiku (~150ms) │
│  - Acciones: BLOCK / REDACT / WARN / LOG                    │
│  - <200 ms overhead target  (spec 01)                       │
└─────────────────────────────────────────────────────────────┘
                            ▲ HTTPS — ANTHROPIC_BASE_URL
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — Claude Code (developer's machine)                │
└─────────────────────────────────────────────────────────────┘
```

## Las 4 acciones del proxy

| Acción | Qué hace | Cuándo se usa |
|---|---|---|
| **BLOCK** | Rechaza el request. Devuelve un `Message` sintético explicando qué política se violó. Claude Code lo muestra como respuesta del modelo. | PII crítica, credenciales, info regulada |
| **REDACT** | Reemplaza partes sensibles con `[REDACTED:tipo]` y reenvía a Anthropic. La respuesta vuelve normal al user. | Nombres de clientes, paths internos, snippets de código propietario |
| **WARN** | Deja pasar tal cual, pero marca el evento y notifica al admin. | Patrones sospechosos no críticos |
| **LOG** | Solo registra. Sirve para baseline antes de promover una regla a un nivel más estricto. | Auditoría, learning |

## Pipeline de detección (cascada)

```
request → [Regex layer ~5ms]
         ├─ match? → action → end
         └─ no match → [Pattern layer ~20ms]
                       ├─ match? → action → end
                       └─ no match → [Haiku judge ~150ms, opcional]
                                     ├─ flag? → action → end
                                     └─ pass → forward to Anthropic
```

- **Capa 1 — Regex** (instantáneo): emails, números de tarjeta, AWS keys, JWTs, etc.
- **Capa 2 — Pattern matching** (rápido): paths sensibles, nombres de archivos comunes (`.env`, `id_rsa`, `secrets.json`).
- **Capa 3 — Haiku judge** (smart): solo cuando el admin define una regla en lenguaje natural ("no menciones nombres de clientes"). Haiku evalúa con contexto. La VDB de reglas NL le da few-shots a Haiku via prompt caching.

---

## Principios (no negociables)

1. **Todo request de Claude Code pasa por el proxy antes de tocar Anthropic.** No hay "bypass para casos urgentes".
2. **Trazabilidad sobre velocidad.** Cada decisión genera un `traceId` con qué reglas matchearon, en qué capa y qué dijo Haiku. Si tenemos que elegir, latencia se sacrifica primero.
3. **Cascada antes que LLM.** No se llama a Haiku si una capa más barata ya decidió. Costo y latencia importan.
4. **Sin PII en logs sin redacción.** Antes de loggear, el prompt se redacta (las mismas regex que las reglas BLOCK/REDACT corren primero en el logger).
5. **Specs > código.** Si el código no coincide con su spec, el código se ajusta o el spec se actualiza con PR — nunca se acepta divergencia silenciosa.
6. **Idempotencia en seeds y migrations.** Re-correr un script no debe duplicar datos.
7. **Demo > documentación bonita.** Para el hack: si una pantalla no se ve en la demo de 3min, no es prioridad.
8. **El admin es no técnico.** Toda UX del back-office debe poder ser usada sin saber regex. La regex queda escondida detrás del rule builder visual.

---

## Stack canónico

| Capa | Tech | Razón |
|---|---|---|
| LLM de juicio | **Anthropic Claude Haiku 4.5** vía SDK oficial | Latencia + costo bajos, prompt caching activo |
| LLM de embeddings | **OpenAI `text-embedding-3-small`** o **Voyage `voyage-3-lite`** | Free tier suficiente para 48h |
| DB local | **Postgres 16 + `pgvector`** vía Docker (`pgvector/pgvector:pg16`) | Setup en 30s con `docker compose up`, mismo cliente que prod |
| DB prod | **Supabase Postgres** con extensión `vector` habilitada | Auth + storage + vectores en una cuenta, free tier alcanza |
| ORM | **Prisma** (con `Unsupported("vector(1536)")` para embeddings) | Tipos generados, migraciones declarativas; `match_policies` y el ivfflat van en SQL manual |
| Auth (admin) | **Supabase Auth** (`@supabase/ssr`) con magic links | Solo se usa en `/admin`. En local hay bypass mock |
| Realtime (live feed) | **Polling 2s** en v1; Supabase Realtime cuando deploye en prod | Evita acoplar a una sola plataforma en local |
| Frontends | **Next.js 16 App Router** + **shadcn/ui** + **Tailwind 4** | Standard, deploy directo a Vercel |
| Interceptor (Layer 2) | **Python 3.12 + FastAPI** | Equipo del interceptor lo dev en paralelo. Comparte la misma Postgres que `web/` (lee `policies`, escribe `interactions`) — no usa Prisma; conector Python directo (asyncpg / SQLAlchemy) |
| Hosting (web) | **Vercel** (Functions Node runtime — necesitamos drivers) | Preview por PR para QA paralelo |
| Hosting (interceptor) | A definir (Fly.io / Railway / contenedor en VPS) | Vercel no aplica para el proxy Python; latencia <200ms requiere runtime de larga vida con prompt-cache de Haiku activo |
| Package manager (web) | **pnpm** | — |
| Package manager (interceptor) | **uv** o **poetry** | A definir por el dev del interceptor |
| Lenguajes | TypeScript estricto en `web/`. Python 3.12 con `mypy --strict` en `interceptor/` | — |

> **Out:** Neo4j / cualquier graph DB. La idea original de "grafo de roles + recursos" se reemplaza por reglas declarativas en Postgres + cascada del proxy.

---

## Convenciones

### Idioma
- **Código y comentarios**: inglés.
- **Specs, copy de UI, errores user-facing**: español rioplatense.
- **Nombres de archivos en specs**: `NN-slug-en-ingles.md` (numerados para orden de lectura).

### Branching y PRs
- `main` siempre deployable.
- `feature/<spec-id>-<slug>` — ej. `feature/01-proxy-skeleton`.
- 1 PR ↔ 1 task del spec correspondiente.
- PR description: link al spec y task que cerrás + mini-checklist de acceptance criteria afectados.
- Squash merge.

### Estructura de repo (target)
```
platanus-hack-26-ar-team-22/
├── docker-compose.yml        # Postgres + pgvector para dev local
├── specs/                    # estos specs (fuente de verdad)
├── identidad/                # sistema de marca (paleta, wordmark, voz)
├── research/                 # ya existe, no tocar
├── web/                      # Next.js 16 — landing + admin
│   ├── prisma/
│   │   ├── schema.prisma     # modelos canónicos (TS y Python siguen este shape)
│   │   └── migrations/       # SQL idempotente: extension vector, match_policies, etc.
│   └── src/
├── interceptor/              # Python 3.12 + FastAPI — proxy modificable (Layer 2)
│   │                         # En desarrollo en branch separada; aún no commiteado a main.
│   │                         # Lee/escribe la misma DB que `web/` vía DSN compartido.
│   ├── pyproject.toml
│   └── src/
├── seeds/                    # corpus inicial de reglas (NL + regex/pattern)
└── scripts/                  # seed-vdb, run-suggestor, etc.
```

> El schema Prisma en `web/prisma/` es la **fuente de verdad** del data model. El `interceptor/` accede a la misma DB pero **no** ejecuta migraciones — `web/prisma/migrations/` es la única vía. Los enums, tabla `policies`, función `match_policies` y constraints viven ahí.

### Naming
- Acciones del proxy: literal strings `"BLOCK" | "REDACT" | "WARN" | "LOG"` (uppercase, viajan así en JSON y en DB).
- Tablas Postgres: `snake_case` plural — las canónicas son **`policies`**, **`interactions`**, **`organizations`** (el spec 02 detalla schemas).
- Modelos Prisma: `PascalCase` singular — `Policy`, `Interaction`, `Organization` (con `@@map(...)` al nombre snake_case).
- Componentes React: `PascalCase`. Hooks: `useCamelCase`.

### Variables de entorno
Toda env var nueva se documenta en `07-requirements-docs.md` y `.env.example`. Sin env documentada → no merge.

---

## Multi-tenancy (goal)

El producto es **multi-tenant por diseño**: cada empresa cliente es una `organization` con su propio set de reglas, su propia API key de Anthropic upstream y sus propios admins. El proxy identifica la `org_id` por:

- Header `x-team22-org-key` que el admin configura en el env de Claude Code de cada dev, **o**
- Subdominio del proxy (`<org>.proxy.team22.dev`) si llegamos a configurar DNS.

Para el hack se acepta **single-tenant hardcoded** (`org_id = 'demo'` en env) siempre y cuando el schema de DB ya tenga la columna `org_id` y los queries la filtren — la migración a multi-tenant real debe ser solo configuración, no rewrite.

> **TODO post-hack (multi-tenant real)**: habilitar **Row Level Security** en `policies`, `interactions` y `rule_suggestions` con policy `org_id = current_setting('request.jwt.claims', true)::jsonb->>'org_id'`. Sin esto, cuando activemos Supabase Realtime en `/admin/events`, el channel filtra por tabla pero no por org → leak entre tenants. Ver finding I8 del audit del 2026-05-09.

---

## Out of scope global (no construimos esto en 48h)

- SSO corporativo / SAML / SCIM.
- Streaming responses de Anthropic (solo non-streaming en v1 del proxy).
- Rate limiting avanzado / quotas por dev.
- Métricas de producción (Datadog, Sentry) — usar `console.log` estructurado.
- Tests E2E exhaustivos — solo smoke tests del happy path.
- Internacionalización (solo es-AR).
- Mobile-responsive perfecto (solo desktop para la demo).
- Soporte de otros assistants (Cursor, Cline, etc.) — solo Claude Code.
- Encriptación de logs en reposo más allá de lo que Supabase ofrece por default.

---

## Aún por definir (decidir en kickoff)

- [x] ~~`project-name` final~~ → **Tranquera** (ya en `platanus-hack-project.json`).
- [x] ~~`project-oneliner-spanish`~~ → **"Un paso controlado entre la intención y la respuesta."** (ya en JSON).
- [ ] Provider de embeddings: OpenAI vs Voyage (decidir en spec `02-vdb-bootstrap.md` cuando se mida latencia).
- [ ] Si el proxy se deploya en Vercel Functions Node runtime o si para latencia <200ms necesitamos un tier dedicado (Fly.io, Railway).
