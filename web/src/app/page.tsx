import Link from "next/link";

const TEAM = [
  { name: "Christian Rojas Rodriguez", gh: "Christian-Rojas-Rodriguez" },
  { name: "Federico Hörl", gh: "fede-h" },
  { name: "Mauricio Genta", gh: "5y5F4il" },
  { name: "Jaime Aza", gh: "Jjat00" },
  { name: "Tomás Leonel Degese", gh: "tomileonel" },
];

const REPO_URL = "https://github.com/platanus-hack/platanus-hack-26-ar-team-22";

export default function HomePage() {
  return (
    <main className="flex flex-col">
      <SiteHeader />
      <Hero />
      <ProblemSection />
      <HowItWorksSection />
      <WhyLatamSection />
      <ManifestoSection />
      <SiteFooter />
    </main>
  );
}

function SiteHeader() {
  return (
    <header className="w-full border-b border-graphite-dark/15">
      <div className="mx-auto max-w-6xl flex items-center justify-between px-6 py-5">
        <Wordmark />
        <nav className="hidden md:flex items-center gap-8 font-mono text-xs text-graphite uppercase tracking-wide">
          <a href="#problema" className="hover:text-ink transition-colors">
            // problema
          </a>
          <a href="#como-funciona" className="hover:text-ink transition-colors">
            // cómo funciona
          </a>
          <a href="#latam" className="hover:text-ink transition-colors">
            // por qué latam
          </a>
        </nav>
        <Link
          href={REPO_URL}
          className="font-mono text-xs text-ink underline underline-offset-4 hover:text-graphite transition-colors"
        >
          GitHub →
        </Link>
      </div>
    </header>
  );
}

function Wordmark({ size = "sm" }: { size?: "sm" | "lg" }) {
  const wordSize = size === "lg" ? "text-5xl md:text-7xl" : "text-xl";
  const markSize = size === "lg" ? "h-14 w-14 md:h-20 md:w-20" : "h-6 w-6";
  return (
    <Link href="/" className="flex items-center gap-3">
      <TranqueraMark className={markSize} />
      <span
        className={`${wordSize} font-sans font-semibold tracking-tight text-ink lowercase`}
      >
        tranquera
      </span>
    </Link>
  );
}

// Logo construction per identidad/design.md § 4:
//   8u × 6u box, 2 postes (1u × 6u) separated by 2u, 2 travesaños (5u × 1u)
function TranqueraMark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 80 60" fill="currentColor" aria-hidden className={className}>
      <rect x="20" y="0" width="10" height="60" />
      <rect x="50" y="0" width="10" height="60" />
      <rect x="15" y="12" width="50" height="10" />
      <rect x="15" y="38" width="50" height="10" />
    </svg>
  );
}

function Hero() {
  return (
    <section className="w-full">
      <div className="mx-auto max-w-6xl px-6 pt-20 pb-24 md:pt-32 md:pb-32 flex flex-col gap-10">
        <Wordmark size="lg" />
        <p className="font-mono text-sm text-graphite max-w-3xl">
          // un paso controlado entre la intención y la respuesta
        </p>
        <h1 className="text-4xl md:text-6xl font-semibold leading-tight tracking-tight max-w-4xl">
          El firewall de Claude Code que tu compliance officer va a aprobar.
        </h1>
        <p className="text-lg md:text-xl text-graphite-dark max-w-2xl leading-relaxed">
          Reglas no-code, redacción en runtime y auditoría completa.
          Tus devs siguen usando Claude Code; vos decidís qué sale del perímetro.
        </p>
        <div className="flex flex-wrap items-center gap-4 mt-2">
          <Link
            href="/admin?demo=1"
            className="inline-flex items-center justify-center bg-ink text-paper px-6 py-3 font-medium hover:bg-graphite-dark transition-colors"
            style={{ borderRadius: "var(--radius)" }}
          >
            Ver el admin demo →
          </Link>
          <Link
            href={REPO_URL}
            className="inline-flex items-center justify-center border border-ink text-ink px-6 py-3 font-medium hover:bg-ink hover:text-paper transition-colors"
            style={{ borderRadius: "var(--radius)" }}
          >
            Ver en GitHub
          </Link>
        </div>
      </div>
    </section>
  );
}

function SectionHeading({ tag, title }: { tag: string; title: string }) {
  return (
    <div className="flex flex-col gap-3 mb-12">
      <span className="font-mono text-xs text-graphite uppercase tracking-wider">
        // {tag}
      </span>
      <h2 className="text-3xl md:text-4xl font-semibold tracking-tight max-w-3xl">
        {title}
      </h2>
    </div>
  );
}

