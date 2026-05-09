# 04 — Admin Web

> Layer 3. Back-office para admins **no técnicos**. Visual rule builder no-code + dashboards + approval queue de reglas auto-sugeridas.

---

## Contexto

El producto se vende a empresas que dan Claude Code a sus devs. La persona que **configura las reglas** es típicamente un compliance officer / security lead — no un dev. Por lo tanto el admin debe:

1. Permitir crear reglas con un **rule builder visual** (no escribir regex a mano, no tocar SQL).
2. Mostrar **eventos en tiempo real** del proxy (qué bloqueó, qué redactó, cuál fue el motivo).
3. Mostrar **what-if reports** ("si activabas esta regla la semana pasada, hubieras bloqueado X requests con riesgo Y").
4. Tener una **approval queue** para reglas que el AI Suggestor (spec 08) propone después de N días.
5. Multi-tenant by design: una org, su set de reglas, sus admins, sus eventos. Para el hack se permite single-tenant hardcoded (`org_id = 'demo'`) pero el schema y los queries deben estar listos para la migración.

Sin admin web, no se pueden modificar reglas sin meterse a SQL. Para la demo es **clave** mostrar: "miren, agrego una regla acá y al toque el interceptor la usa".

---

## Goals

- 4 secciones: **Dashboard**, **Rules** (visual builder + lista), **Events** (live feed), **Suggestions** (approval queue del AI Suggestor).
- Visual rule builder con 3 tipos de regla:
  - **Match exacto / regex preset**: el admin elige de una galería (`AWS Access Key`, `Email`, `Tarjeta de crédito`, ...) — la regex vive escondida.
  - **Filename / path** (Layer 2): admin elige "archivos terminados en .env / id_rsa / *.pem".
  - **En lenguaje natural** (Layer 3): admin escribe "no menciones nombres de clientes" — se embebe y va a `policies.layer='nl'`.
- CRUD completo: crear / listar / editar / habilitar-deshabilitar / eliminar.
- Cambios de reglas se reflejan en el proxy en menos de 5 s (en prod: Supabase Realtime sobre `policies`; en local: polling 5 s).
- Dashboard con 4 KPIs y gráfico de la última hora.
- Approval queue muestra reglas sugeridas por el Layer 4 con preview ("hubiera matcheado N requests, ejemplos: ...") y permite Aceptar / Rechazar / Editar antes de aceptar.

## Non-Goals

- No SSO empresarial (SAML/OIDC enterprise) — Auth.js v5 con Google OAuth está OK.
- No bulk import / CSV upload de reglas.
- No audit log visual de cambios al admin (se ve en Supabase directo).
- No edición técnica de regex crudas (escondidas detrás de presets); si un admin quiere regex custom abrimos issue post-hack.

---

## User Stories

- **Como compliance officer**, quiero loguearme y ver cuántos prompts se bloquearon hoy, sin saber programar.
- **Como rule owner**, quiero crear una regla "redactar nombres de clientes" en 30 s desde una UI visual.
- **Como compliance officer**, quiero revisar la cola de reglas sugeridas y aceptar la que tiene más sentido con un click.
- **Como demo runner**, quiero que el panel se vea limpio y profesional para el pitch.

---

## Acceptance Criteria

- [x] Login en `/admin` con Google OAuth (Auth.js v5). Modo demo bypass con `?demo=1` mientras `GOOGLE_CLIENT_ID` esté vacío.
- [x] Primer login Google sin invitación previa → crea org nueva con el user como admin owner (`src/lib/org-resolution.ts`).
- [x] Admin invita devs por email desde `/admin/team` → quedan en estado pendiente hasta su primer login.
- [ ] `/admin/dashboard` muestra 4 KPIs: total events 24h, % BLOCK, % REDACT, latencia p50 del proxy.
- [ ] `/admin/dashboard` muestra gráfico de barras con acciones de los últimos 100 events.
- [x] `/admin/rules` lista todas las reglas con `slug`, `layer`, `domain`, `default_action`, toggle on/off.
- [x] Crear regla NL desde el form → upsert en `policies` vía Prisma. Cambios reflejados en el próximo prompt del proxy (sin caché).
- [x] `/admin/events` muestra feed con polling 3s. `created_at`, `action` (badge color), `policy_hits[]`, `prompt_redacted` (truncado).
- [ ] `/admin/suggestions` lista propuestas del Layer 4 con preview de matches retroactivos y CTAs Aceptar / Rechazar / Editar.
- [x] Todas las pantallas funcionan en desktop Chrome 130+.

---

## Interfaces / Contratos

### Rutas

