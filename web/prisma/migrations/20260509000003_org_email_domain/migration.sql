-- Auto-onboarding: matcheamos email del user con el `email_domain` de una
-- organización para asignarlo sin invitación manual.

ALTER TABLE "organizations" ADD COLUMN "email_domain" TEXT;
CREATE UNIQUE INDEX "organizations_email_domain_key"
    ON "organizations"("email_domain");
