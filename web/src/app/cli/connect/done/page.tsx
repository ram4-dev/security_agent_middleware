// Vista post-aprobación. El CLI ya tiene (o va a tener en el próximo poll)
// el token. Esta página solo le confirma al user que puede cerrar la pestaña.
/* eslint-disable react/jsx-no-comment-textnodes */

export default function CliConnectDonePage() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 py-16">
        <div
          className="flex w-full flex-col gap-6 border border-graphite-dark/20 bg-paper p-8 md:p-10"
          style={{ borderRadius: "var(--radius)" }}
        >
          <span className="font-mono text-xs uppercase tracking-wider text-emerald-700">
            // ok
          </span>
          <h1 className="text-2xl font-semibold tracking-tight">
            Tu CLI quedó vinculado.
          </h1>
          <p className="text-sm leading-relaxed text-graphite-dark">
            Volvé a la terminal — el comando <code className="font-mono">npx tranquera setup</code> ya
            recibió tu token y terminó. Podés cerrar esta pestaña.
          </p>
          <p className="font-mono text-[11px] leading-relaxed text-graphite">
            // si vas a vincular otra máquina, corré npx tranquera setup desde
            allá. cada device es independiente.
          </p>
        </div>
      </main>
    </div>
  );
}
