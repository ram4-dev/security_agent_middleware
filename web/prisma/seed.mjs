/**
 * Demo seed for Tranquera admin.
 * Uses `pg` directly (already installed) — no Prisma adapter needed.
 * Run: node prisma/seed.mjs
 *
 * Loads DATABASE_URL from .env.local then .env (same priority as Next.js).
 */

import { createRequire } from "module";
import { readFileSync, existsSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── .env loader (manual, no deps) ──────────────────────────────────────────
function loadEnv(path) {
  if (!existsSync(path)) return;
  const lines = readFileSync(path, "utf-8").split("\n");
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    const val = line.slice(eq + 1).trim().replace(/^["']|["']$/g, "");
    if (!(key in process.env)) process.env[key] = val;
  }
}

const webDir = join(__dirname, "..");
loadEnv(join(webDir, ".env.local"));
loadEnv(join(webDir, ".env"));

// ── pg client ───────────────────────────────────────────────────────────────
const require = createRequire(import.meta.url);
const { Pool } = require("pg");

const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const db = { query: (sql, params) => pool.query(sql, params) };

// ── helpers ─────────────────────────────────────────────────────────────────
function uuid() {
  return crypto.randomUUID();
}

function daysAgo(n, jitterHours = 0) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  d.setHours(d.getHours() - jitterHours);
  return d;
}

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

// ── CLI args ────────────────────────────────────────────────────────────────
function parseArgs(argv) {
  const out = { policiesOnly: false, orgId: null };
  for (const a of argv) {
    if (a === "--policies-only") out.policiesOnly = true;
    else if (a.startsWith("--org-id=")) out.orgId = a.slice("--org-id=".length);
  }
  return out;
}

const CLI = parseArgs(process.argv.slice(2));

// ── data definitions ────────────────────────────────────────────────────────
const ORG_ID = CLI.orgId ?? "demo";

const POLICIES = [
  // ── Regex / credentials ────────────────────────────────────────────────────
  {
    slug: "aws-access-key",
    domain: "credentials",
    layer: "regex",
    rule: "Detecta claves de acceso AWS (AKIA…) en cualquier mensaje.",
    pattern: "AKIA[0-9A-Z]{16}",
    defaultAction: "BLOCK",
    severity: "high",
  },
  {
    slug: "generic-api-key",
    domain: "credentials",
    layer: "regex",
    rule: "Detecta patrones genéricos de API keys (sk-… / token: …).",
    pattern: "(sk-[a-zA-Z0-9]{32,}|api[_-]?key[^\\S\\r\\n]*[:=][^\\S\\r\\n]*['\"]?[a-zA-Z0-9/_\\-]{20,})",
    defaultAction: "REDACT",
    severity: "high",
  },
  // ── Regex / PII ────────────────────────────────────────────────────────────
  {
    slug: "email-pii",
    domain: "pii",
    layer: "regex",
    rule: "Detecta direcciones de correo electrónico en prompts.",
    pattern: "[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}",
    defaultAction: "REDACT",
    severity: "medium",
  },
  {
    slug: "cuil-cuit",
    domain: "pii",
    layer: "regex",
    rule: "Detecta CUIL/CUIT argentinos (XX-XXXXXXXX-X).",
    pattern: "\\b(20|23|24|27|30|33|34)-?\\d{8}-?\\d\\b",
    defaultAction: "REDACT",
    severity: "medium",
  },
  {
    slug: "phone-number-ar",
    domain: "pii",
    layer: "regex",
    rule: "Detecta números de teléfono argentinos en formato +54 o 011.",
    pattern: "(\\+54|0?11|0?[2-9]\\d{2,3})[\\s\\-]?\\d{4}[\\s\\-]?\\d{4}",
    defaultAction: "REDACT",
    severity: "medium",
  },
  // ── Pattern / internal paths ───────────────────────────────────────────────
  {
    slug: "env-files",
    domain: "internal_paths",
    layer: "pattern",
    rule: "Bloquea archivos de configuración de entorno que pueden contener secrets.",
    pattern: null,
    matchConfig: { extensions: [".env", ".env.local", ".env.production"] },
    defaultAction: "BLOCK",
    severity: "high",
  },
  {
    slug: "private-keys",
    domain: "internal_paths",
    layer: "pattern",
    rule: "Bloquea archivos de clave privada (PEM, p12, pfx).",
    pattern: null,
    matchConfig: { extensions: [".pem", ".p12", ".pfx", ".key"] },
    defaultAction: "BLOCK",
    severity: "high",
  },
  // ── NL / business_policy — estándares corporativos de Acme Corp ────────────
  {
    slug: "competitor-mention",
    domain: "business_policy",
    layer: "nl",
    rule: "El usuario menciona o pide comparar con competidores directos (OpenAI, Cursor, Copilot, GitHub).",
    pattern: null,
    defaultAction: "WARN",
    severity: "medium",
  },
  {
    slug: "roadmap-disclosure",
    domain: "business_policy",
    layer: "nl",
    rule: "El prompt revela o pregunta sobre el roadmap de producto, features no lanzadas o planes estratégicos internos.",
    pattern: null,
    defaultAction: "BLOCK",
    severity: "high",
  },
  {
    slug: "direct-production-access",
    domain: "business_policy",
    layer: "nl",
    rule: "El objetivo de Acme Corp es que ninguna modificación llegue a producción sin pasar por el proceso formal de change management. Los empleados que soliciten asistencia para ejecutar comandos, modificar datos o deployar directamente en prod sin ticket aprobado deben ser bloqueados.",
    pattern: null,
    defaultAction: "BLOCK",
    severity: "high",
  },
  {
    slug: "financial-projections",
    domain: "business_policy",
    layer: "nl",
    rule: "El objetivo de Acme Corp es mantener absoluta confidencialidad sobre su situación financiera. Está prohibido mencionar en prompts métricas como ARR, MRR, runway, valuación, proyecciones de revenue, cap table o cualquier dato financiero no público de la compañía.",
    pattern: null,
    defaultAction: "BLOCK",
    severity: "high",
  },
  {
    slug: "skip-code-review",
    domain: "business_policy",
    layer: "nl",
    rule: "Los empleados que pregunten cómo saltear, bypassear o evitar el proceso de code review establecido en el Engineering Handbook de Acme Corp deben ser advertidos. Todo cambio a main requiere al menos una aprobación de un peer.",
    pattern: null,
    defaultAction: "WARN",
    severity: "medium",
  },
  {
    slug: "pii-retention-violation",
    domain: "business_policy",
    layer: "nl",
    rule: "El objetivo de Acme Corp es cumplir con LGPD y Habeas Data. Toda función que persista datos personales de usuarios debe incluir una política de retención (TTL máximo 90 días). Los devs que consulten sobre almacenar PII indefinidamente deben ser advertidos.",
    pattern: null,
    defaultAction: "WARN",
    severity: "medium",
  },
  // ── NL / code — estándares de ingeniería de Acme Corp ─────────────────────
  {
    slug: "hardcoded-credentials",
    domain: "code",
    layer: "nl",
    rule: "El código generado contiene credenciales hardcodeadas, tokens o contraseñas en texto plano.",
    pattern: null,
    defaultAction: "BLOCK",
    severity: "high",
  },
  {
    slug: "code-must-be-english",
    domain: "code",
    layer: "nl",
    rule: "El objetivo de Acme Corp es mantener una base de código legible para equipos distribuidos. Todas las funciones, variables, comentarios y mensajes de error deben estar en inglés. Los devs que generen código con identificadores o comentarios en español deben ser advertidos.",
    pattern: null,
    defaultAction: "WARN",
    severity: "low",
  },
  {
    slug: "async-without-timeout",
    domain: "code",
    layer: "nl",
    rule: "El objetivo de Acme Corp es garantizar la resiliencia de sus servicios. Toda función asíncrona que llame a un servicio externo o base de datos debe incluir un timeout configurado explícitamente. Las funciones sin timeout violan el estándar de ingeniería y deben generar una advertencia.",
    pattern: null,
    defaultAction: "WARN",
    severity: "medium",
  },
  {
    slug: "informal-language-code",
    domain: "code",
    layer: "nl",
    rule: "Los empleados que utilicen palabras malsonantes, ofensivas o expresiones informales (wtf, mierda, cagada, hack sucio, no sé por qué funciona) en comentarios de código, mensajes de commit o nombres de variables deben ser advertidos sobre el estándar de comunicación profesional de Acme Corp.",
    pattern: null,
    defaultAction: "WARN",
    severity: "low",
  },
];

// ── realistic interaction scenarios ─────────────────────────────────────────
const SCENARIOS = [
  // ── BLOCK ──────────────────────────────────────────────────────────────────

  // aws-access-key — regex hit
  {
    action: "BLOCK",
    reason: "Clave de acceso AWS detectada en el prompt. Request bloqueado.",
    policyHits: [{ layer: "regex", slug: "aws-access-key" }],
    promptTemplate:
      "Tengo este error al deployar en Lambda. Mi config:\nAWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\nAWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n¿Por qué falla el rol?",
    latency: [18, 45],
  },
  {
    action: "BLOCK",
    reason: "Clave de acceso AWS detectada en el prompt. Request bloqueado.",
    policyHits: [{ layer: "regex", slug: "aws-access-key" }],
    promptTemplate:
      "El deploy de ECS falla con AccessDenied. Credenciales actuales: AKIAJ5ZFAKEKEY9DEMO1\nSecret: fakeS3cr3tKey/DEMO+456+XYZ99. ¿Qué IAM policy falta?",
    latency: [16, 42],
  },

  // roadmap-disclosure — NL hit
  {
    action: "BLOCK",
    reason: "El prompt expone features de roadmap no lanzadas. Request bloqueado.",
    policyHits: [{ layer: "nl", slug: "roadmap-disclosure" }],
    promptTemplate:
      "Redactá el PRD para la integración de pagos con Mercado Pago que vamos a lanzar en Q3. Incluí los endpoints que aún no están en producción.",
    latency: [120, 220],
  },
  {
    action: "BLOCK",
    reason: "Divulgación de feature no anunciada detectada. Request bloqueado.",
    policyHits: [{ layer: "nl", slug: "roadmap-disclosure" }],
    promptTemplate:
      "Ayudame a escribir el anuncio del nuevo módulo de IA generativa que vamos a revelar en el evento de octubre. El nombre en clave es Proyecto Cóndor y todavía es confidencial.",
    latency: [130, 240],
  },

  // hardcoded-credentials — NL hit
  {
    action: "BLOCK",
    reason: "Solicitud de código con credenciales hardcodeadas detectada. Request bloqueado.",
    policyHits: [{ layer: "nl", slug: "hardcoded-credentials" }],
    promptTemplate:
      "Escribí un script de Python para conectarse a nuestra base de datos. User: admin, password: Acm3S3cur3!2024, host: db.acme.internal.",
    latency: [110, 200],
  },
  {
    action: "BLOCK",
    reason: "Código con password en texto plano detectado. Request bloqueado.",
    policyHits: [{ layer: "nl", slug: "hardcoded-credentials" }],
    promptTemplate:
      "Completá este snippet de Node.js para conectar a Redis:\nconst client = createClient({ password: 'r3d1s$ecr3t2024', host: 'cache.internal' })",
    latency: [105, 195],
  },

  // direct-production-access — NL hit (nueva policy)
  {
    action: "BLOCK",
    reason: "Solicitud de acceso directo a producción sin proceso de change management. Request bloqueado.",
    policyHits: [{ layer: "nl", slug: "direct-production-access" }],
    promptTemplate:
      "Necesito modificar directamente la tabla users en prod para corregir los registros del evento de ayer. ¿Cómo me conecto al Postgres de producción y ejecuto el UPDATE sin pasar por el proceso de change management?",
    latency: [125, 230],
  },
  {
    action: "BLOCK",
    reason: "Intento de deploy directo a producción sin ticket aprobado. Request bloqueado.",
    policyHits: [{ layer: "nl", slug: "direct-production-access" }],
    promptTemplate:
      "Es urgente, el cliente está caído. ¿Cómo hago kubectl apply directo en el cluster de prod sin esperar la aprobación del change board? El ticket tarda 2 horas.",
    latency: [118, 215],
  },

  // financial-projections — NL hit (nueva policy)
  {
    action: "BLOCK",
    reason: "Datos financieros confidenciales de la empresa detectados. Request bloqueado.",
    policyHits: [{ layer: "nl", slug: "financial-projections" }],
    promptTemplate:
      "Preparame la presentación del board de inversores para el jueves. ARR actual: $2.1M, proyectamos llegar a $5M para Q4 y tenemos 18 meses de runway. ¿Cómo ordeno los slides?",
    latency: [135, 245],
  },
  {
    action: "BLOCK",
    reason: "Métricas financieras no públicas detectadas. Request bloqueado.",
    policyHits: [{ layer: "nl", slug: "financial-projections" }],
    promptTemplate:
      "Ayudame a calcular la valuación pre-money para la ronda Serie A. Tenemos $180K MRR, churn del 2% y queremos pedir un múltiplo de 8x ARR.",
    latency: [128, 235],
  },

  // ── REDACT ─────────────────────────────────────────────────────────────────

  // email-pii — regex hit
  {
    action: "REDACT",
    reason: "Dirección de email redactada del prompt.",
    policyHits: [{ layer: "regex", slug: "email-pii" }],
    promptTemplate:
      "El cliente [REDACTED] reportó un bug en el checkout. ¿Cómo lo debuggeo?",
    latency: [12, 30],
  },
  {
    action: "REDACT",
    reason: "Dirección de email redactada del prompt.",
    policyHits: [{ layer: "regex", slug: "email-pii" }],
    promptTemplate:
      "¿Por qué falla la invitación que le mandé a [REDACTED]? El link expira antes de que abra el mail.",
    latency: [11, 28],
  },
  {
    action: "REDACT",
    reason: "Dirección de email redactada del prompt.",
    policyHits: [{ layer: "regex", slug: "email-pii" }],
    promptTemplate:
      "Necesito filtrar todos los registros del usuario [REDACTED] para el reporte de auditoría. ¿Cómo armo la query?",
    latency: [10, 26],
  },

  // generic-api-key — regex hit
  {
    action: "REDACT",
    reason: "API key detectada y redactada. El prompt continúa sin el secret.",
    policyHits: [{ layer: "regex", slug: "generic-api-key" }],
    promptTemplate:
      "¿Por qué falla este fetch? Headers: { Authorization: 'Bearer [REDACTED]' }. El endpoint devuelve 401.",
    latency: [14, 35],
  },
  {
    action: "REDACT",
    reason: "Token de API redactado del prompt.",
    policyHits: [{ layer: "regex", slug: "generic-api-key" }],
    promptTemplate:
      "Integré el webhook de Stripe pero sigo recibiendo signature mismatch. Mi endpoint secret es [REDACTED]. ¿Qué puede estar fallando?",
    latency: [13, 32],
  },

  // cuil-cuit — regex hit
  {
    action: "REDACT",
    reason: "CUIT/CUIL argentino redactado del prompt.",
    policyHits: [{ layer: "regex", slug: "cuil-cuit" }],
    promptTemplate:
      "Generá un certificado para la empresa con CUIT [REDACTED]. Necesito el XML del AFIP.",
    latency: [10, 28],
  },
  {
    action: "REDACT",
    reason: "CUIL de empleado redactado del prompt.",
    policyHits: [{ layer: "regex", slug: "cuil-cuit" }],
    promptTemplate:
      "Procesá el alta del empleado en el sistema. Su CUIL es [REDACTED] y su fecha de ingreso fue el 1 de marzo.",
    latency: [9, 25],
  },

  // phone-number-ar — regex hit (nueva policy)
  {
    action: "REDACT",
    reason: "Número de teléfono argentino redactado del prompt.",
    policyHits: [{ layer: "regex", slug: "phone-number-ar" }],
    promptTemplate:
      "El cliente llamó al [REDACTED] para reportar el bug de pagos. ¿Cómo le mando el fix por WhatsApp?",
    latency: [11, 27],
  },
  {
    action: "REDACT",
    reason: "Número de teléfono redactado del prompt.",
    policyHits: [{ layer: "regex", slug: "phone-number-ar" }],
    promptTemplate:
      "Actualizá el campo phone del usuario id=4521 con el número [REDACTED]. ¿Cómo hago el UPDATE con validación de formato?",
    latency: [10, 24],
  },

  // ── WARN ───────────────────────────────────────────────────────────────────

  // competitor-mention — NL hit
  {
    action: "WARN",
    reason: "Mención de herramienta competidora detectada. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "competitor-mention" }],
    promptTemplate:
      "¿Cómo se compara nuestra latencia con la de Cursor? ¿Deberíamos migrar a GitHub Copilot para los devs?",
    latency: [105, 190],
  },
  {
    action: "WARN",
    reason: "Comparación con competidor externo detectada. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "competitor-mention" }],
    promptTemplate:
      "OpenAI acaba de lanzar Codex 2. ¿Qué ventajas tenemos nosotros respecto a ellos para vender a enterprise?",
    latency: [118, 210],
  },
  {
    action: "WARN",
    reason: "Análisis comparativo con competidor detectado. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "competitor-mention" }],
    promptTemplate:
      "¿Qué features tiene Cursor que nosotros no tengamos? Quiero armar un competitive analysis para el equipo de producto antes del sprint planning.",
    latency: [112, 205],
  },
  {
    action: "WARN",
    reason: "Mención de herramienta competidora en contexto de adopción. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "competitor-mention" }],
    promptTemplate:
      "El equipo de mobile quiere probar GitHub Copilot porque dicen que soporta mejor Swift. ¿Cómo evaluamos si cambiamos?",
    latency: [108, 198],
  },

  // informal-language-code — NL hit (nueva policy)
  {
    action: "WARN",
    reason: "Lenguaje informal detectado en código. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "informal-language-code" }],
    promptTemplate:
      "// wtf por qué esto no compila\nfunction calcTotal(items) {\n  // no sé por qué funciona pero funciona\n  return items.reduce((a, b) => a + b.price, 0)\n}\n¿Qué está mal acá?",
    latency: [95, 180],
  },
  {
    action: "WARN",
    reason: "Expresiones informales en comentarios de código detectadas. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "informal-language-code" }],
    promptTemplate:
      "Tengo este hack de mierda que dejó el dev anterior y ahora hay que mantenerlo. ¿Cómo lo refactorizo sin romper nada?\n\n// HACK TEMPORAL (lleva 2 años acá)\nif (user.role === 'admin' || user.id === 42) { ... }",
    latency: [100, 185],
  },
  {
    action: "WARN",
    reason: "Lenguaje inapropiado en nombre de variable detectado. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "informal-language-code" }],
    promptTemplate:
      "La función `fixCagadaDelMiercoles` está fallando en staging. Es la que parsea los webhooks de Stripe. ¿Le cambio el nombre o la reescribo?",
    latency: [92, 175],
  },

  // skip-code-review — NL hit (nueva policy)
  {
    action: "WARN",
    reason: "Intento de saltear el proceso de code review detectado. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "skip-code-review" }],
    promptTemplate:
      "¿Cómo pusheo directo a main sin que salte la protección de la branch? Es urgente, hay un bug en prod y el reviewer no está disponible.",
    latency: [98, 185],
  },
  {
    action: "WARN",
    reason: "Consulta para evadir el proceso de review detectada. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "skip-code-review" }],
    promptTemplate:
      "¿Puedo hacer un force push a la rama release/2.4 para saltear el pipeline de CI que está tardando 45 minutos? El cliente está esperando el hotfix.",
    latency: [102, 190],
  },

  // pii-retention-violation — NL hit (nueva policy)
  {
    action: "WARN",
    reason: "Consulta sobre retención indefinida de PII detectada. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "pii-retention-violation" }],
    promptTemplate:
      "Guardamos todos los logs con nombre, email e IP de usuarios desde hace 4 años sin borrar nada. Las queries se ponen lentas. ¿Cómo indexo mejor en vez de borrar?",
    latency: [108, 195],
  },
  {
    action: "WARN",
    reason: "Almacenamiento indefinido de datos personales detectado. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "pii-retention-violation" }],
    promptTemplate:
      "¿Cómo diseño la tabla de historial de sesiones? Quiero guardar IP, user agent y timestamp de cada login de por vida para tener trazabilidad completa.",
    latency: [105, 192],
  },

  // code-must-be-english — NL hit (nueva policy)
  {
    action: "WARN",
    reason: "Código con identificadores en español detectado. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "code-must-be-english" }],
    promptTemplate:
      "function calcularDescuento(monto, porcentaje) {\n  // calcula el descuento final con validación\n  if (porcentaje > 100) throw new Error('porcentaje inválido')\n  return monto * (porcentaje / 100)\n}\n¿Por qué falla con decimales grandes?",
    latency: [96, 180],
  },
  {
    action: "WARN",
    reason: "Variables y comentarios en español en el código detectados. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "code-must-be-english" }],
    promptTemplate:
      "Revisá este módulo de facturación:\nconst obtenerFactura = async (idCliente) => {\n  // busca la factura del cliente en la base de datos\n  const resultado = await db.facturas.findOne({ cliente: idCliente })\n  return resultado\n}",
    latency: [99, 183],
  },

  // async-without-timeout — NL hit (nueva policy)
  {
    action: "WARN",
    reason: "Función asíncrona sin timeout configurado detectada. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "async-without-timeout" }],
    promptTemplate:
      "¿Cómo optimizo este fetch a la API de terceros?\nconst data = await fetch('https://api.proveedor.com/facturas')\nA veces tarda mucho y no sé por qué.",
    latency: [103, 188],
  },
  {
    action: "WARN",
    reason: "Llamada a servicio externo sin timeout ni circuit breaker detectada. Request permitido con advertencia.",
    policyHits: [{ layer: "nl", slug: "async-without-timeout" }],
    promptTemplate:
      "Integré la API de AFIP para validar CUITs. A veces la API no responde y mi servicio se queda colgado. ¿Cómo lo manejo?\nawait afip.validateCuit(cuit) // sin timeout",
    latency: [106, 193],
  },

  // ── LOG — normal benign requests ────────────────────────────────────────────
  {
    action: "LOG",
    reason: "Request procesado sin violaciones de política.",
    policyHits: [],
    promptTemplate: "Explicame la diferencia entre `useEffect` y `useLayoutEffect` en React.",
    latency: [8, 25],
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones de política.",
    policyHits: [],
    promptTemplate: "¿Cómo ordeno un array de objetos por fecha en JavaScript? Dame un ejemplo.",
    latency: [7, 22],
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones de política.",
    policyHits: [],
    promptTemplate: "Escribí un test unitario para esta función de validación de email con Jest.",
    latency: [9, 26],
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones de política.",
    policyHits: [],
    promptTemplate: "¿Cuál es la diferencia entre `async/await` y Promises en JavaScript?",
    latency: [6, 20],
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones de política.",
    policyHits: [],
    promptTemplate: "Ayudame a refactorizar este componente React para que use hooks en vez de clases.",
    latency: [11, 30],
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones de política.",
    policyHits: [],
    promptTemplate: "¿Cómo implemento paginación con cursor en GraphQL? Necesito que soporte filtros.",
    latency: [9, 27],
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones de política.",
    policyHits: [],
    promptTemplate: "Explicame el patrón Repository en TypeScript con un ejemplo de un CRUD básico.",
    latency: [8, 24],
  },

  // LOG — client name mentions (pattern for AI Suggestor to detect)
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "Nuestro cliente Banco Galicia reportó un error en el módulo de liquidaciones. ¿Cómo debuggeo esto?",
    latency: [7, 22],
    weight: 4,
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "Preparame el resumen del sprint para Claro Argentina. Esta semana entregamos la integración con su sistema de facturación.",
    latency: [8, 24],
    weight: 4,
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "¿Cómo optimizo esta query para el cliente Mercado Libre? Están teniendo timeouts en su módulo de pagos.",
    latency: [9, 25],
    weight: 4,
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "El equipo de YPF pregunta si podemos integrar con su API interna. ¿Qué información necesitamos pedirles?",
    latency: [7, 20],
    weight: 4,
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "Telecom Argentina necesita el reporte de disponibilidad del último mes en formato PDF. ¿Cómo genero el gráfico de uptime?",
    latency: [8, 23],
    weight: 4,
  },

  // LOG — internal host mentions (pattern for AI Suggestor to detect)
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "¿Por qué falla el healthcheck contra db-prod-01.internal? El servicio de pagos no puede conectarse.",
    latency: [8, 23],
    weight: 4,
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "Necesito conectarme a redis://cache.internal:6379 desde el servicio de notificaciones. ¿Cómo configuro el pool?",
    latency: [6, 18],
    weight: 4,
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "El microservicio auth.internal:8080 devuelve 502 intermitente. ¿Puede ser un timeout del load balancer?",
    latency: [9, 25],
    weight: 4,
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "¿Cómo configuro el service discovery para que api-gateway.internal encuentre automáticamente los nuevos pods?",
    latency: [8, 22],
    weight: 4,
  },

  // LOG — salary/compensation mentions (pattern for AI Suggestor to detect)
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "Redactá el email de oferta para el senior backend. El sueldo acordado es $5000 USD/mes + equity. ¿Cómo lo presento bien?",
    latency: [8, 22],
    weight: 4,
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "¿Cómo armo una planilla de bandas salariales para engineering? Tenemos juniors a $1500, mids a $3000, seniors a $5000 USD.",
    latency: [7, 20],
    weight: 4,
  },
  {
    action: "LOG",
    reason: "Request procesado sin violaciones.",
    policyHits: [],
    promptTemplate:
      "El candidato rechazó la oferta de $4200 USD y pide $4800. ¿Cómo redacto el contra-oferta de forma convincente?",
    latency: [9, 24],
    weight: 4,
  },
];

