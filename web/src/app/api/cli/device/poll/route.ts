// GET /api/cli/device/poll?device_code=...
// El CLI hace polling acá. Cuando el user aprueba en el browser, devolvemos
// el token plaintext UNA sola vez y limpiamos secretToken.

import type { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const deviceCode = url.searchParams.get("device_code");
  if (!deviceCode) {
    return Response.json({ error: "missing device_code" }, { status: 400 });
  }

  const code = await prisma.cliDeviceCode.findUnique({
    where: { deviceCode },
    include: {
      member: {
        select: {
          email: true,
          role: true,
          orgId: true,
          organization: { select: { id: true, name: true } },
        },
      },
    },
  });

  if (!code) {
    return Response.json({ error: "unknown device code" }, { status: 404 });
  }

  // Expirado por TTL. Marcamos para que el siguiente poll vea el estado real.
  if (code.status === "pending" && code.expiresAt.getTime() < Date.now()) {
    await prisma.cliDeviceCode.update({
      where: { deviceCode },
      data: { status: "expired" },
    });
    return Response.json({ status: "expired" });
  }

  if (code.status === "pending") {
    return Response.json({ status: "pending" });
  }

  if (code.status === "approved") {
    if (!code.secretToken || !code.member) {
      // Approved pero ya recogido — el cliente esperó demasiado entre polls.
      return Response.json({ status: "consumed" }, { status: 410 });
    }
    const token = code.secretToken;
    // Borramos el plaintext para que solo se entregue una vez.
    await prisma.cliDeviceCode.update({
      where: { deviceCode },
      data: { secretToken: null },
    });
    return Response.json({
      status: "approved",
      token,
      member: {
        email: code.member.email,
        role: code.member.role,
        org: {
          id: code.member.organization.id,
          name: code.member.organization.name,
        },
      },
    });
  }

  return Response.json({ status: code.status });
}
