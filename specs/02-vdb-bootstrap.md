# 02 — VDB Bootstrap

> Genera la base de **reglas en lenguaje natural** y los **embeddings** que usan dos consumidores: el **Haiku judge (Layer 3)** del proxy y el **AI Suggestor (Layer 4)**.

---

## Contexto

La cascada del proxy tiene 3 capas. Las primeras dos (Regex y Pattern) son configuradas en el visual rule builder del admin como reglas declarativas — no necesitan VDB.

La **Layer 3 (Haiku judge)** sí: Haiku recibe el prompt + las top-K reglas en lenguaje natural más relevantes a ese prompt. Para que ese match sea bueno, las reglas NL viven en una VDB (`pgvector`). Local: Postgres en Docker; prod: Supabase Postgres.

Además, la **Layer 4 (AI Suggestor)** necesita embeddings de los prompts redactados de los logs para clusterizar patrones recurrentes y proponer reglas nuevas. Reusamos la misma extensión `pgvector` y el mismo provider de embeddings.

Hoy partimos de cero. Necesitamos:

1. La extensión `pgvector` habilitada y la tabla `policies` (con `embedding vector(1536)`) creada vía la migración Prisma `web/prisma/migrations/...init/migration.sql` (que ya existe e incluye `CREATE EXTENSION`, ivfflat parcial y la función `match_policies`).
2. Un script idempotente `pnpm seed:vdb` que lea un corpus seed desde `seeds/` y haga upsert por `(org_id, slug)`.
3. Que el corpus tenga reglas NL **y** reglas regex/pattern (las regex/pattern no necesitan embedding, pero igual viven en `policies` con `layer='regex'|'pattern'`).

---

## Goals

- Tabla `policies` + extensión `vector` instaladas vía la migración Prisma (ya escrita).
- Script `pnpm seed:vdb` que carga ≥ 20 reglas NL + ≥ 10 regex/pattern.
- Re-correr el script no duplica reglas (idempotente por `(org_id, slug)`).
- Función `match_policies(query_embedding, k, p_org_id)` en Postgres devuelve top-k filtradas por org con cosine distance — ya creada en la migración inicial.
- Corpus seed cubre ≥ 4 dominios: `credentials`, `pii`, `internal-paths`, `business-policy`.
- Provider de embeddings configurable vía env (`EMBEDDING_PROVIDER=openai|voyage`).

## Non-Goals

- No automatizamos el re-seed continuo desde el back-office (eso vive en spec `04-admin-web.md`).
- No multi-idioma — solo es-AR para el seed inicial.
- No fine-tuning del modelo de embeddings.
- La columna `embedding` de `interactions` la pueblan otros componentes (proxy + AI Suggestor), no este seed.

---

## User Stories

- **Como dev** corriendo el repo por primera vez, quiero `docker compose up && pnpm db:migrate && pnpm seed:vdb` y tener todo listo.
- **Como CI/CD** post-deploy a Vercel, quiero correr el seed sin duplicar datos.
- **Como demo runner**, quiero que el corpus tenga reglas reconocibles que pueda referenciar en el pitch ("acá ven que la regla `customer-name-mention` matcheó").

---

## Acceptance Criteria

- [ ] `seeds/policies-nl/` contiene ≥ 20 archivos `.md` con frontmatter `{slug, domain, severity, default_action}` y body en español.
- [ ] `seeds/policies-regex.json` y `seeds/policies-pattern.json` tienen entre los dos ≥ 10 reglas (`aws-access-key`, `gcp-service-account`, `pem-private-key`, `dotenv-paste`, `id_rsa-paste`, etc.).
- [ ] `pnpm seed:vdb` corre en < 60 s con red estable y termina con exit 0.
- [ ] Re-correr `pnpm seed:vdb` no genera filas duplicadas (verificable con `select layer, count(*) from policies group by layer`).
- [ ] La función `match_policies(query_embedding vector(1536), k int, p_org_id text)` existe (creada en migración init) y devuelve `{policy_id, slug, domain, rule, default_action, severity, score}`.
- [ ] La extensión `vector` está habilitada (en local automáticamente por la imagen `pgvector/pgvector:pg16`; en Supabase prod, habilitar una vez desde Database → Extensions).
- [ ] Provider de embeddings es configurable vía `EMBEDDING_PROVIDER=openai|voyage`.

---

## Interfaces / Contratos

### Estructura de un archivo seed NL

```markdown
---
slug: customer-name-mention
domain: business-policy
severity: medium
default_action: REDACT
---

Una regla aplica cuando el dev menciona el nombre de un cliente actual de la empresa
en el prompt — ej. "Acme Corp", "Banco Galicia", "Mercado Pago".

Ejemplos que deberían matchear:
- "Necesito refactorear el código que sirve al cliente Acme."
- "El bug que reportó Banco Galicia el viernes..."

Ejemplos que NO deberían matchear:
- "Acme Corp" usado como ejemplo genérico de placeholder en docs.
- Nombres de clientes ficticios o de test.

Cuando esto matchea con score > 0.78, el Haiku judge suele decidir REDACT.
```

### Formato de seeds regex/pattern

`seeds/policies-regex.json`:

```jsonc
[
  {
    "slug": "aws-access-key",
    "domain": "credentials",
    "severity": "high",
    "default_action": "BLOCK",
    "pattern": "AKIA[0-9A-Z]{16}",
    "rule": "Detecta AWS Access Key ID expuesta en un prompt"
  },
  {
    "slug": "pem-private-key",
    "domain": "credentials",
    "severity": "high",
    "default_action": "BLOCK",
    "pattern": "-----BEGIN (RSA|OPENSSH|EC|PRIVATE) KEY-----",
    "rule": "Detecta una private key PEM en clear-text"
  }
]
```

`seeds/policies-pattern.json`:

```jsonc
[
  {
    "slug": "dotenv-paste",
    "domain": "credentials",
    "severity": "high",
    "default_action": "BLOCK",
    "match_config": { "extensions": [".env"], "filename_globs": [".env", ".env.*"] },
    "rule": "Detecta paste de archivos .env con variables de entorno productivas"
  },
  {
    "slug": "id-rsa-paste",
    "domain": "credentials",
    "severity": "high",
    "default_action": "BLOCK",
    "match_config": { "filename_globs": ["id_rsa", "id_ed25519"] },
    "rule": "Detecta paste de archivos de SSH private keys"
  }
]
```

### CLI

```bash
pnpm seed:vdb                       # corre seed completo para org 'demo'
pnpm seed:vdb --org=acme            # seed para una org específica
pnpm seed:vdb --only=credentials    # solo dominio
pnpm seed:vdb --dry-run             # imprime acciones sin escribir
```

### Schema canónico

Vive en `web/prisma/schema.prisma` (modelo `Policy` → tabla `policies`). La migración SQL `web/prisma/migrations/20260509000000_init/migration.sql` ya incluye:

- `CREATE EXTENSION IF NOT EXISTS vector;`
- Tabla `policies` con todos los campos.
- Índice `policies_embedding_idx` ivfflat parcial sobre `embedding` para `layer='nl' AND is_active=true`.
- Función `match_policies(query_embedding, k, p_org_id)`.
- Seed de `organizations` con `('demo', 'Org Demo')`.

> Si en algún momento se modifica `schema.prisma`, regenerar la próxima migración con `pnpm prisma migrate dev --create-only --name <nombre>` y **volver a sumar** el bloque manual (ivfflat + función) al final del SQL generado. Prisma no expresa esos pedazos declarativamente.

### Cómo el proxy consume las policies

```ts
// Layer 1+2 (Regex + Pattern): cargado en memoria al boot.
const fastRules = await prisma.policy.findMany({
  where: { orgId, isActive: true, layer: { in: ['regex', 'pattern'] } },
});

// Layer 3 (Haiku judge): top-K via match_policies — raw porque Prisma no maneja vector.
const nlMatches = await prisma.$queryRaw<Array<{
  policy_id: string;
  slug: string;
  domain: string;
  rule: string;
  default_action: 'BLOCK' | 'REDACT' | 'WARN' | 'LOG';
  severity: 'low' | 'medium' | 'high';
  score: number;
}>>`SELECT * FROM match_policies(${queryEmbedding}::vector, ${k}, ${orgId})`;
```

---

## Dependencias

- **Spec `00-constitution.md`** — provider de embeddings, env vars.
- Postgres local (Docker `pgvector/pgvector:pg16`) o Supabase prod con extensión `vector` habilitada.
- API key del provider (`OPENAI_API_KEY` o `VOYAGE_API_KEY`).

## Tasks (paralelizables)

- [ ] **T1** — Verificar que la migración `web/prisma/migrations/20260509000000_init/migration.sql` aplica limpio en Docker local. Done: `pnpm prisma migrate dev` termina sin error y `\dx` en psql muestra `vector`.
- [ ] **T2** — Corpus seed NL: 20+ archivos `.md` en `seeds/policies-nl/` cubriendo `credentials`, `pii`, `internal-paths`, `business-policy`. Done: `ls seeds/policies-nl/*.md | wc -l` ≥ 20.
- [ ] **T3** — Corpus seed regex/pattern: archivos `seeds/policies-regex.json` y `seeds/policies-pattern.json` con ≥ 10 reglas combinadas. Done: archivos versionados, JSON válido.
- [ ] **T4** — Script `web/scripts/seed-vdb.ts` que lee los 3 corpus, llama al provider de embeddings (solo NL) y hace `prisma.policy.upsert` por `(org_id, slug)`. Done: corre localmente y popla la tabla.
- [ ] **T5** — Wrapper `--dry-run`, `--only=<domain>` y `--org=<org_id>`. Done: `pnpm seed:vdb --dry-run` imprime acciones sin escribir.
- [ ] **T6** — GitHub Action `.github/workflows/seed-on-deploy.yml` que corre el seed después del deploy a Vercel preview/prod. Done: el workflow corre verde en un PR de prueba.
- [ ] **T7** — Documentar en `07-requirements-docs.md` qué env vars hacen falta para correr el seed.

## Verification

- **Local**: `docker compose up -d && pnpm prisma migrate dev && pnpm seed:vdb` → `psql ... -c "select layer, count(*) from policies group by layer"` muestra ≥ 10 regex/pattern + ≥ 20 NL.
- **Idempotencia**: correr seed dos veces seguidas → counts no cambian.
- **Match funciona**: en psql, `select * from match_policies((select embedding from policies where slug='customer-name-mention'), 5, 'demo')` devuelve 5 filas con score descendente y la primera es score ≈ 1.0.
- **Engine integration**: el spec `01` puede llamar `embedAndMatchPolicies("decime el cliente Acme", 5)` y recibe `customer-name-mention` en el top-3.
