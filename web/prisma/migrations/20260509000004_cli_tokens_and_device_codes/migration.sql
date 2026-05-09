-- CLI tokens persistentes + device flow para que el CLI delegue auth al
-- browser sin pegar API keys a mano.

CREATE TABLE "cli_tokens" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "member_id" UUID NOT NULL,
    "token_hash" TEXT NOT NULL,
    "label" TEXT,
    "last_used_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "revoked_at" TIMESTAMP(3),
    CONSTRAINT "cli_tokens_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "cli_tokens_token_hash_key" ON "cli_tokens"("token_hash");
CREATE INDEX "cli_tokens_member_id_idx" ON "cli_tokens"("member_id");
ALTER TABLE "cli_tokens"
    ADD CONSTRAINT "cli_tokens_member_id_fkey"
    FOREIGN KEY ("member_id") REFERENCES "members"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "cli_device_codes" (
    "device_code" TEXT NOT NULL,
    "user_code" TEXT NOT NULL,
    "member_id" UUID,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires_at" TIMESTAMP(3) NOT NULL,
    "approved_at" TIMESTAMP(3),
    "issued_token_id" UUID,
    CONSTRAINT "cli_device_codes_pkey" PRIMARY KEY ("device_code")
);
CREATE UNIQUE INDEX "cli_device_codes_user_code_key" ON "cli_device_codes"("user_code");
CREATE INDEX "cli_device_codes_status_idx" ON "cli_device_codes"("status");
ALTER TABLE "cli_device_codes"
    ADD CONSTRAINT "cli_device_codes_member_id_fkey"
    FOREIGN KEY ("member_id") REFERENCES "members"("id")
    ON DELETE SET NULL ON UPDATE CASCADE;
