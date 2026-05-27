"""Seed de producción para Tranquera.

Datos incluidos
───────────────
  Policies (25)
    - credentials  (regex)  : API keys, tokens, claves privadas, connection strings
    - pii          (regex)  : tarjetas de crédito, emails masivos, RUT, DNI, teléfonos
    - pii          (nl)     : registros de salud, datos financieros personales
    - code         (regex)  : credenciales hardcodeadas, bypasses de seguridad
    - code         (nl)     : código sin tests, sin manejo de errores
    - business_policy (nl)  : roadmap, precios, comparación con competidores,
                              objetivos corporativos, criterios de implementación
    - internal_paths (pattern): archivos .env/.pem/.key, configuración de infra

  Interactions (25)
    - 8  LOG   : uso normal, pasa sin fricción
    - 6  WARN  : política de negocio rozada, pasa con aviso al admin
    - 6  REDACT: PII/credenciales encontradas y enmascaradas, el request continúa
    - 5  BLOCK : credenciales críticas o violaciones graves, request cortado

  RuleSuggestions (6)
    - 3 pending  : propuestas nuevas del AI Suggestor en revisión
    - 1 accepted : promovida a policy
    - 2 rejected : descartadas con motivo

Ejecución
─────────
    cd interceptor
    python scripts/seed_prod.py [--org <org_id>]    # default: demo

Idempotencia
────────────
  - Organization    : upsert por id
  - Member          : upsert por (org_id, email)
  - Policy          : upsert por (org_id, slug)   — sobreescribe todos los campos
  - Interaction     : INSERT IGNORE por trace_id  — nunca duplica eventos
  - RuleSuggestion  : INSERT IGNORE por (org_id, proposed_slug)
"""

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import null, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Allow running as `python scripts/seed_prod.py` from interceptor/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import async_session_maker, engine  # noqa: E402
from app.enums import Action, PolicyDomain, PolicyLayer, PolicySource, Severity  # noqa: E402
from app.models import Interaction, Policy  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ago(days: float = 0, hours: float = 0) -> datetime:
    """Return a naive UTC datetime for Postgres timestamp columns."""
    return (datetime.now(tz=UTC) - timedelta(days=days, hours=hours)).replace(tzinfo=None)


def _v(enum_val) -> str:
    """Return the string value of an enum (or the string itself)."""
    return enum_val.value if hasattr(enum_val, "value") else enum_val


def _match_config(value):
    """Use SQL NULL, not JSON null, so policies_match_config_obj passes."""
    return value if value is not None else null()


# ---------------------------------------------------------------------------
# Org + Member
# ---------------------------------------------------------------------------

ORG_ROW = {
    "id": "demo",
    "name": "Acme Corp (demo)",
    "email_domain": "acme.com",
    "upstream_api_key_ref": "env:ANTHROPIC_API_KEY",
    "created_at": _ago(days=60),
}

MEMBER_ROW = {
    "id": str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
    "org_id": "demo",
    "email": "admin@acme.com",
    "role": "admin",
    "created_at": _ago(days=60),
}

# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

