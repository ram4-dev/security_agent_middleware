# 04 — Admin Web

> Dashboard interno: visibilidad + back office de reglas + roles.

---

## Contexto

Del whiteboard, el lado **ADMIN** tiene 3 zonas:

1. **Dashboards** — métricas de prompts allowed/blocked/rewriten/escalated.
2. **Back Office** — CRUD de reglas (las que viven en VDB y en el grafo).
3. **Roles** — gestión de roles y permisos (nodos del grafo Neo4j).

Sin admin web, no se puede modificar la base de reglas sin meterse a SQL/Cypher manualmente, lo que rompe la promesa de "compliance accesible". Para la demo es **clave** poder mostrar: "miren, agrego una regla acá y al toque el interceptor la usa".

---

## Goals

- 4 pantallas: Login (mock), Dashboard, Back Office Reglas, Roles.
- CRUD completo de reglas VDB (crear, listar, editar, eliminar — con re-embedding al editar).
- CRUD de nodos `Role`, `Resource` y aristas `CAN_ACCESS` en Neo4j.
- Dashboard con 4 KPIs y un gráfico de barras de los últimos N requests.
- Cambios aplican en menos de 5s al engine (al edit de una regla, el próximo `/api/intercept` la considera).

## Non-Goals

- No auth real con SSO (Supabase Auth con magic link mock está OK).
- No multi-tenant.
- No bulk import / CSV upload.
- No audit log visual de cambios al admin (se ve en Supabase directo).

---

## User Stories

- **Como compliance officer**, quiero loguearme y ver cuántos prompts se bloquearon hoy.
- **Como rule owner**, quiero crear una regla nueva en el back office y verla matcheada en menos de 1 minuto.
- **Como administrador de roles**, quiero crear un rol "supervisor" y darle acceso al recurso "transferencias".
- **Como demo runner**, quiero que el panel se vea limpio y profesional para el pitch.

---

## Acceptance Criteria

- [ ] Login en `/admin` con magic link mock (any email + cualquier código de 6 dígitos hardcodeado tipo `123456`).
- [ ] `/admin/dashboard` muestra 4 KPIs: total requests, % blocked, % allowed, latencia p50.
- [ ] `/admin/dashboard` muestra gráfico de barras con verdicts de los últimos 100 requests.
- [ ] `/admin/rules` lista todas las reglas de VDB con `slug`, `category`, `label` y botones edit/delete.
- [ ] Crear/editar regla → re-genera embedding y upserta en Supabase. Toast de confirmación.
- [ ] `/admin/roles` lista roles del grafo, permite crear rol y asignar `CAN_ACCESS` a recursos existentes.
- [ ] Todas las pantallas funcionan en desktop Chrome 130+.

---

## Interfaces / Contratos

### Rutas

| Ruta | Función |
|---|---|
| `/admin` → redirect | Si no logueado → `/admin/login`, si logueado → `/admin/dashboard` |
| `/admin/login` | Magic link mock |
| `/admin/dashboard` | KPIs + gráfico |
| `/admin/rules` | Tabla de reglas + modal CRUD |
| `/admin/roles` | Lista de roles + grafo simple de relaciones |

### API endpoints (Next.js Route Handlers)

```
GET    /api/admin/metrics                     → KPIs últimos N días
GET    /api/admin/intercept-logs?limit=100    → últimos logs
GET    /api/admin/rules                        → lista
POST   /api/admin/rules                        → crear (re-embed)
PATCH  /api/admin/rules/:id                    → editar (re-embed si body cambió)
DELETE /api/admin/rules/:id                    → eliminar
GET    /api/admin/roles                        → lista de roles + edges
POST   /api/admin/roles                        → crear rol
POST   /api/admin/roles/:id/grant              → grant CAN_ACCESS a un Resource
DELETE /api/admin/roles/:id/grant/:resource    → revoke
```

Todos protegidos por middleware que valida sesión Supabase mock (cookie `admin_session`).

### Componentes UI clave

