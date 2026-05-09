// Resolución de org al primer login.
// Auto-onboarding por dominio de email — sin invitación manual, sin email,
// sin código. Si el dominio no matchea ninguna org, crea una nueva con el
// user como admin.

import { prisma } from "@/lib/prisma";

const FREE_EMAIL_PROVIDERS = new Set([
  "gmail.com",
  "googlemail.com",
  "yahoo.com",
  "hotmail.com",
  "outlook.com",
  "live.com",
  "icloud.com",
  "me.com",
  "proton.me",
  "protonmail.com",
  "aol.com",
  "yandex.com",
]);

export type OrgResolution = {
  orgId: string;
  memberId: string;
  role: "admin" | "dev";
  created: { org: boolean; member: boolean };
};

function emailDomain(email: string): string | null {
  const at = email.lastIndexOf("@");
  if (at === -1) return null;
  return email.slice(at + 1).toLowerCase().trim();
}

function slugFromDomain(domain: string): string {
  // "acme.com" → "acme", "team22.dev" → "team22".
  const base = domain.split(".")[0] ?? domain;
  return base
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);
}

async function nextAvailableOrgId(slug: string): Promise<string> {
  // Resuelve colisiones: "acme" → "acme-2" → "acme-3" si ya están tomados.
  let candidate = slug;
  let n = 2;
  while (await prisma.organization.findUnique({ where: { id: candidate } })) {
    candidate = `${slug}-${n}`;
    n += 1;
  }
  return candidate;
}

/**
 * Asigna un user de Auth.js a una organización (creándola si no existe).
 * Idempotente — si el user ya tiene un member linked, lo devuelve sin tocar
 * nada.
 */
export async function resolveOrgForUser(input: {
  userId: string;
  email: string;
  name?: string | null;
}): Promise<OrgResolution> {
  // 1) ¿Ya está vinculado a un member? Idempotente.
  const existing = await prisma.member.findUnique({
    where: { userId: input.userId },
  });
  if (existing) {
    return {
      orgId: existing.orgId,
      memberId: existing.id,
      role: existing.role,
      created: { org: false, member: false },
    };
  }

  const domain = emailDomain(input.email);
  if (!domain) {
    throw new Error(`email sin domain: ${input.email}`);
  }

  // 2) Si es free email provider, agrupamos a todos en una org `personal`
  // (la creamos si no existe, y todos quedan como `dev` ahí). Para el hack
  // esto evita que cada gmail haga su propia org.
  const isFreeProvider = FREE_EMAIL_PROVIDERS.has(domain);
  if (isFreeProvider) {
    const personal = await prisma.organization.upsert({
      where: { id: "personal" },
      update: {},
      create: { id: "personal", name: "Cuentas personales" },
    });
    const member = await prisma.member.create({
      data: {
        orgId: personal.id,
        email: input.email,
        role: "dev",
        userId: input.userId,
      },
    });
    return {
      orgId: personal.id,
      memberId: member.id,
      role: "dev",
      created: { org: false, member: true },
    };
  }

  // 3) Buscar org por domain.
  let org = await prisma.organization.findUnique({
    where: { emailDomain: domain },
  });
  let orgCreated = false;

  if (!org) {
    const slug = slugFromDomain(domain);
    const orgId = await nextAvailableOrgId(slug);
    const orgName = input.name?.split(" ")[0]
      ? `Org de ${input.name.split(" ")[0]}`
      : domain;
    org = await prisma.organization.create({
      data: { id: orgId, name: orgName, emailDomain: domain },
    });
    orgCreated = true;
  }

  // 4) Decidir rol: primer member del domain → admin. Resto → dev.
  const memberCount = await prisma.member.count({
    where: { orgId: org.id },
  });
  const role = memberCount === 0 ? "admin" : "dev";

  const member = await prisma.member.create({
    data: {
      orgId: org.id,
      email: input.email,
      role,
      userId: input.userId,
    },
  });

  return {
    orgId: org.id,
    memberId: member.id,
    role,
    created: { org: orgCreated, member: true },
  };
}