POLICIES: list[dict] = [
    # ── credentials / regex ─────────────────────────────────────────────────
    {
        "slug": "aws-access-key",
        "domain": PolicyDomain.credentials,
        "layer": PolicyLayer.regex,
        "rule": "AWS Access Key ID expuesta en un prompt",
        "pattern": r"AKIA[0-9A-Z]{16}",
        "default_action": Action.BLOCK,
        "severity": Severity.high,
    },
    {
        "slug": "github-token",
        "domain": PolicyDomain.credentials,
        "layer": PolicyLayer.regex,
        "rule": "GitHub Personal Access Token (classic o fine-grained)",
        "pattern": r"gh[pousr]_[A-Za-z0-9]{36,}",
        "default_action": Action.BLOCK,
        "severity": Severity.high,
    },
    {
        "slug": "pem-private-key",
        "domain": PolicyDomain.credentials,
        "layer": PolicyLayer.regex,
        "rule": "Clave privada PEM en texto plano",
        "pattern": r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----",
        "default_action": Action.BLOCK,
        "severity": Severity.high,
    },
    {
        "slug": "anthropic-api-key",
        "domain": PolicyDomain.credentials,
        "layer": PolicyLayer.regex,
        "rule": "Anthropic API key compartida en el prompt",
        "pattern": r"sk-ant-[A-Za-z0-9_\-]{20,}",
        "default_action": Action.BLOCK,
        "severity": Severity.high,
    },
    {
        "slug": "openai-api-key",
        "domain": PolicyDomain.credentials,
        "layer": PolicyLayer.regex,
        "rule": "OpenAI API key compartida en el prompt",
        "pattern": r"sk-[A-Za-z0-9]{48}",
        "default_action": Action.BLOCK,
        "severity": Severity.high,
    },
    {
        "slug": "db-connection-string",
        "domain": PolicyDomain.credentials,
        "layer": PolicyLayer.regex,
        "rule": "Connection string de base de datos con credenciales embebidas",
        "pattern": r"(postgres(?:ql)?|mysql|mongodb)://[^:]+:[^@]+@",
        "default_action": Action.REDACT,
        "severity": Severity.high,
    },
    {
        "slug": "hardcoded-secret-env",
        "domain": PolicyDomain.credentials,
        "layer": PolicyLayer.regex,
        "rule": "Variable de entorno con secreto hardcodeado (PASSWORD=, SECRET=, TOKEN=)",
        "pattern": r'(?i)(PASSWORD|SECRET|TOKEN|API_KEY)\s*=\s*["\']?[A-Za-z0-9_\-\.]{8,}["\']?',
        "default_action": Action.REDACT,
        "severity": Severity.medium,
    },
    # ── pii / regex ──────────────────────────────────────────────────────────
    {
        "slug": "credit-card-number",
        "domain": PolicyDomain.pii,
        "layer": PolicyLayer.regex,
        "rule": "Número de tarjeta de crédito/débito en el prompt",
        "pattern": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
        "default_action": Action.REDACT,
        "severity": Severity.high,
    },
    {
        "slug": "national-id-rut",
        "domain": PolicyDomain.pii,
        "layer": PolicyLayer.regex,
        "rule": "RUT chileno enviado a la API",
        "pattern": r"\b\d{7,8}-[\dkK]\b",
        "default_action": Action.REDACT,
        "severity": Severity.medium,
    },
    {
        "slug": "national-id-dni",
        "domain": PolicyDomain.pii,
        "layer": PolicyLayer.regex,
        "rule": "DNI argentino (8 dígitos seguidos) enviado a la API",
        "pattern": r"\b\d{8}\b",
        "default_action": Action.WARN,
        "severity": Severity.low,
    },
    {
        "slug": "iban-number",
        "domain": PolicyDomain.pii,
        "layer": PolicyLayer.regex,
        "rule": "Número de cuenta bancaria IBAN",
        "pattern": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b",
        "default_action": Action.REDACT,
        "severity": Severity.high,
    },
    {
        "slug": "phone-number-bulk",
        "domain": PolicyDomain.pii,
        "layer": PolicyLayer.regex,
        "rule": "Listado de números telefónicos (3 o más en el mismo mensaje)",
        "pattern": r"(?:(?:\+?\d[\d\s\-\(\)]{8,}){3,})",
        "default_action": Action.WARN,
        "severity": Severity.medium,
    },
    # ── pii / nl ─────────────────────────────────────────────────────────────
    {
        "slug": "pii-health-records",
        "domain": PolicyDomain.pii,
        "layer": PolicyLayer.nl,
        "rule": "Información médica o de salud de pacientes enviada a la API",
        "pattern": None,
        "default_action": Action.BLOCK,
        "severity": Severity.high,
    },
    {
        "slug": "pii-financial-personal",
        "domain": PolicyDomain.pii,
        "layer": PolicyLayer.nl,
        "rule": "Datos financieros personales de clientes (saldos, deudas, historial crediticio)",
        "pattern": None,
        "default_action": Action.REDACT,
        "severity": Severity.high,
    },
    # ── code / regex ─────────────────────────────────────────────────────────
    {
        "slug": "hardcoded-credentials-in-code",
        "domain": PolicyDomain.code,
        "layer": PolicyLayer.regex,
        "rule": "Credenciales hardcodeadas en código fuente compartido con la API",
        "pattern": r'(?i)(password|passwd|pwd|api_key|apikey|secret)\s*=\s*["\'][^"\']{6,}["\']',
        "default_action": Action.REDACT,
        "severity": Severity.high,
    },
    {
        "slug": "security-check-bypass",
        "domain": PolicyDomain.code,
        "layer": PolicyLayer.regex,
        "rule": "Comentario TODO/FIXME para eliminar validaciones de seguridad o autenticación",
        "pattern": r"(?i)#\s*(TODO|FIXME|HACK)\s*:.*?(remove|skip|bypass|disable)\s*(auth|security|check|validat)",
        "default_action": Action.WARN,
        "severity": Severity.medium,
    },
    # ── code / nl ────────────────────────────────────────────────────────────
    {
        "slug": "code-without-tests",
        "domain": PolicyDomain.code,
        "layer": PolicyLayer.nl,
        "rule": "Solicitud de implementación de funcionalidad crítica sin cobertura de tests",
        "pattern": None,
        "default_action": Action.WARN,
        "severity": Severity.medium,
    },
    {
        "slug": "code-without-error-handling",
        "domain": PolicyDomain.code,
        "layer": PolicyLayer.nl,
        "rule": "Solicitud de código que omite manejo de errores en operaciones de I/O o red",
        "pattern": None,
        "default_action": Action.WARN,
        "severity": Severity.low,
    },
    # ── business_policy / nl ─────────────────────────────────────────────────
    {
        "slug": "disclose-internal-roadmap",
        "domain": PolicyDomain.business_policy,
        "layer": PolicyLayer.nl,
        "rule": "Compartir roadmap de producto, planes de lanzamiento o funcionalidades no anunciadas",
        "pattern": None,
        "default_action": Action.BLOCK,
        "severity": Severity.high,
    },
    {
        "slug": "disclose-pricing-strategy",
        "domain": PolicyDomain.business_policy,
        "layer": PolicyLayer.nl,
        "rule": "Revelar estrategia de precios, descuentos o márgenes no públicos a terceros",
        "pattern": None,
        "default_action": Action.BLOCK,
        "severity": Severity.high,
    },
    {
        "slug": "competitor-direct-comparison",
        "domain": PolicyDomain.business_policy,
        "layer": PolicyLayer.nl,
        "rule": "Solicitar comparación directa de producto propio contra competidores con datos internos",
        "pattern": None,
        "default_action": Action.WARN,
        "severity": Severity.medium,
    },
    {
        "slug": "confidential-company-objectives",
        "domain": PolicyDomain.business_policy,
        "layer": PolicyLayer.nl,
        "rule": "Exposición de OKRs, metas estratégicas o KPIs confidenciales de la empresa",
        "pattern": None,
        "default_action": Action.WARN,
        "severity": Severity.high,
    },
    {
        "slug": "implementation-criteria-bypass",
        "domain": PolicyDomain.business_policy,
        "layer": PolicyLayer.nl,
        "rule": "Solicitud que contradice los criterios de implementación aprobados por arquitectura (ej. evadir code review, CI/CD o pair programming)",
        "pattern": None,
        "default_action": Action.WARN,
        "severity": Severity.medium,
    },
    # ── internal_paths / pattern ─────────────────────────────────────────────
    {
        "slug": "env-file-exposure",
        "domain": PolicyDomain.internal_paths,
        "layer": PolicyLayer.pattern,
        "rule": "Contenido de archivos .env, .pem, .key o .p12 enviado al modelo",
        "pattern": None,
        "match_config": {"extensions": [".env", ".pem", ".key", ".p12", ".pfx", ".cer"]},
        "default_action": Action.BLOCK,
        "severity": Severity.high,
    },
    {
        "slug": "infrastructure-config",
        "domain": PolicyDomain.internal_paths,
        "layer": PolicyLayer.pattern,
        "rule": "Archivos de configuración de infraestructura (Terraform, Kubernetes, Docker secrets) con posibles credenciales",
        "pattern": None,
        "match_config": {
            "paths": ["terraform/", "k8s/", "helm/", ".kube/"],
            "filenames": ["docker-compose.prod.yml", "secrets.yaml", "values-prod.yaml"],
        },
        "default_action": Action.WARN,
        "severity": Severity.medium,
    },
]

# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

_MODEL = "claude-sonnet-4-6"

INTERACTIONS: list[dict] = [
    # ── LOG — uso normal ─────────────────────────────────────────────────────
    {
        "trace_id": "tr-log-001",
        "request_model": _MODEL,
        "prompt": "Escribí una función en Python que calcule el factorial de un número usando recursión.",
        "action": Action.LOG,
        "reason": "No se detectaron políticas aplicables. Request permitido.",
        "policy_hits": [],
        "latency_total_ms": 42,
        "latency_by_layer": {"regex": 2, "pattern": 1, "haiku": 0, "upstream": 39},
        "upstream_status": 200,
        "created_at": _ago(days=28, hours=3),
    },
    {
        "trace_id": "tr-log-002",
        "request_model": _MODEL,
        "prompt": "Refactorizá este componente React para extraer la lógica de fetch a un custom hook.",
        "action": Action.LOG,
        "reason": "No se detectaron políticas aplicables. Request permitido.",
        "policy_hits": [],
        "latency_total_ms": 38,
        "latency_by_layer": {"regex": 2, "pattern": 1, "haiku": 0, "upstream": 35},
        "upstream_status": 200,
        "created_at": _ago(days=25, hours=7),
    },
    {
        "trace_id": "tr-log-003",
        "request_model": _MODEL,
        "prompt": "Explicame el patrón Observer en TypeScript con un ejemplo de Event Emitter.",
        "action": Action.LOG,
        "reason": "No se detectaron políticas aplicables. Request permitido.",
        "policy_hits": [],
        "latency_total_ms": 55,
        "latency_by_layer": {"regex": 3, "pattern": 1, "haiku": 0, "upstream": 51},
        "upstream_status": 200,
        "created_at": _ago(days=22, hours=11),
    },
    {
        "trace_id": "tr-log-004",
        "request_model": _MODEL,
        "prompt": "Cómo configuro un índice GIN en PostgreSQL para búsqueda full-text en español?",
        "action": Action.LOG,
        "reason": "No se detectaron políticas aplicables. Request permitido.",
        "policy_hits": [],
        "latency_total_ms": 47,
        "latency_by_layer": {"regex": 2, "pattern": 1, "haiku": 0, "upstream": 44},
        "upstream_status": 200,
        "created_at": _ago(days=19, hours=2),
    },
    {
        "trace_id": "tr-log-005",
        "request_model": _MODEL,
        "prompt": "Generá un Dockerfile multi-stage para una app Node.js con build de TypeScript.",
        "action": Action.LOG,
        "reason": "No se detectaron políticas aplicables. Request permitido.",
        "policy_hits": [],
        "latency_total_ms": 61,
        "latency_by_layer": {"regex": 3, "pattern": 2, "haiku": 0, "upstream": 56},
        "upstream_status": 200,
        "created_at": _ago(days=15, hours=9),
    },
    {
        "trace_id": "tr-log-006",
        "request_model": _MODEL,
        "prompt": "Cómo implemento paginación cursor-based en una API GraphQL con Relay spec?",
        "action": Action.LOG,
        "reason": "No se detectaron políticas aplicables. Request permitido.",
        "policy_hits": [],
        "latency_total_ms": 44,
        "latency_by_layer": {"regex": 2, "pattern": 1, "haiku": 0, "upstream": 41},
        "upstream_status": 200,
        "created_at": _ago(days=10, hours=14),
    },
    {
        "trace_id": "tr-log-007",
        "request_model": _MODEL,
        "prompt": "Necesito un script de bash que haga backup de una carpeta y la suba a S3 usando la AWS CLI.",
        "action": Action.LOG,
        "reason": "No se detectaron políticas aplicables. Request permitido.",
        "policy_hits": [],
        "latency_total_ms": 39,
        "latency_by_layer": {"regex": 3, "pattern": 1, "haiku": 0, "upstream": 35},
        "upstream_status": 200,
        "created_at": _ago(days=6, hours=5),
    },
    {
        "trace_id": "tr-log-008",
        "request_model": _MODEL,
        "prompt": "Escribí tests unitarios para esta función de validación de formulario en Jest.",
        "action": Action.LOG,
        "reason": "No se detectaron políticas aplicables. Request permitido.",
        "policy_hits": [],
        "latency_total_ms": 52,
        "latency_by_layer": {"regex": 2, "pattern": 1, "haiku": 0, "upstream": 49},
        "upstream_status": 200,
        "created_at": _ago(days=2, hours=3),
    },
    # ── WARN — política rozada, request pasa ─────────────────────────────────
    {
        "trace_id": "tr-warn-001",
        "request_model": _MODEL,
        "prompt": "Ayudame a armar una presentación comparando nuestros precios con los de la competencia para el cliente Enterprise.",
        "action": Action.WARN,
        "reason": "Política 'competitor-direct-comparison': solicitud con datos internos de precios hacia comparación competitiva.",
        "policy_hits": [{"layer": "nl", "slug": "competitor-direct-comparison", "score": 0.87}],
        "latency_total_ms": 198,
        "latency_by_layer": {"regex": 4, "pattern": 2, "haiku": 142, "upstream": 50},
        "upstream_status": 200,
        "created_at": _ago(days=27, hours=6),
    },
    {
        "trace_id": "tr-warn-002",
        "request_model": _MODEL,
        "prompt": "Podés resumir los OKRs del equipo de producto para Q3 y Q4 de este año?",
        "action": Action.WARN,
        "reason": "Política 'confidential-company-objectives': exposición de objetivos estratégicos internos.",
        "policy_hits": [{"layer": "nl", "slug": "confidential-company-objectives", "score": 0.91}],
        "latency_total_ms": 187,
        "latency_by_layer": {"regex": 3, "pattern": 1, "haiku": 138, "upstream": 45},
        "upstream_status": 200,
        "created_at": _ago(days=21, hours=10),
    },
    {
        "trace_id": "tr-warn-003",
        "request_model": _MODEL,
        "prompt": "Implementá este endpoint sin tests, el deadline es mañana y no tenemos tiempo.",
        "action": Action.WARN,
        "reason": "Política 'code-without-tests': solicitud de implementación crítica sin cobertura de tests.",
        "policy_hits": [{"layer": "nl", "slug": "code-without-tests", "score": 0.83}],
        "latency_total_ms": 175,
        "latency_by_layer": {"regex": 3, "pattern": 1, "haiku": 131, "upstream": 40},
        "upstream_status": 200,
        "created_at": _ago(days=16, hours=8),
    },
    {
        "trace_id": "tr-warn-004",
        "request_model": _MODEL,
        "prompt": "# TODO: remove auth check before demo\ndef get_user_data(id): return db.query(id)",
        "action": Action.WARN,
        "reason": "Política 'security-check-bypass': comentario para deshabilitar validación de autenticación.",
        "policy_hits": [{"layer": "regex", "slug": "security-check-bypass", "score": None}],
        "latency_total_ms": 22,
        "latency_by_layer": {"regex": 18, "pattern": 2, "haiku": 0, "upstream": 2},
        "upstream_status": 200,
        "created_at": _ago(days=12, hours=4),
    },
    {
        "trace_id": "tr-warn-005",
        "request_model": _MODEL,
        "prompt": "Explicame los criterios de implementación del equipo. Necesito saber cómo evitar el proceso de code review para este hotfix.",
        "action": Action.WARN,
        "reason": "Política 'implementation-criteria-bypass': intención de evadir proceso de code review.",
        "policy_hits": [{"layer": "nl", "slug": "implementation-criteria-bypass", "score": 0.89}],
        "latency_total_ms": 192,
        "latency_by_layer": {"regex": 3, "pattern": 1, "haiku": 145, "upstream": 43},
        "upstream_status": 200,
        "created_at": _ago(days=8, hours=15),
    },
    {
        "trace_id": "tr-warn-006",
        "request_model": _MODEL,
        "prompt": "El archivo terraform/prod/main.tf tiene las variables de RDS, podés revisarlo y decirme si está bien configurado?",
        "action": Action.WARN,
        "reason": "Política 'infrastructure-config': archivo de infraestructura de producción con posibles credenciales.",
        "policy_hits": [{"layer": "pattern", "slug": "infrastructure-config", "score": None}],
        "latency_total_ms": 31,
        "latency_by_layer": {"regex": 4, "pattern": 24, "haiku": 0, "upstream": 3},
        "upstream_status": 200,
        "created_at": _ago(days=3, hours=11),
    },
    # ── REDACT — PII/creds enmascaradas, request continúa ───────────────────
    {
        "trace_id": "tr-redact-001",
        "request_model": _MODEL,
        "prompt": "Cómo conecto a la base de datos de producción? La URL es postgresql://admin:[REDACTED]@prod.db.acme.com:5432/main",
        "action": Action.REDACT,
        "reason": "Política 'db-connection-string': credenciales de base de datos enmascaradas.",
        "policy_hits": [{"layer": "regex", "slug": "db-connection-string", "score": None}],
        "latency_total_ms": 19,
        "latency_by_layer": {"regex": 15, "pattern": 2, "haiku": 0, "upstream": 2},
        "upstream_status": 200,
        "created_at": _ago(days=26, hours=4),
    },
    {
        "trace_id": "tr-redact-002",
        "request_model": _MODEL,
        "prompt": "El usuario Juan García (DNI [REDACTED], email juan.garcia@cliente.com) necesita resetear su contraseña. Cómo proceso este caso?",
        "action": Action.REDACT,
        "reason": "Política 'national-id-dni': DNI argentino detectado y enmascarado.",
        "policy_hits": [{"layer": "regex", "slug": "national-id-dni", "score": None}],
        "latency_total_ms": 24,
        "latency_by_layer": {"regex": 19, "pattern": 2, "haiku": 0, "upstream": 3},
        "upstream_status": 200,
        "created_at": _ago(days=20, hours=9),
    },
    {
        "trace_id": "tr-redact-003",
        "request_model": _MODEL,
        "prompt": "Procesá este pago: tarjeta [REDACTED], vencimiento 12/26, CVV [REDACTED]. Monto: $150.000.",
        "action": Action.REDACT,
        "reason": "Política 'credit-card-number': número de tarjeta de crédito enmascarado.",
        "policy_hits": [{"layer": "regex", "slug": "credit-card-number", "score": None}],
        "latency_total_ms": 17,
        "latency_by_layer": {"regex": 13, "pattern": 2, "haiku": 0, "upstream": 2},
        "upstream_status": 200,
        "created_at": _ago(days=17, hours=13),
    },
    {
        "trace_id": "tr-redact-004",
        "request_model": _MODEL,
        "prompt": "const config = { apiKey: [REDACTED], endpoint: 'https://api.prod.acme.com' }; cómo uso esto en el cliente?",
        "action": Action.REDACT,
        "reason": "Política 'hardcoded-credentials-in-code': API key hardcodeada enmascarada en código fuente.",
        "policy_hits": [{"layer": "regex", "slug": "hardcoded-credentials-in-code", "score": None}],
        "latency_total_ms": 21,
        "latency_by_layer": {"regex": 17, "pattern": 2, "haiku": 0, "upstream": 2},
        "upstream_status": 200,
        "created_at": _ago(days=13, hours=7),
    },
    {
        "trace_id": "tr-redact-005",
        "request_model": _MODEL,
        "prompt": "RUT del cliente: [REDACTED]. Verificá si está habilitado para operar en el sistema.",
        "action": Action.REDACT,
        "reason": "Política 'national-id-rut': RUT chileno detectado y enmascarado.",
        "policy_hits": [{"layer": "regex", "slug": "national-id-rut", "score": None}],
        "latency_total_ms": 16,
        "latency_by_layer": {"regex": 12, "pattern": 2, "haiku": 0, "upstream": 2},
        "upstream_status": 200,
        "created_at": _ago(days=9, hours=3),
    },
    {
        "trace_id": "tr-redact-006",
        "request_model": _MODEL,
        "prompt": "Los datos financieros del cliente María López (cuenta [REDACTED], saldo disponible $[REDACTED]) necesitan ser migrados al nuevo sistema.",
        "action": Action.REDACT,
        "reason": "Política 'pii-financial-personal': datos financieros personales identificados y enmascarados.",
        "policy_hits": [{"layer": "nl", "slug": "pii-financial-personal", "score": 0.92}],
        "latency_total_ms": 204,
        "latency_by_layer": {"regex": 5, "pattern": 2, "haiku": 155, "upstream": 42},
        "upstream_status": 200,
        "created_at": _ago(days=4, hours=16),
    },
    # ── BLOCK — request cortado ──────────────────────────────────────────────
    {
        "trace_id": "tr-block-001",
        "request_model": _MODEL,
        "prompt": "Mi AWS Access Key es FAKE_AWS_ACCESS_KEY_ID_INVALID. Cómo la uso para subir archivos a S3?",
        "action": Action.BLOCK,
        "reason": "Política 'aws-access-key': AWS Access Key ID detectada. Request bloqueado para evitar exfiltración.",
        "policy_hits": [{"layer": "regex", "slug": "aws-access-key", "score": None}],
        "latency_total_ms": 14,
        "latency_by_layer": {"regex": 11, "pattern": 2, "haiku": 0, "upstream": 0},
        "upstream_status": None,
        "created_at": _ago(days=24, hours=2),
    },
    {
        "trace_id": "tr-block-002",
        "request_model": _MODEL,
        "prompt": "Token de GitHub: fake_github_pat_invalid. Ayudame a listar mis repositorios privados.",
        "action": Action.BLOCK,
        "reason": "Política 'github-token': GitHub Personal Access Token detectado. Request bloqueado.",
        "policy_hits": [{"layer": "regex", "slug": "github-token", "score": None}],
        "latency_total_ms": 12,
        "latency_by_layer": {"regex": 9, "pattern": 2, "haiku": 0, "upstream": 0},
        "upstream_status": None,
        "created_at": _ago(days=18, hours=17),
    },
    {
        "trace_id": "tr-block-003",
        "request_model": _MODEL,
        "prompt": "La key de Anthropic es sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxx. Cómo la configuro en el proyecto?",
        "action": Action.BLOCK,
        "reason": "Política 'anthropic-api-key': Anthropic API key detectada. Request bloqueado.",
        "policy_hits": [{"layer": "regex", "slug": "anthropic-api-key", "score": None}],
        "latency_total_ms": 11,
        "latency_by_layer": {"regex": 8, "pattern": 2, "haiku": 0, "upstream": 0},
        "upstream_status": None,
        "created_at": _ago(days=11, hours=8),
    },
    {
        "trace_id": "tr-block-004",
        "request_model": _MODEL,
        "prompt": "El paciente Roberto Silva tiene diabetes tipo 2 y presión alta. Generame un plan de medicación.",
        "action": Action.BLOCK,
        "reason": "Política 'pii-health-records': información médica sensible de paciente. Request bloqueado.",
        "policy_hits": [{"layer": "nl", "slug": "pii-health-records", "score": 0.96}],
        "latency_total_ms": 189,
        "latency_by_layer": {"regex": 4, "pattern": 2, "haiku": 183, "upstream": 0},
        "upstream_status": None,
        "created_at": _ago(days=7, hours=12),
    },
    {
        "trace_id": "tr-block-005",
        "request_model": _MODEL,
        "prompt": "Necesito que redactes el anuncio del lanzamiento de nuestra feature de pagos para Q2, con las fechas exactas de release.",
        "action": Action.BLOCK,
        "reason": "Política 'disclose-internal-roadmap': exposición de roadmap de producto no anunciado. Request bloqueado.",
        "policy_hits": [{"layer": "nl", "slug": "disclose-internal-roadmap", "score": 0.93}],
        "latency_total_ms": 194,
        "latency_by_layer": {"regex": 3, "pattern": 1, "haiku": 188, "upstream": 0},
        "upstream_status": None,
        "created_at": _ago(days=1, hours=6),
    },
]

