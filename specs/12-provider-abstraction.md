# 12 — Provider Abstraction / Multi-provider Core

> Evolución del interceptor: de **proxy Anthropic/Claude Code-specific** a una capa de enforcement con adapters por protocolo. El objetivo no es soportar todos los providers de una vez, sino aislar el contrato de Tranquera para sumar OpenAI-compatible, Pi, opencode, Codex y gateways sin reescribir la cascada.

---

## Estado actual

Parcial. Ya existen campos de metadata (`protocol`, `integration`, `upstream_provider`, `upstream_model`) y la ruta OpenAI-compatible de spec 13. Todavía no existe una capa formal `NormalizedRequest`/`ProtocolAdapter`/registry; la cascada sigue repartida entre rutas Anthropic y OpenAI-compatible. `/v1/responses` queda pendiente.

---

## Decisión corta

Tranquera mantiene una sola cascada de policy enforcement (`BLOCK · REDACT · WARN · LOG`) y agrega una frontera explícita de **protocol adapters**:

```text
harness/client → protocol adapter → normalized request → cascade → provider adapter → upstream
```

La cascada no debe saber si el request vino de Claude Code, opencode, Pi, Aider o Codex. Solo recibe texto normalizado, metadata de caller/org y una función para reconstruir la respuesta del protocolo original.

---

## Contexto

Hoy `interceptor/` está acoplado a Anthropic Messages API:

- `POST /cli/{token}/v1/messages`
- body `{ model, system?, messages, max_tokens, stream? }`
- headers `x-api-key`, `anthropic-version`
- BLOCK response con shape Anthropic JSON/SSE
- NL judge y AI Suggestor hardcodeados a Claude Haiku

Eso funciona muy bien para Claude Code, pero limita el producto. La investigación mostró que los próximos targets más útiles son:

1. **OpenAI-compatible API** — desbloquea opencode, Aider, Ollama, LM Studio, vLLM, OpenRouter y LiteLLM.
2. **Pi provider override / extension** — integración controlada con muchos providers.
3. **Codex Responses API** — estratégico para OpenAI Codex CLI, pero requiere otro wire protocol.
4. **Gemini CLI hooks** — alternativa no-proxy para enforcement previo/posterior al modelo.

---

## Goals

- Separar la cascada de seguridad del protocolo upstream.
- Soportar múltiples protocolos sin duplicar regex/NL/persistencia.
- Mantener compatibilidad con el flujo Claude Code actual.
- Definir un `NormalizedRequest` estable para policy evaluation.
- Definir `ProtocolAdapter` para parsear requests, aplicar redacciones y sintetizar BLOCK/WARN.
- Definir `ProviderAdapter` para forwardear a upstreams reales o gateways.
- Permitir que cada org configure provider/protocol por integración.
- Preparar el camino para usar LiteLLM como normalizador de providers cuando convenga.

## Non-Goals

- No soportar todos los providers en una sola PR.
- No traducir respuestas del modelo salvo en `BLOCK` sintético.
- No mover el admin ni la DB fuera del schema actual.
- No cambiar el modelo de políticas (`Policy`, `Interaction`) salvo campos mínimos de metadata.
- No resolver todavía SSO/SAML/SCIM para distribución corporativa.

---

## Contrato interno

### `NormalizedRequest`

```py
@dataclass
class NormalizedRequest:
    protocol: Literal["anthropic_messages", "openai_chat", "openai_responses"]
    integration: str              # claude-code, opencode, pi, aider, codex, custom
    org_id: str
    user_id: UUID | None
    trace_id: str
    request_model: str
    stream: bool
    texts: list[TextPart]         # todo texto evaluable por policies
    raw_body: dict
    raw_headers: dict[str, str]
    raw_query: str
```

```py
@dataclass
class TextPart:
    path: str                     # ej. messages[0].content[1].text
    role: str | None              # user, assistant, system, developer, tool
    text: str
```

### `ProtocolAdapter`

```py
class ProtocolAdapter(Protocol):
    protocol: str

    def parse(self, raw_body: bytes, headers: dict[str, str], query: str) -> NormalizedRequest: ...
    def redact(self, raw_body: dict, hits: list[PolicyHit]) -> bytes: ...
    def synthesize_block(self, req: NormalizedRequest, hit: PolicyHit) -> Response: ...
    def upstream_path(self, request_path: str) -> str: ...
```

### `ProviderAdapter`

```py
class ProviderAdapter(Protocol):
    provider: str

    async def open_upstream(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
        query_string: str,
    ) -> httpx.Response: ...
```

---

## Routing propuesto

