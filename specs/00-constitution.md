# 00 — Constitution

> Principios, stack y convenciones que **todos los specs heredan**.
> Cualquier excepción a esta constitution se discute en grupo antes de codear.

---

## Visión del producto

Construir un **interceptor de prompts** que se planta entre el usuario y el modelo, y que para cada prompt:

1. Lo embebe y lo busca contra una **VDB de reglas semánticas** (Supabase + pgvector).
2. Lo evalúa contra un **grafo de reglas estructurales** (Neo4j + Cypher) usando rol del usuario, recurso pedido y políticas explícitas.
3. Hace que **Haiku 4.5** decida un veredicto: `allow | block | rewrite | escalate`.
4. Devuelve el veredicto + un *trace* auditable.

Target inicial: **fintech / banking LATAM** que necesita evidencia auditable para LGPD / Habeas Data Argentina (ver `research/landscape.md` § Idea C).

---

## Principios (no negociables)

1. **Todo prompt pasa por el interceptor antes de tocar el modelo.** No hay "bypass para casos urgentes".
2. **Trazabilidad sobre velocidad.** Cada decisión genera un `traceId` con qué reglas matchearon, en qué orden y qué dijo Haiku. Si tenemos que elegir, latencia se sacrifica primero.
3. **VDB es la fuente de verdad semántica. Grafo es la fuente de verdad estructural.** No duplicar reglas entre los dos. Si una regla se puede expresar como grafo, va al grafo.
4. **Sin PII en logs sin redacción.** Antes de loggear, pasar por un redactor (ej. regex de DNI/CUIT/email + `[REDACTED]`).
5. **Specs > código.** Si el código no coincide con su spec, el código se ajusta o el spec se actualiza con PR — nunca se acepta divergencia silenciosa.
6. **Idempotencia en seeds y migrations.** Re-correr un script no debe duplicar datos.
7. **Demo > documentación bonita.** Para el hack: si una pantalla no se ve en la demo de 3min, no es prioridad.

---

## Stack canónico

| Capa | Tech | Razón |
|---|---|---|
| LLM de decisión | **Anthropic Claude Haiku 4.5** vía SDK oficial | Latencia + costo bajos para clasificación, prompt caching activo |
| LLM de embeddings | **OpenAI `text-embedding-3-small`** o **Voyage `voyage-3-lite`** | Free tier suficiente para 48h |
| Vector DB | **Supabase Postgres + extensión `pgvector`** | 1 cuenta para auth + storage + vectores |
| Graph DB | **Neo4j AuraDB free tier** + queries Cypher | Free 200k nodos, alcanza para demo |
| Frontends | **Next.js 16 App Router** + **shadcn/ui** + **Tailwind** | Standard, deploy directo a Vercel |
| Hosting | **Vercel** (Functions Node runtime, no Edge — necesitamos drivers) | Preview por PR para QA paralelo |
| Auth | **Supabase Auth** con magic links — mock OK para el hack | Cero fricción, sin OAuth real |
| Package manager | **pnpm** | Monorepo limpio si dividimos en `apps/` |
| Lenguaje | TypeScript estricto en frontend y backend | — |

---

## Convenciones

### Idioma
- **Código y comentarios**: inglés.
- **Specs, copy de UI, errores user-facing**: español rioplatense.
- **Nombres de archivos en specs**: `NN-slug-en-ingles.md` (numerados para orden de lectura).

### Branching y PRs
- `main` siempre deployable.
- `feature/<spec-id>-<slug>` — ej. `feature/01-anthropic-client`.
- 1 PR ↔ 1 task del spec correspondiente.
- PR description: link al spec y task que cerrás + mini-checklist de acceptance criteria afectados.
- Squash merge.

### Estructura de repo (target)
```
platanus-hack-26-ar-team-22/
├── specs/                    # estos specs
├── research/                 # ya existe, no tocar
├── apps/
│   ├── web/                  # landing + user web + admin web (Next.js 16)
│   └── api/                  # opcional: si algún día separamos del web
├── packages/
│   ├── interceptor/          # core del engine, reusable
│   ├── db/                   # clientes Supabase + Neo4j
│   └── shared/               # tipos comunes (Verdict, Rule, Trace)
├── seeds/                    # corpus inicial de reglas (markdown)
└── scripts/                  # seed-vdb, seed-graph, etc.
```

> Si alguien quiere arrancar más simple (single Next.js app), está OK también — pero esa decisión va en spec `07-requirements-docs.md`.

### Naming
- Verdicts: literal strings `"allow" | "block" | "rewrite" | "escalate"`.
- Tablas Supabase: `snake_case` plural (ej. `rules`, `intercept_logs`).
- Nodos Neo4j: `PascalCase` singular (`User`, `Role`, `Resource`, `Rule`).
- Componentes React: `PascalCase`. Hooks: `useCamelCase`.

### Variables de entorno
Toda env var nueva se documenta en `07-requirements-docs.md` y `.env.example`. Sin env documentada → no merge.

---

## Out of scope global (no construimos esto en 48h)

- Auth real con OAuth corporate / SSO.
- Multi-tenant / aislamiento por organización.
- Rate limiting avanzado / quotas por user.
- Métricas de producción (Datadog, Sentry) — usar `console.log` estructurado.
- Tests E2E exhaustivos — solo smoke tests del happy path.
- Internacionalización (solo es-AR).
- Mobile-responsive perfecto (solo desktop para la demo).

---

## Aún por definir (decidir en kickoff)

- [ ] `project-name` final → actualizar `platanus-hack-project.json`.
- [ ] `project-oneliner-spanish` → idem.
- [ ] Si separamos `apps/web` y `apps/api` o todo en una sola Next.js app.
- [ ] Provider de embeddings: OpenAI vs Voyage (decidir en spec `02-vdb-bootstrap.md` cuando se mida latencia).