# ---------------------------------------------------------------------------
# Rule Suggestions
# ---------------------------------------------------------------------------

SUGGESTIONS: list[dict] = [
    {
        "id": str(uuid.UUID("10000000-0000-0000-0000-000000000001")),
        "proposed_slug": "salary-information",
        "proposed_domain": "business_policy",
        "proposed_layer": "nl",
        "proposed_rule": "Información salarial, bandas de compensación o datos de equity de empleados compartidos en prompts",
        "proposed_pattern": None,
        "proposed_match_config": None,
        "proposed_action": "BLOCK",
        "proposed_severity": "high",
        "match_count": 3,
        "examples": [
            {"traceId": "tr-log-006", "promptRedacted": "Cuál es la banda salarial para un Senior Engineer?", "createdAt": _ago(days=10, hours=14).isoformat()},
        ],
        "source_hint": None,
        "status": "pending",
        "reject_reason": None,
        "accepted_policy_id": None,
        "created_at": _ago(days=5, hours=2),
        "decided_at": None,
    },
    {
        "id": str(uuid.UUID("10000000-0000-0000-0000-000000000002")),
        "proposed_slug": "employee-personal-data",
        "proposed_domain": "pii",
        "proposed_layer": "nl",
        "proposed_rule": "Datos personales de empleados (legajo, CUIL, domicilio) enviados a la API",
        "proposed_pattern": None,
        "proposed_match_config": None,
        "proposed_action": "REDACT",
        "proposed_severity": "high",
        "match_count": 5,
        "examples": [
            {"traceId": "tr-redact-002", "promptRedacted": "El empleado [REDACTED] con CUIL [REDACTED] necesita...", "createdAt": _ago(days=20, hours=9).isoformat()},
        ],
        "source_hint": None,
        "status": "pending",
        "reject_reason": None,
        "accepted_policy_id": None,
        "created_at": _ago(days=3, hours=7),
        "decided_at": None,
    },
    {
        "id": str(uuid.UUID("10000000-0000-0000-0000-000000000003")),
        "proposed_slug": "confidential-project-names",
        "proposed_domain": "business_policy",
        "proposed_layer": "nl",
        "proposed_rule": "Nombres en clave de proyectos confidenciales (Proyecto Cóndor, Proyecto Atlas) mencionados en prompts",
        "proposed_pattern": None,
        "proposed_match_config": None,
        "proposed_action": "WARN",
        "proposed_severity": "medium",
        "match_count": 2,
        "examples": [],
        "source_hint": None,
        "status": "pending",
        "reject_reason": None,
        "accepted_policy_id": None,
        "created_at": _ago(days=1, hours=15),
        "decided_at": None,
    },
    {
        "id": str(uuid.UUID("10000000-0000-0000-0000-000000000004")),
        "proposed_slug": "aws-lambda-arn",
        "proposed_domain": "internal_paths",
        "proposed_layer": "regex",
        "proposed_rule": "ARN de función Lambda de producción expuesto en el prompt",
        "proposed_pattern": r"arn:aws:lambda:[a-z0-9\-]+:\d{12}:function:[A-Za-z0-9_\-:]+",
        "proposed_match_config": None,
        "proposed_action": "WARN",
        "proposed_severity": "medium",
        "match_count": 4,
        "examples": [
            {"traceId": "tr-log-007", "promptRedacted": "El ARN de la función es arn:aws:lambda:us-east-1:...", "createdAt": _ago(days=6, hours=5).isoformat()},
        ],
        "source_hint": None,
        "status": "accepted",
        "reject_reason": None,
        "accepted_policy_id": None,  # se actualiza si se promueve a policy real
        "created_at": _ago(days=9, hours=3),
        "decided_at": _ago(days=7, hours=10),
    },
    {
        "id": str(uuid.UUID("10000000-0000-0000-0000-000000000005")),
        "proposed_slug": "any-number-sequence",
        "proposed_domain": "pii",
        "proposed_layer": "regex",
        "proposed_rule": "Detectar cualquier secuencia de 8 dígitos como posible DNI",
        "proposed_pattern": r"\b\d{8}\b",
        "proposed_match_config": None,
        "proposed_action": "BLOCK",
        "proposed_severity": "high",
        "match_count": 47,
        "examples": [],
        "source_hint": None,
        "status": "rejected",
        "reject_reason": "Demasiados falsos positivos: matchea números de versión, fechas (20240101) y otros datos sin relación con DNI.",
        "accepted_policy_id": None,
        "created_at": _ago(days=14, hours=5),
        "decided_at": _ago(days=13, hours=9),
    },
    {
        "id": str(uuid.UUID("10000000-0000-0000-0000-000000000006")),
        "proposed_slug": "external-api-credentials-in-prompt",
        "proposed_domain": "credentials",
        "proposed_layer": "nl",
        "proposed_rule": "Credenciales de APIs externas (Stripe, Twilio, SendGrid) compartidas en el contexto del prompt",
        "proposed_pattern": None,
        "proposed_match_config": None,
        "proposed_action": "BLOCK",
        "proposed_severity": "high",
        "match_count": 2,
        "examples": [],
        "source_hint": None,
        "status": "rejected",
        "reject_reason": "El patrón regex de 'hardcoded-secret-env' ya cubre estos casos con menor overhead. Duplicado innecesario.",
        "accepted_policy_id": None,
        "created_at": _ago(days=6, hours=11),
        "decided_at": _ago(days=5, hours=8),
    },
]

