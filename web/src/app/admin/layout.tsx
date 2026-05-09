// Admin shell. Sidebar + header + main slot. Server component — the proxy
// (src/proxy.ts) has already gated access by the time we render here.
/* eslint-disable react/jsx-no-comment-textnodes */
import Image from "next/image";
import Link from "next/link";
import { isAuthConfigured, signOut } from "@/auth";
import { ensureAdminSession } from "@/lib/admin-session";
import { AdminNav } from "./_components/nav";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // ensureAdminSession() onboardea al admin (crea org si no existe) en su
  // primer hit a cualquier ruta /admin/*. Es el reemplazo de la rama de
  // auto-create que sacamos de resolveOrgForUser.
  const session = await ensureAdminSession();
  const email = session?.email ?? "—";
  const orgId = session?.orgId ?? "—";

  // Dev no debería estar acá: el back-office es solo-admin. Mostramos un
  // mensaje claro en vez de la UI de admin (que confunde y no se puede usar).
  if (session?.role === "dev") {
    return <DevForbidden email={email} orgId={orgId} />;
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="sticky top-0 z-30 border-b border-graphite-dark/15 bg-paper/85 backdrop-blur supports-[backdrop-filter]:bg-paper/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-3">
            <TranqueraMark className="h-6 w-6" />
            <span className="text-xl font-semibold lowercase tracking-tight">
              tranquera
            </span>
            <span className="ml-3 border-l border-graphite-dark/20 pl-3 font-mono text-xs uppercase tracking-wider text-graphite">
              admin
            </span>
          </Link>
          <div className="flex items-center gap-4 font-mono text-xs uppercase tracking-wider text-graphite">
            <span>// org · {orgId}</span>
            <span className="hidden md:inline">// {email}</span>
            {isAuthConfigured() ? <SignOutButton /> : null}
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl gap-8 px-6 py-10 md:py-14">
        <aside className="w-44 shrink-0">
          <AdminNav />
          <p className="mt-10 font-mono text-[11px] leading-relaxed text-graphite">
            // org · {orgId}
            <br />
            // {isAuthConfigured() ? "google session" : "demo session"}
          </p>
        </aside>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
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
        className="border border-graphite-dark/30 px-2 py-1 transition-colors hover:border-ink hover:text-ink"
        style={{ borderRadius: "var(--radius)" }}
      >
        salir
      </button>
    </form>
  );
}

function TranqueraMark({ className = "" }: { className?: string }) {
  return (
    <Image
      src="/logo.png"
      alt="Tranquera"
      width={64}
      height={64}
      className={`${className} object-contain`}
      style={{ borderRadius: "var(--radius)" }}
    />
  );
}