| Endpoint Tranquera | Protocol adapter | Primeros clientes |
|---|---|---|
| `/cli/{token}/v1/messages` | `anthropic_messages` | Claude Code actual |
| `/openai/cli/{token}/v1/chat/completions` | `openai_chat` | opencode, Aider, LiteLLM clients, Ollama/LM Studio/vLLM clients |
| `/openai/cli/{token}/v1/responses` | `openai_responses` | Codex CLI, OpenAI Responses clients |
| `/hooks/gemini/before-model` | `gemini_hook` | Gemini CLI hook mode, futuro |

> El token en path se mantiene para clientes que no dejan inyectar headers. Para clientes que sí permiten headers, aceptar también `Authorization: Bearer <tranquera_token>` como variante futura.

---

## Data model mínimo

`Interaction` ya tiene casi todo. Agregar metadata no disruptiva:

```prisma
model Interaction {
  // existente...
  requestModel    String @map("request_model")

  // nuevo opcional
  protocol        String @default("anthropic_messages")
  integration     String @default("claude-code")
  upstreamProvider String? @map("upstream_provider")
  upstreamModel    String? @map("upstream_model")
}
```

Motivo: poder filtrar eventos por harness/proveedor sin inferir desde `requestModel`.

---

## Config propuesta

```env
# Default global, puede ser overrideado por org/integration
TRANQUERA_DEFAULT_PROTOCOL=anthropic_messages
TRANQUERA_DEFAULT_INTEGRATION=claude-code

# Anthropic current path
ANTHROPIC_UPSTREAM_URL=https://api.anthropic.com

# OpenAI-compatible path
OPENAI_COMPAT_UPSTREAM_URL=https://api.openai.com/v1
OPENAI_COMPAT_PROVIDER=openai

# Gateway opcional
LITELLM_UPSTREAM_URL=
```

A nivel org, el admin debería poder elegir:

```json
{
  "integration": "opencode",
  "protocol": "openai_chat",
  "upstreamProvider": "litellm",
  "upstreamBaseUrl": "https://litellm.company.com/v1",
  "modelAllowlist": ["gpt-5.1-codex", "anthropic/claude-sonnet-4"]
}
```

---

## Acceptance Criteria

- [ ] La lógica de regex/NL/persistencia no importa directamente `MessagesRequest` de Anthropic.
- [ ] Claude Code sigue funcionando sin cambios visibles para el dev.
- [x] Cada request persistido incluye `protocol` e `integration`.
- [ ] `BLOCK` se sintetiza con el shape correcto para el protocolo de entrada.
- [ ] `REDACT` modifica solo los `TextPart.path` detectados por el adapter.
- [ ] Un nuevo protocol adapter se puede agregar sin tocar la cascada.
- [ ] Los errores de parseo son protocol-specific pero los logs/audit usan `trace_id` común.

---

## Tasks

- [ ] **T1 — Extraer normalized text extraction.** Crear `NormalizedRequest` y mover `_flatten_prompt` / `extract_texts` a una capa protocol-agnostic. Done: tests cubren Anthropic actual y devuelven mismos textos.
- [ ] **T2 — Anthropic adapter explícito.** Encapsular parse/redact/block/upstream path actual en `AnthropicMessagesAdapter`. Done: smoke Claude Code sigue pasando.
- [ ] **T3 — Provider adapter actual.** Mover `open_upstream` a `AnthropicProviderAdapter` sin cambiar comportamiento. Done: headers filtrados y streaming siguen igual.
- [x] **T4 — Persistir protocol metadata.** Agregar migration Prisma + SQLModel fields para `protocol`, `integration`, `upstream_provider`, `upstream_model`. Done: `/admin/events` no se rompe y muestra defaults.
- [ ] **T5 — Adapter registry.** Resolver adapter por route prefix. Done: route Anthropic actual usa registry, no imports directos.
- [ ] **T6 — Regression smoke.** Smoke BLOCK/LOG/REDACT del spec 01 pasa igual que antes.

---

## Verification

- `ANTHROPIC_BASE_URL=<proxy>/cli/<token> claude "prompt benigno"` sigue funcionando.
- Prompt con credencial sigue devolviendo `tranquera_blocked` Anthropic-shaped.
- Query a `interactions` muestra `protocol='anthropic_messages'` e `integration='claude-code'`.
- Tests unitarios de normalización no requieren red ni credenciales.

---

## Dependencias

- [01 — Engine / Interceptor](./01-engine-interceptor.md)
- [04 — Admin Web](./04-admin-web.md)
- [13 — OpenAI-compatible Adapter](./13-openai-compatible-adapter.md)
- [14 — Harness Integrations](./14-harness-integrations.md)