# ---------------------------------------------------------------------------
# Seed runner
# ---------------------------------------------------------------------------

async def seed_org(session, org_id: str) -> None:
    org_row = {**ORG_ROW, "id": org_id}
    if org_id != "demo":
        org_row["name"] = f"Org {org_id} (seed)"
        org_row["email_domain"] = None

    await session.execute(
        text("""
            INSERT INTO organizations (id, name, email_domain, upstream_api_key_ref, created_at)
            VALUES (:id, :name, :email_domain, :upstream_api_key_ref, :created_at)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                upstream_api_key_ref = EXCLUDED.upstream_api_key_ref
        """),
        org_row,
    )


async def seed_member(session, org_id: str) -> None:
    row = {**MEMBER_ROW, "org_id": org_id}
    await session.execute(
        text("""
            INSERT INTO members (id, org_id, email, role, created_at)
            VALUES (:id, :org_id, :email, :role, :created_at)
            ON CONFLICT (org_id, email) DO NOTHING
        """),
        row,
    )


async def seed_policies(session, org_id: str) -> int:
    count = 0
    for row in POLICIES:
        stmt = (
            pg_insert(Policy.__table__)
            .values(
                id=uuid.uuid5(uuid.NAMESPACE_URL, f"tranquera:{org_id}:policy:{row['slug']}"),
                org_id=org_id,
                source=PolicySource.seed.value,
                is_active=True,
                match_config=_match_config(row.get("match_config")),
                **{
                    k: (_v(v) if k not in ("match_config",) else v)
                    for k, v in row.items()
                    if k != "match_config"
                },
            )
            .on_conflict_do_update(
                index_elements=["org_id", "slug"],
                set_={
                    "domain": _v(row["domain"]),
                    "layer": _v(row["layer"]),
                    "rule": row["rule"],
                    "pattern": row.get("pattern"),
                    "match_config": _match_config(row.get("match_config")),
                    "default_action": _v(row["default_action"]),
                    "severity": _v(row["severity"]),
                    "is_active": True,
                },
            )
        )
        await session.execute(stmt)
        count += 1
    return count


