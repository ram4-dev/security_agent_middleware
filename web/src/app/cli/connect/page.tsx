// /cli/connect?code=XXXX-XXXX — el dev abre esta página desde el browser
// (lo manda el CLI). Después de loguear con Google, ve quién va a quedar
// vinculado al CLI y puede aprobar.
/* eslint-disable react/jsx-no-comment-textnodes */

import { redirect } from "next/navigation";
import { auth, isAuthConfigured } from "@/auth";
import { getAdminSession } from "@/lib/admin-session";
import { prisma } from "@/lib/prisma";
import { approveDeviceCode } from "./_actions";

export const dynamic = "force-dynamic";

export default async function CliConnectPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const { code: userCode } = await searchParams;

  if (!isAuthConfigured()) {
    return (
      <ErrorScreen
        title="Auth no configurado"
        body="El servidor está corriendo en modo demo, sin Google OAuth. Pedile al admin que active GOOGLE_CLIENT_ID."
      />
    );
  }
  if (!userCode) {
    return (
      <ErrorScreen
        title="Falta el código"
        body="Volvé al CLI y corré `npx tranquera setup` para que abra esta página con el código correcto."
      />
    );
  }

  const session = await auth();
  if (!session?.user) {
    redirect(`/admin/login?callbackUrl=${encodeURIComponent(`/cli/connect?code=${userCode}`)}`);
  }

  const adminSession = await getAdminSession();
  if (!adminSession) {
    return (
      <ErrorScreen
        title="Sesión incompleta"
        body="Tu Google login no terminó de resolver tu org. Refrescá la página."
      />
    );
  }

  const code = await prisma.cliDeviceCode.findUnique({
    where: { userCode: userCode.toUpperCase() },
  });

  if (!code) {
    return (
      <ErrorScreen
        title="Código inválido"
        body={`No encontré el código ${userCode}. Pediste un nuevo \`npx tranquera setup\`?`}
      />
    );
  }
  if (code.status === "approved") {
    return (
      <ErrorScreen
        title="Ya estaba aprobado"
        body="Este código ya fue usado. Si necesitás vincular otra terminal, corré `npx tranquera setup` de nuevo."
      />
    );
  }
  // Nota: el chequeo de TTL contra el reloj actual lo hace el server action
  // y el endpoint /poll. Acá solo confiamos en `status` para no llamar APIs
  // impuras desde un Server Component (regla del React Compiler).
  if (code.status === "expired") {
    return (
      <ErrorScreen
        title="Código vencido"
        body="Pasaron más de 10 minutos desde que arrancaste el CLI. Corré `npx tranquera setup` de nuevo."
      />
    );
  }

  return (
    <Shell>
      <span className="font-mono text-xs uppercase tracking-wider text-graphite">
        // autorizar cli
      </span>
      <h1 className="text-2xl font-semibold tracking-tight">
        ¿Vinculás esta terminal a tu cuenta?
      </h1>
      <p className="text-sm leading-relaxed text-graphite-dark">
        Vas a quedar identificado como <strong>{adminSession.email}</strong> en
        la org <strong>{adminSession.orgId}</strong>. Cada prompt de Claude Code
        que pase por la tranquera va a quedar atribuido a vos.
      </p>

      <div
        className="border border-graphite-dark/20 bg-paper-soft/40 px-4 py-3"
        style={{ borderRadius: "var(--radius)" }}
      >
        <p className="font-mono text-[11px] uppercase tracking-wider text-graphite">
          // user code
        </p>
        <p className="mt-1 font-mono text-2xl tracking-widest text-ink">
          {code.userCode}
        </p>
        <p className="mt-2 font-mono text-[11px] text-graphite">
          // confirmá que coincide con el que muestra tu CLI
        </p>
      </div>

      <form action={approveDeviceCode} className="flex flex-col gap-3">
        <input type="hidden" name="userCode" value={code.userCode} />
        <button
          type="submit"
          className="bg-ink px-6 py-3 font-medium text-paper transition-colors hover:bg-graphite-dark"
          style={{ borderRadius: "var(--radius)" }}
        >
          Autorizar CLI
        </button>
        <p className="font-mono text-[11px] leading-relaxed text-graphite">
          // si no fuiste vos quien pidió esto, simplemente cerrá la pestaña.
          el código vence en 10 min.
        </p>
      </form>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 py-16">
        <div
          className="flex w-full flex-col gap-6 border border-graphite-dark/20 bg-paper p-8 md:p-10"
          style={{ borderRadius: "var(--radius)" }}
        >
          {children}
        </div>
      </main>
    </div>
  );
}

function ErrorScreen({ title, body }: { title: string; body: string }) {
  return (
    <Shell>
      <span className="font-mono text-xs uppercase tracking-wider text-red-600">
        // error
      </span>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="text-sm leading-relaxed text-graphite-dark">{body}</p>
    </Shell>
  );
}
