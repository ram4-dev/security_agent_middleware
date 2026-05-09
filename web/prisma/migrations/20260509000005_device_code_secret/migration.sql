-- Token plaintext que entrega el approver y el CLI recoge en el poll.
-- Una vez recogido, el handler lo nulea — solo el hash queda en cli_tokens.

ALTER TABLE "cli_device_codes" ADD COLUMN "secret_token" TEXT;
