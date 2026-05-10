// Admin shell. Sidebar + header + main slot. Server component — the proxy
// (src/proxy.ts) has already gated access by the time we render here.
/* eslint-disable react/jsx-no-comment-textnodes */
import Link from "next/link";
import { isAuthConfigured, signOut } from "@/auth";
import { ensureAdminSession } from "@/lib/admin-session";
import { readThemeCookie } from "@/lib/theme";
import { AdminShell } from "./_components/admin-shell";
import { ThemeSwitcher } from "./_components/theme-switcher";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // ensureAdminSession() onboardea al admin (crea org si no existe) en su
  // primer hit a cualquier ruta /admin/*. Es el reemplazo de la rama de
  // auto-create que sacamos de resolveOrgForUser.
  const session = await ensureAdminSession();

  // Sin sesión solo se llega acá vía /admin/login (proxy.ts gatea el resto).
  // Renderizamos children pelado para que la página de login no herede el
  // sidebar/header del admin con opciones a las que el visitante todavía no
  // puede entrar.
  if (!session) {
    return <>{children}</>;
  }

  const email = session.email;
  const orgId = session.orgId;
  const theme = await readThemeCookie();

  // Dev no debería estar acá: el back-office es solo-admin. Mostramos un
  // mensaje claro en vez de la UI de admin (que confunde y no se puede usar).
  if (session.role === "dev") {
    return <DevForbidden email={email} orgId={orgId} />;
  }

  return (
    <div
      data-admin-shell
      data-theme={theme}
      className="flex h-svh flex-col overflow-hidden bg-paper text-ink"
    >
      <AdminShell
        email={email}
        orgId={orgId}
        authConfigured={isAuthConfigured()}
        signOut={isAuthConfigured() ? <SignOutButton /> : null}
        themeSwitcher={<ThemeSwitcher initial={theme} />}
      >
        {children}
      </AdminShell>
    </div>
  );
}

function DevForbidden({ email, orgId }: { email: string; orgId: string }) {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 py-16">
        <div
          className="flex w-full flex-col gap-6 border border-graphite-dark/20 bg-paper p-8 md:p-10"
          style={{ borderRadius: "var(--radius)" }}
        >
          <span className="font-mono text-xs uppercase tracking-wider text-graphite">
            // forbidden
          </span>
          <h1 className="text-2xl font-semibold tracking-tight">
            Estás logueado como dev.
          </h1>
          <p className="text-sm leading-relaxed text-graphite-dark">
            El back-office es solo para admins. Vos ({email}) sos un dev de la
            org <strong>{orgId}</strong> — usá Claude Code normal, ya estás
            siendo atribuido en cada prompt.
          </p>
          <div className="flex items-center justify-between gap-4">
            <Link
              href="/"
              className="font-mono text-[11px] uppercase tracking-wider text-graphite hover:text-ink"
            >
              ← volver al inicio
            </Link>
            <SignOutButton />
          </div>
        </div>
      </main>
    </div>
  );
}

function SignOutButton() {
  return (
    <form
      action={async () => {
        "use server";
        await signOut({ redirectTo: "/" });
      }}
    >
      <button
        type="submit"
        className="border border-graphite-dark/35 px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-graphite transition-colors hover:border-ink hover:text-ink"
        style={{ borderRadius: "var(--radius)" }}
      >
        salir
      </button>
    </form>
  );
}

