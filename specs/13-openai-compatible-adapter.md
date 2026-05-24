# 13 — OpenAI-compatible Adapter

> Primer salto multi-provider. Exponer una API compatible con **OpenAI Chat Completions** para que Tranquera pueda proteger opencode, Aider, LiteLLM clients, OpenRouter, Ollama, LM Studio, vLLM y otros clientes que ya hablan `/v1/chat/completions`.

---

## Estado actual

Implementado en `interceptor/app/openai_adapter.py`, `interceptor/app/main.py` y tests `interceptor/tests/test_openai_adapter.py` / `test_openai_route.py`. Quedan pendientes smokes/documentación externos para Aider y validación de streaming BLOCK en un cliente real; el runtime opencode ya se probó vía ruta OpenAI-compatible.

---

## Decisión corta

Implementamos primero **OpenAI Chat Completions**, no Responses API. Es el protocolo con mayor superficie inmediata y menor costo de integración.

```text
opencode / Aider / local client
  → https://proxy.tranquera.dev/openai/cli/<token>/v1/chat/completions
  → OpenAIChatAdapter
  → cascada Tranquera
  → OpenAI-compatible upstream o LiteLLM
```

---

## Contexto

La implementación actual solo acepta Anthropic Messages API. Muchos harnesses alternativos, en cambio, ya permiten configurar un `baseURL` OpenAI-compatible:

- opencode custom provider con `@ai-sdk/openai-compatible`
- Aider con `OPENAI_API_BASE`
- Ollama / LM Studio / vLLM usando `/v1/chat/completions`
- OpenRouter y gateways compatibles
- LiteLLM Proxy como gateway unificado a 100+ providers

Si Tranquera habla OpenAI-compatible, el producto deja de depender exclusivamente de Claude Code sin tener que escribir adapters por cada provider.

---

## Goals

- Agregar endpoint `POST /openai/cli/{token}/v1/chat/completions`.
- Aceptar el subset de OpenAI Chat Completions necesario para coding agents.
- Evaluar `messages[].content` y `developer/system` prompts con la cascada actual.
- Soportar `BLOCK`, `REDACT`, `WARN`, `LOG`.
- Forwardear a un upstream OpenAI-compatible configurable.
- Soportar streaming SSE (`stream: true`) y non-streaming.
- Mantener path-token attribution igual que Claude Code.

## Non-Goals

- No implementar `/v1/responses` en esta spec; eso queda para Codex.
- No implementar embeddings, images, audio ni fine-tuning.
- No garantizar compatibilidad con todos los quirks de cada provider local.
- No traducir tool calls complejos más allá de forward 1:1 cuando no hay redacción.
- No almacenar API keys de usuarios finales en la DB en esta fase.

---

## Request contract

```http
POST /openai/cli/{token}/v1/chat/completions
Content-Type: application/json
Authorization: Bearer <upstream-api-key>
```

```json
{
  "model": "gpt-5.1-codex",
  "stream": true,
  "messages": [
    {"role": "system", "content": "You are a coding assistant."},
    {"role": "user", "content": "Refactor this code. SECRET=..."}
  ],
  "tools": []
}
```

### Roles evaluables

| Role | Se evalúa | Motivo |
|---|---:|---|
| `user` | sí | principal fuente de leaks |
| `system` | sí | puede contener contexto corporativo sensible |
| `developer` | sí | usado por Responses/modern OpenAI clients; algunos compatibles lo mandan en chat |
| `assistant` | no por default | no re-escribimos respuestas del modelo en v1 |
| `tool` | no por default | puede ser output local; evaluar en fase posterior |

---

## Response contract

### LOG / WARN / REDACT

Se devuelve el response upstream 1:1, agregando headers diagnósticos:

```http
x-tranquera-trace-id: 01...
x-tranquera-action: LOG
x-tranquera-protocol: openai_chat
```

> Durante migración, se pueden mantener aliases `x-team22-*` para no romper UI existente, pero lo canónico nuevo debe ser `x-tranquera-*`.

### BLOCK non-streaming

```json
{
  "id": "chatcmpl_tranquera_blocked_01...",
  "object": "chat.completion",
  "created": 1760000000,
  "model": "gpt-5.1-codex",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Tu prompt se cruzó con la política `aws-access-key`: detectamos un patrón de credencial. Reformulalo sin incluir ese dato o coordiná con tu admin. — Tranquera"
      },
      "finish_reason": "content_filter"
    }
  ],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

### BLOCK streaming

Emitir SSE compatible con Chat Completions:

```text
data: {"id":"chatcmpl_tranquera_blocked_01...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl_tranquera_blocked_01...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Tu prompt se cruzó..."},"finish_reason":null}]}

