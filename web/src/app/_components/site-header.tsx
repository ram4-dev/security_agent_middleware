/* eslint-disable react/jsx-no-comment-textnodes */
import Image from "next/image";
import Link from "next/link";

const REPO_URL = "https://github.com/platanus-hack/platanus-hack-26-ar-team-22";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 w-full border-b border-graphite-dark/15 bg-paper/85 backdrop-blur supports-[backdrop-filter]:bg-paper/70">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Wordmark />
        <nav className="hidden items-center gap-8 font-mono text-xs uppercase tracking-wide text-graphite md:flex">
          <Link href="/#problema" className="transition-colors hover:text-ink">
            // problema
          </Link>
          <Link
            href="/#como-funciona"
            className="transition-colors hover:text-ink"
          >
            // cómo funciona
          </Link>
          <Link href="/#install" className="transition-colors hover:text-ink">
            // install
          </Link>
          <Link href="/#trace" className="transition-colors hover:text-ink">
            // trace
          </Link>
          <Link href="/#latam" className="transition-colors hover:text-ink">
            // latam
          </Link>
        </nav>
        <div className="flex items-center gap-4">
          <Link
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden font-mono text-xs text-ink underline underline-offset-4 transition-colors hover:text-graphite md:inline"
          >
            github →
          </Link>
          <Link
            href="/admin/login"
            className="inline-flex items-center bg-ink px-4 py-2 font-mono text-xs uppercase tracking-wider text-paper transition-colors hover:bg-graphite-dark"
            style={{ borderRadius: "var(--radius)" }}
          >
            login →
          </Link>
        </div>
      </div>
    </header>
  );
}

export function Wordmark({ size = "sm" }: { size?: "sm" | "lg" }) {
  const wordSize = size === "lg" ? "text-6xl md:text-8xl" : "text-xl";
  const markSize = size === "lg" ? "h-16 w-16 md:h-24 md:w-24" : "h-6 w-6";
  return (
    <Link href="/" className="flex items-center gap-3">
      <TranqueraMark className={markSize} />
      <span
        className={`${wordSize} font-sans font-semibold lowercase tracking-tight text-ink`}
      >
        tranquera
      </span>
    </Link>
  );
}

export function TranqueraMark({ className = "" }: { className?: string }) {
  // Tamaños raster grandes para que la versión hero (h-24 w-24) se vea
  // nítida en pantallas retina.
  return (
    <Image
      src="/logo.png"
      alt="Tranquera"
      width={256}
      height={256}
      priority
      className={`${className} object-contain`}
      style={{ borderRadius: "var(--radius)" }}
    />
  );
}