async def seed_interactions(session, org_id: str) -> int:
    count = 0
    for row in INTERACTIONS:
        stmt = (
            pg_insert(Interaction.__table__)
            .values(
                id=str(uuid.uuid4()),
                org_id=org_id,
                trace_id=f"{org_id}:{row['trace_id']}",
                request_model=row["request_model"],
                prompt=row["prompt"],
                action=_v(row["action"]),
                reason=row["reason"],
                policy_hits=row["policy_hits"],
                latency_total_ms=row["latency_total_ms"],
                latency_by_layer=row["latency_by_layer"],
                upstream_status=row.get("upstream_status"),
                created_at=row["created_at"],
            )
            .on_conflict_do_nothing(index_elements=["trace_id"])
        )
        await session.execute(stmt)
        count += 1
    return count


async def seed_suggestions(session, org_id: str) -> int:
    count = 0
    for row in SUGGESTIONS:
        await session.execute(
            text("""
                INSERT INTO rule_suggestions (
                    id, org_id, proposed_slug, proposed_domain, proposed_layer,
                    proposed_rule, proposed_pattern, proposed_match_config,
                    proposed_action, proposed_severity, match_count, examples,
                    source_hint, status, reject_reason, accepted_policy_id,
                    created_at, decided_at
                ) VALUES (
                    :id, :org_id, :proposed_slug,
                    CAST(:proposed_domain AS \"PolicyDomain\"),
                    CAST(:proposed_layer AS \"PolicyLayer\"),
                    :proposed_rule, :proposed_pattern,
                    CAST(:proposed_match_config AS jsonb),
                    CAST(:proposed_action AS \"Action\"),
                    CAST(:proposed_severity AS \"Severity\"),
                    :match_count, CAST(:examples AS jsonb),
                    :source_hint, CAST(:status AS \"SuggestionStatus\"), :reject_reason,
                    CAST(:accepted_policy_id AS uuid), :created_at, :decided_at
                )
                ON CONFLICT (id) DO NOTHING
            """),
            {
                **row,
                "org_id": org_id,
                "proposed_match_config": (
                    __import__("json").dumps(row["proposed_match_config"])
                    if row["proposed_match_config"]
                    else None
                ),
                "examples": __import__("json").dumps(row["examples"]),
            },
        )
        count += 1
    return count


async def main(org_id: str = "demo") -> None:
    async with async_session_maker() as session:
        await seed_org(session, org_id)
        await seed_member(session, org_id)
        n_policies = await seed_policies(session, org_id)
        n_interactions = await seed_interactions(session, org_id)
        n_suggestions = await seed_suggestions(session, org_id)
        await session.commit()

    await engine.dispose()
    print(f"✓ Seed completado para org_id={org_id!r}")
    print(f"  {n_policies} policies · {n_interactions} interactions · {n_suggestions} rule_suggestions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed de producción para Tranquera")
    parser.add_argument("--org", default="demo", help="org_id destino (default: demo)")
    args = parser.parse_args()
    asyncio.run(main(args.org))