function ProblemSection() {
  const cases = [
    {
      tag: "01 · credencial",
      title: "Leak de AWS key",
      prompt: "ayudame a debuggear esto: AKIAIOSFODNN7EXAMPLE",
      consequence: "Tu access key sale del perímetro y queda en logs de Anthropic.",
    },
    {
      tag: "02 · cliente",
      title: "Mención de cliente real",
      prompt: "escribime un email para Acme Corp explicando el bug de su pipeline",
      consequence: "Datos comerciales identificables salen sin mediación.",
    },
    {
      tag: "03 · secreto",
      title: "Paste accidental de .env",
      prompt: "no funciona el .env: DATABASE_URL=postgres://admin:Pa$$...",
      consequence: "Credenciales productivas viajan en un prompt cualquiera.",
    },
  ];

  return (
    <section
      id="problema"
      className="w-full bg-paper-soft/40 border-y border-graphite-dark/15"
    >
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <SectionHeading
          tag="el problema"
          title="Tus devs usan Claude Code. Vos no controlás qué pegan en cada prompt."
        />
        <div className="grid md:grid-cols-3 gap-6">
          {cases.map((c) => (
            <article
              key={c.tag}
              className="bg-paper border border-graphite-dark/20 p-6 flex flex-col gap-4"
              style={{ borderRadius: "var(--radius)" }}
            >
              <span className="font-mono text-xs text-graphite uppercase tracking-wider">
                // {c.tag}
              </span>
              <h3 className="text-xl font-semibold">{c.title}</h3>
              <pre className="font-mono text-xs text-ink bg-paper-soft/50 p-3 whitespace-pre-wrap break-words">
                $ claude &quot;{c.prompt}&quot;
              </pre>
              <p className="text-sm text-graphite-dark mt-auto">{c.consequence}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function HowItWorksSection() {
  const layers = [
    {
      n: "01",
      name: "Claude Code (cliente)",
      desc: "El dev sigue usando Claude Code igual. Solo configura ANTHROPIC_BASE_URL apuntando al proxy.",
    },
    {
      n: "02",
      name: "Interceptor — proxy modificable",
      desc: "Cada request pasa por una cascada de tres capas (Regex → Pattern → Haiku) con menos de 200 ms de overhead.",
    },
    {
      n: "03",
      name: "Admin Backoffice (no-code)",
      desc: "Compliance officers crean reglas con un visual builder. Nadie escribe regex a mano.",
    },
    {
      n: "04",
      name: "AI Suggestor",
      desc: "Después de N días, propone reglas nuevas con preview de matches. El admin aprueba con un click.",
    },
  ];

  return (
    <section id="como-funciona" className="w-full">
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <SectionHeading
          tag="cómo funciona"
          title="Cuatro capas. Una sola tranquera entre Claude Code y Anthropic."
        />

        <div className="flex flex-col gap-4 mb-16">
          {layers.map((layer) => (
            <div
              key={layer.n}
              className="grid grid-cols-[auto_1fr] md:grid-cols-[auto_auto_1fr] gap-x-8 gap-y-2 items-baseline border-l-2 border-ink pl-6 py-3"
            >
              <span className="font-mono text-sm text-graphite md:row-span-2">
                Layer {layer.n}
              </span>
              <h3 className="text-xl font-semibold">{layer.name}</h3>
              <p className="text-graphite-dark md:col-start-3 max-w-2xl">
                {layer.desc}
              </p>
            </div>
          ))}
        </div>

        <div
          className="border border-graphite-dark/20 p-6 md:p-10"
          style={{ borderRadius: "var(--radius)" }}
        >
          <span className="font-mono text-xs text-graphite uppercase tracking-wider mb-6 block">
            // cascada de detección — &lt; 200 ms
          </span>
          <div className="grid md:grid-cols-3 gap-6 font-mono text-sm">
            <CascadeStep
              step="1"
              name="Regex"
              latency="~5 ms"
              example="emails · tarjetas · AWS keys · JWTs"
            />
            <CascadeStep
              step="2"
              name="Pattern"
              latency="~20 ms"
              example=".env · id_rsa · *.pem · paths internos"
            />
            <CascadeStep
              step="3"
              name="Haiku judge"
              latency="~150 ms"
              example="reglas en lenguaje natural · contexto"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function CascadeStep({
  step,
  name,
  latency,
  example,
}: {
  step: string;
  name: string;
  latency: string;
  example: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline gap-3">
        <span className="text-graphite">capa {step}</span>
        <span className="text-ink font-medium text-base">{name}</span>
      </div>
      <span className="text-graphite-dark">{latency}</span>
      <p className="text-graphite-dark text-xs leading-relaxed">{example}</p>
    </div>
  );
}

function WhyLatamSection() {
  const sources = [
    {
      country: "Brasil",
      law: "PL 2338/2023",
      detail:
        "Risk-based, AIA obligatorio para alto riesgo, supervisión humana mandatoria.",
    },
    {
      country: "Argentina",
      law: "S-0071/2025",
      detail:
        "Registro nacional de sistemas IA + impact assessments + clasificación de riesgo.",
    },
    {
      country: "México",
      law: "CONAIA / Ley Federal IA",
      detail:
        "Autorización previa para sistemas de alto riesgo + documentación de safety y accountability.",
    },
  ];

  return (
    <section id="latam" className="w-full bg-ink text-paper">
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <div className="flex flex-col gap-3 mb-12">
          <span className="font-mono text-xs text-graphite uppercase tracking-wider">
            // por qué latam, ahora
          </span>
          <h2 className="text-3xl md:text-4xl font-semibold tracking-tight max-w-3xl">
            Cinco países, cinco leyes risk-based en simultáneo. Toda empresa con LLM en producción va a necesitar evidencia auditable.
          </h2>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {sources.map((s) => (
            <div
              key={s.country}
              className="border border-paper/15 p-6 flex flex-col gap-3"
              style={{ borderRadius: "var(--radius)" }}
            >
              <span className="font-mono text-xs text-graphite uppercase tracking-wider">
                // {s.country.toLowerCase()}
              </span>
              <h3 className="text-lg font-semibold">{s.law}</h3>
              <p className="text-sm text-paper/70 leading-relaxed">{s.detail}</p>
            </div>
          ))}
        </div>
        <p className="font-mono text-xs text-graphite mt-10 max-w-3xl leading-relaxed">
          // gap multilingüe documentado: XL-SafetyBench (state-of-the-art) no incluye portugués
          ni países latinoamericanos. La literatura de safety es &gt; 90 % inglés.
        </p>
      </div>
    </section>
  );
}

function ManifestoSection() {
  return (
    <section className="w-full">
      <div className="mx-auto max-w-3xl px-6 py-24 md:py-32 flex flex-col gap-8 text-center">
        <span className="font-mono text-xs text-graphite uppercase tracking-wider">
          // manifiesto
        </span>
        <p className="text-2xl md:text-3xl leading-relaxed font-medium">
          No es un escudo, no es una advertencia.
          Es una{" "}
          <em className="not-italic underline decoration-graphite underline-offset-8">
            aduana silenciosa
          </em>{" "}
          que aplica las reglas de la empresa sin interrumpir el ritmo de quien escribe.
        </p>
        <div className="grid grid-cols-3 gap-6 mt-10 font-mono text-sm">
          <Principle n="01" title="Preciso" />
          <Principle n="02" title="Silencioso" />
          <Principle n="03" title="Permanente" />
        </div>
      </div>
    </section>
  );
}

function Principle({ n, title }: { n: string; title: string }) {
  return (
    <div className="flex flex-col items-center gap-2 border-t-2 border-ink pt-4">
      <span className="text-graphite">{n} ·</span>
      <span className="text-ink font-medium text-base">{title}</span>
    </div>
  );
}

function SiteFooter() {
  return (
    <footer className="w-full border-t border-graphite-dark/15 mt-auto">
      <div className="mx-auto max-w-6xl px-6 py-12 flex flex-col gap-8">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <Wordmark />
          <p className="font-mono text-xs text-graphite max-w-md">
            // platanus hack 26 · buenos aires · team 22 · track ai security
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {TEAM.map((t) => (
            <a
              key={t.gh}
              href={`https://github.com/${t.gh}`}
              className="flex flex-col gap-1 group"
            >
              <span className="text-sm text-ink group-hover:text-graphite-dark transition-colors">
                {t.name}
              </span>
              <span className="font-mono text-xs text-graphite group-hover:text-ink transition-colors">
                @{t.gh}
              </span>
            </a>
          ))}
        </div>
        <div className="flex items-center justify-between border-t border-graphite-dark/15 pt-6 font-mono text-xs text-graphite">
          <span>// sistema · v1.0 · 2026</span>
          <Link href={REPO_URL} className="hover:text-ink transition-colors">
            github →
          </Link>
        </div>
      </div>
    </footer>
  );
}