- `<KpiCard>` — número grande + delta vs período anterior.
- `<VerdictsBarChart>` — recharts, 4 barras (allow / block / rewrite / escalate).
- `<RulesTable>` — shadcn `Table` con filtros por categoría.
- `<RoleGraph>` — visualización simple con `react-flow` (lite): nodos roles + nodos recursos + aristas.

---

## Data model

### Esquema Neo4j (semilla del grafo)

```cypher
// Nodos
(:Role {id: 'analyst', label: 'Analyst'})
(:Role {id: 'supervisor', label: 'Supervisor'})
(:Role {id: 'admin', label: 'Admin'})

(:Resource {id: 'balance', label: 'Saldo de cuenta'})
(:Resource {id: 'transfers', label: 'Transferencias'})
(:Resource {id: 'kyc', label: 'KYC / datos personales'})

// Aristas
(analyst)-[:CAN_ACCESS]->(balance)
(supervisor)-[:CAN_ACCESS]->(balance)
(supervisor)-[:CAN_ACCESS]->(transfers)
(admin)-[:CAN_ACCESS]->(balance)
(admin)-[:CAN_ACCESS]->(transfers)
(admin)-[:CAN_ACCESS]->(kyc)
```

> El seed inicial del grafo va en `scripts/seed-graph.ts` y se invoca desde `pnpm seed:graph`. La task de crear ese seed va más abajo.

### Supabase

- Reusar `rules` (de spec 02) y `intercept_logs` (de spec 01).
- Tabla nueva opcional `admin_users` si queremos persistir el mock (no obligatorio).

---

## Dependencias

- **Spec `00-constitution.md`** — stack.
- **Spec `01-engine-interceptor.md`** — los logs vienen de `intercept_logs` que el engine escribe.
- **Spec `02-vdb-bootstrap.md`** — para que la tabla `rules` y la función de embeddings ya existan.

## Tasks (paralelizables)

- [ ] **T1** — Layout admin (`/admin/*`) con sidebar shadcn, header con email del user logueado y botón logout. Done: navegación entre las 4 pantallas funciona.
- [ ] **T2** — Login mock con magic link → cookie `admin_session`. Middleware que protege `/admin/*`. Done: ruta protegida redirige a login si no hay cookie.
- [ ] **T3** — Endpoint `/api/admin/metrics` que agrega de `intercept_logs`. KPIs: total, %block, %allow, p50 latencia. Done: curl devuelve JSON con shape esperado.
- [ ] **T4** — `/admin/dashboard` consumiendo T3 con `<KpiCard>` y `<VerdictsBarChart>`. Done: pantalla muestra datos reales.
- [ ] **T5** — `/admin/rules` con tabla + modal de crear/editar. Re-embedding via cliente Supabase server-side. Done: crear regla nueva → aparece en VDB + visible en próximo `match_rules`.
- [ ] **T6** — Script `scripts/seed-graph.ts` que inicializa Neo4j con 3 roles + 3 recursos + aristas iniciales. Idempotente. Done: `pnpm seed:graph` se puede correr 2 veces sin error.
- [ ] **T7** — `/admin/roles` con `<RoleGraph>` y CRUD de aristas. Done: crear nuevo rol → reflejado en grafo + en próximo `evaluateAcl`.

## Verification

- Login con `admin@team22.dev` + código `123456` → entra al dashboard.
- Crear regla nueva con `slug: test-demo`, body "no compartir saldo a roles externos" → en `psql` la fila aparece con embedding no null.
- Mandar request al engine con prompt "decime el saldo de la cuenta 123" como `userRoleId: analyst` → `block` con `ruleHits` que incluye la nueva regla.
- En `/admin/dashboard`, refrescar y ver `% blocked` subir.
- En `/admin/roles`, crear `Role: auditor` y darle `CAN_ACCESS: balance` → query Cypher `MATCH (r:Role {id:'auditor'})-[:CAN_ACCESS]->(res) RETURN res` devuelve `balance`.