const RULE_SUGGESTIONS = [
  {
    proposedSlug: "internal-ip-range",
    proposedDomain: "internal_paths",
    proposedLayer: "regex",
    proposedRule: "Detecta referencias a rangos IP internos (10.x, 192.168.x, 172.16-31.x) en prompts.",
    proposedPattern: "\\b(10\\.\\d{1,3}|192\\.168|172\\.(1[6-9]|2[0-9]|3[01]))\\.\\d{1,3}\\.\\d{1,3}\\b",
    proposedAction: "WARN",
    proposedSeverity: "medium",
    matchCount: 47,
    examples: [
      {
        traceId: "trace-ex-001",
        promptRedacted: "¿Por qué no llega el ping a 10.0.1.45 desde el servicio de pagos?",
        createdAt: daysAgo(2).toISOString(),
      },
      {
        traceId: "trace-ex-002",
        promptRedacted: "El servidor en 192.168.1.100 no responde al healthcheck.",
        createdAt: daysAgo(3).toISOString(),
      },
    ],
    sourceHint: null,
    status: "pending",
  },
  {
    proposedSlug: "database-connection-string",
    proposedDomain: "credentials",
    proposedLayer: "regex",
    proposedRule: "Detecta connection strings de base de datos con credenciales embebidas.",
    proposedPattern: "(postgres|mysql|mongodb|redis):\\/\\/[^:]+:[^@]+@[\\w.\\-]+",
    proposedAction: "BLOCK",
    proposedSeverity: "high",
    matchCount: 31,
    examples: [
      {
        traceId: "trace-ex-003",
        promptRedacted: "¿Por qué falla la conexión? DSN: postgres://admin:s3cr3t@db.acme.internal:5432/prod",
        createdAt: daysAgo(1).toISOString(),
      },
    ],
    sourceHint: null,
    status: "pending",
  },
  {
    proposedSlug: "salary-disclosure",
    proposedDomain: "pii",
    proposedLayer: "nl",
    proposedRule: "El prompt menciona salarios específicos, compensaciones o bandas salariales de empleados.",
    proposedPattern: null,
    proposedAction: "BLOCK",
    proposedSeverity: "high",
    matchCount: 12,
    examples: [
      {
        traceId: "trace-ex-004",
        promptRedacted: "Redactá el email de oferta para el candidato. El sueldo acordado es $4.500 USD/mes.",
        createdAt: daysAgo(4).toISOString(),
      },
    ],
    sourceHint: null,
    status: "accepted",
  },
  {
    proposedSlug: "m-and-a-information",
    proposedDomain: "business_policy",
    proposedLayer: "nl",
    proposedRule: "El usuario menciona adquisiciones, fusiones o due diligence de empresas no públicas.",
    proposedPattern: null,
    proposedAction: "BLOCK",
    proposedSeverity: "high",
    matchCount: 8,
    examples: [
      {
        traceId: "trace-ex-005",
        promptRedacted: "Ayudame a preparar el data room para la due diligence de la startup que estamos evaluando comprar.",
        createdAt: daysAgo(5).toISOString(),
      },
    ],
    sourceHint: "google_workspace",
    status: "pending",
  },
  {
    proposedSlug: "legal-privilege",
    proposedDomain: "business_policy",
    proposedLayer: "nl",
    proposedRule: "El prompt contiene comunicaciones privilegiadas con abogados o estrategia legal interna.",
    proposedPattern: null,
    proposedAction: "WARN",
    proposedSeverity: "medium",
    matchCount: 5,
    examples: [],
    sourceHint: null,
    status: "rejected",
    rejectReason: "Muy amplio — genera demasiados falsos positivos en contexto de contratos de proveedores.",
  },
];

