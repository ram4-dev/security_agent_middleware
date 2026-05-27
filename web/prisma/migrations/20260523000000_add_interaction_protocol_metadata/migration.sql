-- Add protocol/provider metadata for multi-provider interaction audit rows.
-- Defaults preserve existing Claude Code / Anthropic rows.

ALTER TABLE "interactions"
    ADD COLUMN "protocol" TEXT NOT NULL DEFAULT 'anthropic_messages',
    ADD COLUMN "integration" TEXT NOT NULL DEFAULT 'claude-code',
    ADD COLUMN "upstream_provider" TEXT,
    ADD COLUMN "upstream_model" TEXT;