| Ruta | Función |
|---|---|
| `/admin` → redirect | Si no logueado → `/admin/login` (modo Google) o landing (modo demo); si logueado → `/admin/events` |
| `/admin/login` | Button "Continuar con Google" (Auth.js v5). En modo demo no se sirve. |
| `/admin/events` | Feed con polling 3s, filtros por acción. |
| `/admin/rules` | Tabla de reglas + form NL para crear/editar. |
| `/admin/team` | Lista de admins/devs + form para invitar dev por email. |
| `/admin/suggestions` | Approval queue del AI Suggestor (gdoc import por ahora). |
| `/admin/dashboard` | KPIs + gráfico. **Pendiente**. |
| `/cli/connect?code=XXXX` | Browser-side del device flow del CLI. Requiere Google login. |

### API endpoints (Next.js Route Handlers)

```
GET    /api/admin/metrics                       → KPIs últimas 24h (pendiente)
GET    /api/admin/events?since=&action=&limit=  → events para el feed (polling)
GET    /api/admin/rules                          → lista
POST   /api/admin/rules                          → crear regla NL
PATCH  /api/admin/rules/:id                      → editar / toggle isActive
DELETE /api/admin/rules/:id                      → eliminar
GET    /api/admin/team                            → lista de members
POST   /api/admin/team                            → invitar dev por email
DELETE /api/admin/team/:id                        → remover member (no se puede el último admin)
GET    /api/admin/suggestions                    → cola del Suggestor / gdoc import
POST   /api/admin/suggestions/:id/accept         → promover a regla activa
POST   /api/admin/suggestions/:id/reject         → descartar (con motivo)
POST   /api/cli/device/start                     → device flow del CLI: nuevo user_code/device_code
GET    /api/cli/device/poll?device_code=…        → polling del CLI hasta approved
GET    /api/cli/me                               → bearer-auth, devuelve member
POST   /api/cli/logout                           → bearer-auth, revoca cli_token
GET    /api/auth/[...nextauth]                   → Auth.js handlers (Google OAuth)
```

Todos los `/api/admin/*` protegidos por `proxy.ts` (Next 16 middleware renombrado): si `GOOGLE_CLIENT_ID` está seteado, valida JWT de Auth.js; si no, valida cookie `admin_session=demo`. En cualquier caso, el handler filtra por `org_id` del session resuelto.

### Componentes UI clave

> **Identidad**: tipografía (IBM Plex Sans + Mono), paleta base (paper / ink / graphite) y wordmark vienen de [`../identidad/design.md`](../identidad/design.md). Los **acentos de color por acción** (sección "Action colors" abajo) son **funcionales** — el design system los autoriza explícitamente para superficies de monitoreo en vivo (ver `identidad/design.md` § 6, nota de tensión funcional).

- `<KpiCard>` — número grande IBM Plex Sans 600 + delta como caption mono graphite (ver `identidad/design.md` § 6).
- `<ActionsBarChart>` — recharts, 4 barras (BLOCK / REDACT / WARN / LOG) con colores convencionales (rojo / amarillo / naranja / gris).
- `<RuleWizard>` — stepper shadcn con 3 caminos: Preset / Filename / NL.
  - Preset: galería de cards (`AWS Access Key`, `Email`, `JWT`, `Credit Card`, `IBAN`, `CUIT/CUIL`, ...).
  - Filename: input + chips de presets (`.env`, `id_rsa`, `*.pem`).
  - NL: textarea con ejemplos placeholder + botón "Probar contra los últimos 100 events" antes de guardar.
- `<EventsFeed>` — client component con polling cada 3s a `/api/admin/events?since=…`. Anexa filas nuevas al top.
- `<TeamPanel>` — lista de admins/devs separados, dot verde si el dev ya logueó por primera vez.
- `<SuggestionCard>` — preview con count de matches retroactivos + 3 ejemplos redactados.

### Action colors (consistencia con landing y eventos)

- `BLOCK` → rojo `bg-red-500/10 text-red-600`
- `REDACT` → amarillo `bg-amber-500/10 text-amber-600`
- `WARN` → naranja `bg-orange-500/10 text-orange-600`
- `LOG` → gris `bg-zinc-500/10 text-zinc-600`

---

## Data model

### Supabase

Reusa `policies` (de spec 02), `interactions` (de spec 01) y `rule_suggestions` (de spec 08).

Tablas que vive en este spec — `members` (humanos / entidades por org) + `organizations` (tenant). Ambas se crean en `web/prisma/migrations/`:

```sql
create table organizations (
  id text primary key,                  -- ej. 'demo', 'acme'
  name text not null,
  upstream_api_key_ref text,            -- referencia a Vault / env, no la key cruda
  created_at timestamptz default now()
);

-- Roles:
--   admin → humano que se loguea al back-office. UI completa.
--   dev   → entidad sin UI por ahora. Existe para atribuir interactions
--           del proxy a un dev concreto cuando emitamos API keys del
--           proxy (post-hack). Sus "permisos" se materializan en el
--           comportamiento del proxy, no en una pantalla.
create type member_role as enum ('admin', 'dev');

create table members (
  id         uuid primary key default gen_random_uuid(),
  org_id     text not null default 'demo' references organizations(id),
  email      text not null,
  role       member_role not null default 'admin',
  created_at timestamptz default now(),
  unique (org_id, email)
);

insert into organizations (id, name) values ('demo', 'Org Demo') on conflict do nothing;
insert into members (org_id, email, role)
  values ('demo', 'admin@team22.dev', 'admin')
  on conflict do nothing;
```

> El SQL canónico vive en `web/prisma/migrations/20260509000001_members_and_suggestions/migration.sql`. Acá lo replicamos resumido como referencia.

> **Auth real**: implementado con **Auth.js v5 + Google OAuth** (migración `20260509000002_auth_js_tables`). `members.user_id` (FK opcional → `auth_users.id`) se vincula automáticamente al primer login. Mientras `GOOGLE_CLIENT_ID` esté vacío, el modo demo (cookie `admin_session=demo` activada por `?demo=1`) sigue funcionando para el pitch sin requerir setup de OAuth.

> **CLI device flow**: tablas `cli_tokens` + `cli_device_codes` (migración `20260509000004_cli_tokens_and_device_codes`) implementan el OAuth-style device flow para que `npx tranquera setup` pueda autenticar al dev sin tener que pegar API keys a mano.

---

## Dependencias

- **Spec `00-constitution.md`** — stack.
- **Spec `01-engine-interceptor.md`** — los events vienen de `interactions` que el proxy escribe.
- **Spec `02-vdb-bootstrap.md`** — para que la tabla `policies` y la función `match_policies` ya existan.
- **Spec `08-ai-suggestor.md`** — alimenta la approval queue.

## Tasks

- [x] **T1** — Layout admin (`/admin/*`) con sidebar (Eventos / Reglas / Equipo / Sugerencias), header con org + email + signout.
- [x] **T2** — Auth.js v5 + Google OAuth con Prisma adapter. `proxy.ts` (Next 16 middleware) protege `/admin/*` con session JWT. Modo demo (cookie mock) como fallback cuando `GOOGLE_CLIENT_ID` está vacío.
- [ ] **T3** — `/api/admin/metrics` que agrega de `interactions` filtrado por `org_id`. KPIs: total 24h, %BLOCK, %REDACT, p50 latencia total.
- [ ] **T4** — `/admin/dashboard` consumiendo T3 con `<KpiCard>` y `<ActionsBarChart>`. Pendiente.
- [x] **T5** — `/admin/rules` con form + tabla. Crear regla NL → upsert en `policies`, próximo prompt del proxy ya la usa (sin caché).
- [x] **T6** — `/admin/events` con `<EventsFeed>` y polling cada 3s. Filtros por action.
- [ ] **T7** — `/admin/suggestions` consumiendo `/api/admin/suggestions` + acciones accept/reject/edit. Versión gdoc-import landed; AI Suggestor (spec 08) pendiente.
- [ ] **T8** — Notificación visual cuando hay un `WARN` event. Pendiente.
- [x] **T9** — `/admin/team` para invitar devs por email (status pendiente hasta primer login con Google).
- [x] **T10** — `/cli/connect?code=…` page con server action `approveDeviceCode` para el browser-side del device flow del CLI.

## Verification

- Loguear con Google en `/admin/login` (modo Google) o entrar a `/admin?demo=1` (modo demo). Llegás a `/admin/events`.
- En `/admin/team` invitar `dev@tu-empresa.com` → aparece como `pendiente` en la lista.
- Crear regla NL `customer-name-mention` con body "no menciones nombres de clientes" → fila aparece en `policies`.
- Mandar request al proxy con `ANTHROPIC_BASE_URL=$URL` y prompt "el cliente Acme me pidió X" → `BLOCK` por la regla NL (vía Haiku judge).
- En `/admin/events` ver la fila aparecer al refrescar (o esperar 3s del polling) con `policyHits` apuntando a `nl/customer-name-mention`.
- Desde el CLI: `npx tranquera setup` abre browser → loguear/aprobar → `~/.tranquera/config.json` queda con `token` y `member`.