// ── main ─────────────────────────────────────────────────────────────────────
async function main() {
  console.log("🌱 Tranquera demo seed — empezando...\n");

  // 1. Truncate in FK-safe order
  console.log("🗑️  Limpiando tablas existentes...");
  await db.query(`
    TRUNCATE TABLE
      cli_device_codes,
      cli_tokens,
      rule_suggestions,
      interactions,
      policies,
      members,
      auth_verification_tokens,
      auth_sessions,
      auth_accounts,
      auth_users,
      organizations
    RESTART IDENTITY CASCADE
  `);
  console.log("   ✓ tablas limpias\n");

  // 2. Organization
  console.log("🏢 Creando organización demo...");
  await db.query(
    `INSERT INTO organizations (id, name, email_domain, created_at)
     VALUES ($1, $2, $3, NOW())`,
    [ORG_ID, "Acme Corp", "acme.com"],
  );
  console.log("   ✓ org demo / Acme Corp\n");

  // 3. Admin member
  console.log("👤 Creando member admin...");
  const memberId = uuid();
  await db.query(
    `INSERT INTO members (id, org_id, email, role, created_at)
     VALUES ($1, $2, $3, $4, NOW())`,
    [memberId, ORG_ID, "admin@acme.com", "admin"],
  );
  console.log("   ✓ admin@acme.com\n");

  // 4. Policies
  console.log("📋 Insertando políticas...");
  const policyIds = {};
  for (const p of POLICIES) {
    const id = uuid();
    policyIds[p.slug] = id;
    const matchConfig = p.matchConfig ? JSON.stringify(p.matchConfig) : null;
    await db.query(
      `INSERT INTO policies
         (id, org_id, slug, domain, layer, rule, pattern, match_config,
          default_action, severity, source, is_active, created_at, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12,NOW(),NOW())`,
      [
        id, ORG_ID, p.slug, p.domain, p.layer, p.rule,
        p.pattern ?? null, matchConfig,
        p.defaultAction, p.severity, "seed", true,
      ],
    );
    console.log(`   ✓ ${p.slug} [${p.layer}/${p.domain}]`);
  }
  console.log();

  // 5. Interactions — ~180 spread over 7 days
  console.log("📡 Generando interactions demo...");

  // Weight distribution per day: more recent = more traffic
  const dayWeights = [30, 28, 25, 22, 18, 15, 12]; // day 0 (today) to day 6
  const totalTarget = 180;
  const weightSum = dayWeights.reduce((a, b) => a + b, 0);

  // Action distribution targets (approximate)
  const actionWeights = { BLOCK: 15, REDACT: 25, WARN: 20, LOG: 40 };

  // Build weighted scenario lists: scenarios with a `weight` field are repeated
  // proportionally so they appear more often when picked randomly.
  function buildWeightedList(scenarios) {
    const result = [];
    for (const s of scenarios) {
      const w = s.weight ?? 1;
      for (let i = 0; i < w; i++) result.push(s);
    }
    return result;
  }

  const scenariosByAction = {
    BLOCK: buildWeightedList(SCENARIOS.filter((s) => s.action === "BLOCK")),
    REDACT: buildWeightedList(SCENARIOS.filter((s) => s.action === "REDACT")),
    WARN: buildWeightedList(SCENARIOS.filter((s) => s.action === "WARN")),
    LOG: buildWeightedList(SCENARIOS.filter((s) => s.action === "LOG")),
  };

  let count = 0;
  for (let dayIdx = 0; dayIdx < 7; dayIdx++) {
    const countForDay = Math.round((dayWeights[dayIdx] / weightSum) * totalTarget);
    for (let i = 0; i < countForDay; i++) {
      // Pick action by weight
      const r = Math.random() * 100;
      let action;
      if (r < actionWeights.BLOCK) action = "BLOCK";
      else if (r < actionWeights.BLOCK + actionWeights.REDACT) action = "REDACT";
      else if (r < actionWeights.BLOCK + actionWeights.REDACT + actionWeights.WARN) action = "WARN";
      else action = "LOG";

      const scenario = pick(scenariosByAction[action]);
      const id = uuid();
      const traceId = `trace-${id.slice(0, 8)}`;
      const latencyMs = randomInt(scenario.latency[0], scenario.latency[1]);
      // Add upstream latency for non-blocked requests
      const upstreamMs = action !== "BLOCK" ? randomInt(80, 300) : null;
      const totalMs = upstreamMs ? latencyMs + upstreamMs : latencyMs;

      // Timestamp: random within the day, slightly clustered in business hours
      const createdAt = daysAgo(dayIdx, randomInt(0, 23));
      createdAt.setMinutes(randomInt(0, 59));
      createdAt.setSeconds(randomInt(0, 59));

      // policy_hits: inject real IDs
      const hits = scenario.policyHits.map((h) => ({
        layer: h.layer,
        policy_id: policyIds[h.slug] ?? uuid(),
        slug: h.slug,
        action,
      }));

      const latencyByLayer =
        action !== "BLOCK"
          ? JSON.stringify({ regex: randomInt(3, 12), pattern: randomInt(2, 8), upstream: upstreamMs })
          : JSON.stringify({ regex: randomInt(3, 12), pattern: randomInt(2, 8) });

      await db.query(
        `INSERT INTO interactions
           (id, trace_id, org_id, request_model, prompt, action, reason,
            policy_hits, latency_total_ms, latency_by_layer, upstream_status, created_at)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10::jsonb,$11,$12)`,
        [
          id, traceId, ORG_ID,
          pick(["claude-sonnet-4-5", "claude-haiku-4-5", "claude-opus-4-7"]),
          scenario.promptTemplate,
          action,
          scenario.reason,
          JSON.stringify(hits),
          totalMs,
          latencyByLayer,
          upstreamMs ? 200 : null,
          createdAt.toISOString(),
        ],
      );
      count++;
    }
  }
  console.log(`   ✓ ${count} interactions creadas\n`);

  // 6. Rule suggestions
  console.log("💡 Insertando sugerencias del AI Suggestor...");
  for (const s of RULE_SUGGESTIONS) {
    const id = uuid();
    const decidedAt = ["accepted", "rejected"].includes(s.status) ? daysAgo(1).toISOString() : null;
    const acceptedPolicyId = null; // policy created separately when accepted; null is valid

    await db.query(
      `INSERT INTO rule_suggestions
         (id, org_id, proposed_slug, proposed_domain, proposed_layer,
          proposed_rule, proposed_pattern, proposed_match_config, proposed_action,
          proposed_severity, match_count, examples, source_hint, status,
          reject_reason, accepted_policy_id, created_at, decided_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12::jsonb,$13,$14,$15,$16,NOW(),$17)`,
      [
        id, ORG_ID, s.proposedSlug, s.proposedDomain, s.proposedLayer,
        s.proposedRule, s.proposedPattern ?? null, null,
        s.proposedAction, s.proposedSeverity, s.matchCount,
        JSON.stringify(s.examples),
        s.sourceHint ?? null, s.status,
        s.rejectReason ?? null, acceptedPolicyId,
        decidedAt,
      ],
    );
    console.log(`   ✓ ${s.proposedSlug} [${s.status}]`);
  }

  const blockCount = SCENARIOS.filter((s) => s.action === "BLOCK").length;
  const warnCount = SCENARIOS.filter((s) => s.action === "WARN").length;
  const redactCount = SCENARIOS.filter((s) => s.action === "REDACT").length;
  const logCount = SCENARIOS.filter((s) => s.action === "LOG").length;

  console.log("\n✅ Seed completo.");
  console.log(`   • 1 org (demo / Acme Corp)`);
  console.log(`   • 1 member admin (admin@acme.com)`);
  console.log(`   • ${POLICIES.length} políticas (regex: ${POLICIES.filter(p => p.layer === "regex").length}, pattern: ${POLICIES.filter(p => p.layer === "pattern").length}, nl: ${POLICIES.filter(p => p.layer === "nl").length})`);
  console.log(`   • ${count} interactions (7 días) — ${blockCount} plantillas BLOCK, ${warnCount} WARN, ${redactCount} REDACT, ${logCount} LOG`);
  console.log(`   • ${RULE_SUGGESTIONS.length} sugerencias\n`);

  await pool.end();
}

