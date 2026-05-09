-- =============================================================
-- 0001 — init
-- Aplica el schema inicial. Incluye los pedazos que Prisma no
-- expresa de forma declarativa (extensión, función match_policies,
-- enum domain, CHECK constraints). Si modificás `schema.prisma`
-- después, regenerá la próxima migración con
-- `pnpm prisma migrate dev --create-only` y volvé a sumar los
-- bloques manuales si tocan tablas con `embedding` o constraints.
-- Diseñado para ser idempotente: re-aplicarlo no debe romper.
-- =============================================================

-- 1. Extensión pgvector (necesaria antes de crear columnas vector(N)).
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Enums. Idempotente vía bloque DO (PG no soporta CREATE TYPE IF NOT EXISTS).
DO $$ BEGIN
    CREATE TYPE "Action" AS ENUM ('BLOCK', 'REDACT', 'WARN', 'LOG');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE "PolicyLayer" AS ENUM ('regex', 'pattern', 'nl');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE "PolicySource" AS ENUM ('seed', 'admin', 'ai-suggestor');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE "Severity" AS ENUM ('low', 'medium', 'high');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE "PolicyDomain" AS ENUM ('credentials', 'pii', 'internal_paths', 'business_policy', 'code');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 3. Tablas.

CREATE TABLE IF NOT EXISTS "organizations" (
    "id"                     TEXT        NOT NULL,
    "name"                   TEXT        NOT NULL,
    "upstream_api_key_ref"   TEXT,                                -- formato: "env:VAR_NAME" | "vault:<uuid>"
    "created_at"             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT "organizations_pkey" PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "policies" (
    "id"             UUID            NOT NULL DEFAULT gen_random_uuid(),
    "org_id"         TEXT            NOT NULL DEFAULT 'demo',
    "slug"           TEXT            NOT NULL,
    "domain"         "PolicyDomain"  NOT NULL,
    "layer"          "PolicyLayer"   NOT NULL,
    "rule"           TEXT            NOT NULL,
    "pattern"        TEXT,
    "match_config"   JSONB,
    "default_action" "Action"        NOT NULL,
    "severity"       "Severity"      NOT NULL DEFAULT 'medium',
    "embedding"      vector(1536),
    "source"         "PolicySource"  NOT NULL DEFAULT 'seed',
    "is_active"      BOOLEAN         NOT NULL DEFAULT true,
    "created_at"     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    "updated_at"     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT "policies_pkey"            PRIMARY KEY ("id"),
    CONSTRAINT "policies_match_config_obj"
        CHECK (match_config IS NULL OR jsonb_typeof(match_config) = 'object')
);

CREATE TABLE IF NOT EXISTS "interactions" (
    "id"                UUID         NOT NULL DEFAULT gen_random_uuid(),
    "trace_id"          TEXT         NOT NULL,
    "org_id"            TEXT         NOT NULL DEFAULT 'demo',
    "user_id"           UUID,                                          -- TODO: FK a auth.users(id) cuando activemos Supabase Auth real
    "request_model"     TEXT         NOT NULL,
    "prompt"            TEXT         NOT NULL,
    "action"            "Action"     NOT NULL,
    "reason"            TEXT         NOT NULL,
    "policy_hits"       JSONB        NOT NULL DEFAULT '[]'::jsonb,
    "latency_total_ms"  INTEGER      NOT NULL,
    "latency_by_layer"  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    "upstream_status"   INTEGER,
    "embedding"         vector(1536),
    "created_at"        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT "interactions_pkey"           PRIMARY KEY ("id"),
    CONSTRAINT "interactions_prompt_size"    CHECK (length(prompt) < 50000),
    CONSTRAINT "interactions_hits_array"     CHECK (jsonb_typeof(policy_hits) = 'array'),
    CONSTRAINT "interactions_latency_object" CHECK (jsonb_typeof(latency_by_layer) = 'object')
);

-- 4. Foreign keys.

ALTER TABLE "policies"
    DROP CONSTRAINT IF EXISTS "policies_org_id_fkey";
ALTER TABLE "policies"
    ADD  CONSTRAINT "policies_org_id_fkey"
    FOREIGN KEY ("org_id") REFERENCES "organizations"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "interactions"
    DROP CONSTRAINT IF EXISTS "interactions_org_id_fkey";
ALTER TABLE "interactions"
    ADD  CONSTRAINT "interactions_org_id_fkey"
    FOREIGN KEY ("org_id") REFERENCES "organizations"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;

-- 5. Unique constraints + índices "regulares".

CREATE UNIQUE INDEX IF NOT EXISTS "policies_org_id_slug_key"
    ON "policies" ("org_id", "slug");

CREATE INDEX IF NOT EXISTS "policies_org_id_layer_idx"
    ON "policies" ("org_id", "layer");

CREATE UNIQUE INDEX IF NOT EXISTS "interactions_trace_id_key"
    ON "interactions" ("trace_id");

-- Composite que cubre el dashboard (`/api/admin/metrics` y `/admin/events?action=...`).
CREATE INDEX IF NOT EXISTS "interactions_org_action_created_at_idx"
    ON "interactions" ("org_id", "action", "created_at" DESC);

-- =============================================================
-- BLOQUE MANUAL — Prisma no genera nada de esto.
-- Mantener al final del archivo, así si re-generás la migración
-- el bloque queda separado y se puede portar fácil.
-- =============================================================

-- 6. (intencionalmente sin índice ANN sobre policies.embedding)
--
-- Con <500 policies NL por org, el seq scan dentro del filtro
-- parcial (`WHERE layer='nl' AND is_active AND org_id=$1`)
-- es más rápido y predecible que un ivfflat mal-sized o un
-- HNSW que en N pequeño sufre overhead.
-- Cuando una org supere ~5k policies NL, agregar:
--   CREATE INDEX policies_embedding_hnsw_idx
--     ON policies USING hnsw (embedding vector_cosine_ops)
--     WHERE layer = 'nl' AND is_active = true;

-- 7. Función match_policies — usada por el Haiku judge (Layer 3 del proxy).
--    Devuelve los enums tipados (no `text`) para que Prisma $queryRaw
--    los reciba con el tipo correcto.
CREATE OR REPLACE FUNCTION match_policies(
    query_embedding vector(1536),
    k               int,
    p_org_id        text
)
RETURNS TABLE (
    policy_id      uuid,
    slug           text,
    domain         "PolicyDomain",
    rule           text,
    default_action "Action",
    severity       "Severity",
    score          float
)
LANGUAGE sql STABLE AS $$
    SELECT id,
           slug,
           domain,
           rule,
           default_action,
           severity,
           1 - (embedding <=> query_embedding) AS score
    FROM   policies
    WHERE  layer      = 'nl'
      AND  is_active  = true
      AND  org_id     = p_org_id
      AND  embedding IS NOT NULL
    ORDER  BY embedding <=> query_embedding
    LIMIT  k;
$$;

-- 8. Seed de la org demo (idempotente).
INSERT INTO "organizations" ("id", "name")
VALUES ('demo', 'Org Demo')
ON CONFLICT ("id") DO NOTHING;
