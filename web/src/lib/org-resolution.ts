// Resolución de org al login.
//
// Modelo: cualquier login Google sin invitación previa = admin de una org
// nueva propia. Si el admin invitó al dev manualmente desde /admin/team,
// existe un member sin `userId` con ese email — al loguear, lo linkeamos.
//
// Cero invite codes, cero magic links: el dev solo escucha "te agregué" y
// abre Google.

import { prisma } from "@/lib/prisma";

// Free email providers — solo los usamos para *no* generar `gmail` /
// `yahoo` / etc. como id de org. La asignación es independiente del domain.
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
  const base = domain.split(".")[0] ?? domain;
  return base
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);
}

function randomShortId(len = 6): string {
  // 6 chars de [a-z0-9] = 36^6 ≈ 2B combinaciones. Suficiente para evitar
  // colisiones a la hora de auto-crear orgs.
  const alphabet = "abcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < len; i++) {
    out += alphabet[Math.floor(Math.random() * alphabet.length)];
  }
  return out;
}

async function nextAvailableOrgId(slug: string): Promise<string> {
  let candidate = slug;
  let n = 2;
  while (await prisma.organization.findUnique({ where: { id: candidate } })) {
    candidate = `${slug}-${n}`;
    n += 1;
  }
  return candidate;
}

function suggestOrgId(email: string): string {
  const domain = emailDomain(email);
  if (domain && !FREE_EMAIL_PROVIDERS.has(domain)) {
    const slug = slugFromDomain(domain);
    if (slug) return slug;
  }
  return `org-${randomShortId(6)}`;
}

function suggestOrgName(email: string, displayName?: string | null): string {
  const domain = emailDomain(email);
  if (domain && !FREE_EMAIL_PROVIDERS.has(domain)) {
    const base = domain.split(".")[0] ?? domain;
    return base.charAt(0).toUpperCase() + base.slice(1);
  }
  const first = displayName?.split(" ")[0];
  return first ? `${first}'s org` : "Mi organización";
}

/**
 * Resuelve la org de un user de Auth.js.
 *
 * 1) Si ya tiene `member.userId === user.id` → return idempotente.
 * 2) Si hay member con `email === user.email` y `userId === null` (invitado
 *    por un admin), lo linkeamos.
 * 3) Si no hay nada con ese email → creamos org nueva + member admin.
 */
export async function resolveOrgForUser(input: {
  userId: string;
  email: string;
  name?: string | null;
}): Promise<OrgResolution> {
  // 1) ¿Ya está linkeado?
  const linked = await prisma.member.findUnique({
    where: { userId: input.userId },
  });
  if (linked) {
    return {
      orgId: linked.orgId,
      memberId: linked.id,
      role: linked.role,
      created: { org: false, member: false },
    };
  }

  // 2) ¿Hay member sin linkear con este email? (admin que lo agregó a mano)
  const invited = await prisma.member.findFirst({
    where: { email: input.email, userId: null },
    orderBy: { createdAt: "asc" }, // el primero gana si hay duplicados raros
  });
  if (invited) {
    const updated = await prisma.member.update({
      where: { id: invited.id },
      data: { userId: input.userId },
    });
    return {
      orgId: updated.orgId,
      memberId: updated.id,
      role: updated.role,
      created: { org: false, member: false },
    };
  }

  // 3) No hay nada — el user nunca fue invitado, así que arma su propia org
  // y queda como admin.
  const orgId = await nextAvailableOrgId(suggestOrgId(input.email));
  const orgName = suggestOrgName(input.email, input.name);

  const org = await prisma.organization.create({
    data: { id: orgId, name: orgName },
  });
  const member = await prisma.member.create({
    data: {
      orgId: org.id,
      email: input.email,
      role: "admin",
      userId: input.userId,
    },
  });

  return {
    orgId: org.id,
    memberId: member.id,
    role: "admin",
    created: { org: true, member: true },
  };
}