async function seedPoliciesOnly(orgId) {
  console.log(`🌱 Tranquera — sembrando solo policies en org "${orgId}"...\n`);

  const orgRow = await db.query(`SELECT id FROM organizations WHERE id = $1`, [orgId]);
  if (orgRow.rowCount === 0) {
    throw new Error(`org "${orgId}" no existe. Logueate primero o pasá un --org-id válido.`);
  }

  console.log("🗑️  Borrando policies y rule_suggestions previas de la org...");
  await db.query(`DELETE FROM rule_suggestions WHERE org_id = $1`, [orgId]);
  await db.query(`DELETE FROM policies WHERE org_id = $1`, [orgId]);
  console.log("   ✓ ok\n");

  console.log("📋 Insertando políticas...");
  for (const p of POLICIES) {
    const id = uuid();
    const matchConfig = p.matchConfig ? JSON.stringify(p.matchConfig) : null;
    await db.query(
      `INSERT INTO policies
         (id, org_id, slug, domain, layer, rule, pattern, match_config,
          default_action, severity, source, is_active, created_at, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12,NOW(),NOW())`,
      [
        id, orgId, p.slug, p.domain, p.layer, p.rule,
        p.pattern ?? null, matchConfig,
        p.defaultAction, p.severity, "seed", true,
      ],
    );
    console.log(`   ✓ ${p.slug} [${p.layer}/${p.domain}]`);
  }

  console.log(`\n✅ Listo. ${POLICIES.length} policies insertadas en "${orgId}".`);
  await pool.end();
}

const entrypoint = CLI.policiesOnly ? seedPoliciesOnly(ORG_ID) : main();
entrypoint.catch((err) => {
  console.error("❌ Seed falló:", err);
  pool.end();
  process.exit(1);
});