data: {"id":"chatcmpl_tranquera_blocked_01...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"content_filter"}]}

data: [DONE]
```

---

## Redaction rules

Para `REDACT`, el adapter muta únicamente texto plano:

```json
{"role": "user", "content": "..."}
```

y bloques tipo:

```json
{"type": "text", "text": "..."}
```

Si `content` incluye imágenes, archivos u otros tipos no-textuales:

- no se modifican;
- se forwardean tal cual;
- se registra `redaction_skipped_non_text_blocks` en `latency_by_layer` o metadata audit si había hits parciales.

---

## Upstream options

| Upstream | Uso recomendado |
|---|---|
| OpenAI directo | PoC simple con modelos OpenAI |
| OpenRouter | Multi-provider rápido, routing por proveedor |
| LiteLLM Proxy | Enterprise/gateway recomendado para 100+ providers |
| Ollama / LM Studio / vLLM | Local dev y demo offline |
| Cloudflare/Vercel AI Gateway | Gateway administrado con billing/routing |

Config mínima:

```env
OPENAI_COMPAT_UPSTREAM_URL=https://api.openai.com/v1
OPENAI_COMPAT_PROVIDER=openai
```

Para LiteLLM:

```env
OPENAI_COMPAT_UPSTREAM_URL=https://litellm.company.com/v1
OPENAI_COMPAT_PROVIDER=litellm
```

---

## Acceptance Criteria

- [x] `POST /openai/cli/{token}/v1/chat/completions` valida JSON y resuelve caller por token.
- [x] Prompt benigno se forwardea a upstream y devuelve body/stream compatible.
- [x] Prompt con policy `BLOCK` devuelve `200` con Chat Completions-shaped response, no toca upstream.
- [x] Prompt con policy `REDACT` forwardea body mutado, sin persistir el secreto original.
- [ ] Streaming `BLOCK` renderiza correctamente en al menos un cliente OpenAI-compatible. Unit test del SSE existe; smoke de cliente real pendiente.
- [x] Headers canónicos `x-tranquera-*` están presentes.
- [x] `interactions.protocol = 'openai_chat'` e `integration` se setea según route/config.
- [x] Tests no requieren API key real para casos BLOCK y parse/redact.

---

## Tasks

- [x] **T1 — OpenAI schema subset.** Definir Pydantic models permissive para `ChatCompletionsRequest` con `extra="allow"`. Done: acepta `messages`, `model`, `stream`, `tools`, `temperature` sin dropear campos.
- [x] **T2 — Text extraction.** Implementar extractor para `messages[].content` string y text blocks. Done: unit tests cubren string, blocks mixtos y roles system/developer/user.
- [x] **T3 — BLOCK JSON synthesizer.** Crear response non-streaming compatible con Chat Completions. Done: snapshot test del shape.
- [x] **T4 — BLOCK SSE synthesizer.** Crear stream SSE con chunks y `[DONE]`. Done: test consume bytes y valida orden.
- [x] **T5 — REDACT mutator.** Mutar body OpenAI-compatible preservando campos extra. Done: snapshot antes/después.
- [x] **T6 — OpenAI-compatible provider forwarder.** Reusar cliente httpx con base URL configurable y headers filtrados. Done: mock upstream recibe `/v1/chat/completions`.
- [x] **T7 — Route + token attribution.** Agregar `/openai/cli/{token}/v1/chat/completions`. Done: token revocado devuelve 401 igual que Claude path.
- [x] **T8 — opencode smoke.** Configurar opencode custom provider apuntando al proxy. Done: prompt benigno responde; prompt con secreto/NL bloquea.
- [ ] **T9 — Aider/local smoke.** Configurar `OPENAI_API_BASE` contra el proxy. Done: BLOCK no rompe el cliente.

---

## Verification

### curl BLOCK sin upstream real

```bash
curl -i -X POST http://localhost:8080/openai/cli/$TOKEN/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer fake' \
  -d '{
    "model": "gpt-5.1-codex",
    "messages": [{"role":"user","content":"[REDACTED:AWS_KEY]"}]
  }'
```

Esperado:

- `HTTP 200`
- `x-tranquera-action: BLOCK`
- body con `object: "chat.completion"`
- `finish_reason: "content_filter"`

### opencode config PoC

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "tranquera": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Tranquera",
      "options": {
        "baseURL": "https://proxy.tranquera.dev/openai/cli/<token>/v1"
      },
      "models": {
        "gpt-5.1-codex": {"name": "GPT 5.1 Codex via Tranquera"}
      }
    }
  },
  "model": "tranquera/gpt-5.1-codex"
}
```

### Aider PoC

```bash
export OPENAI_API_BASE=https://proxy.tranquera.dev/openai/cli/$TOKEN/v1
export OPENAI_API_KEY=upstream-or-gateway-key
aider --model openai/gpt-5.1-codex
```

---

## Dependencias

- [12 — Provider Abstraction](./12-provider-abstraction.md)
- [14 — Harness Integrations](./14-harness-integrations.md)
