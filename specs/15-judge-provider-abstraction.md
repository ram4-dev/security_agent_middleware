# 15 — Judge Provider Abstraction

> Separar el **NL judge interno de Tranquera** del proveedor Anthropic hardcodeado. Esta spec no cambia el protocolo del cliente; agrega una integración multiprovider para que el judge pueda correr con **OpenCode Go**, **OpenAI** o **Gemini**, manteniendo el mismo contrato de `PolicyHit` para la cascada.

---

## Decisión corta

No vamos a reemplazar Tranquera por OpenCode ni a atar el judge a un único proveedor. Vamos a introducir una frontera explícita:

```text
Regex / Pattern → JudgeProvider → PolicyHit[] → BLOCK · REDACT · WARN · LOG
```

Implementación inicial recomendada:

```text
JUDGE_PROVIDER=opencode-go
JUDGE_BASE_URL=https://opencode.ai/zen/go/v1
JUDGE_MODEL=qwen3.6-plus
JUDGE_API_KEY=...
```

Pero el contrato debe soportar también:

```text
JUDGE_PROVIDER=openai
JUDGE_PROVIDER=gemini
```

---

## Contexto

Hoy `interceptor/app/nl_layer.py` asume Anthropic:

- credencial: `ANTHROPIC_JUDGE_API_KEY`;
- endpoint: `POST /v1/messages`;
- modelo: `claude-haiku-4-5-20251001`;
- headers: `x-api-key` + `anthropic-version`;
- parseo de respuesta Anthropic `content[].text`.

Eso bloquea despliegues donde el operador quiere usar OpenCode Go, OpenAI o Gemini como proveedor del judge. El resto de la cascada no necesita saber qué LLM juzgó la regla: solo necesita `list[PolicyHit]`.

---

## Goals

- Extraer un contrato `JudgeProvider` provider-agnostic.
- Mantener el comportamiento actual de Anthropic como provider soportado.
- Agregar provider OpenAI-compatible para:
  - OpenCode Go;
  - OpenAI;
  - otros gateways OpenAI-compatible como futura extensión, sin prometer soporte en esta spec.
- Agregar provider Gemini con `generateContent`.
- Unificar prompt, parseo JSON y conversión a `PolicyHit`.
- Mantener fail-open: si el judge falla, devuelve `[]` y el request sigue con LOG/passthrough salvo que regex haya decidido antes.
- No requerir API keys reales en tests.

## Non-Goals

- No cambiar el endpoint cliente `/openai/cli/{token}/v1/chat/completions`.
- No cambiar la semántica de regex/pattern policies.
- No usar la API key del usuario final para el judge por default.
- No hacer routing dinámico por organización en UI en esta fase.
- No migrar todo a OpenCode-only.
- No resolver costos, billing ni cuotas por tenant.

---

## Config contract

### Default / backwards compatible

Si solo existe la config vieja, debe seguir funcionando:

```env
ANTHROPIC_JUDGE_API_KEY=...
ANTHROPIC_UPSTREAM_URL=https://api.anthropic.com
```

Equivalente nuevo:

```env
JUDGE_PROVIDER=anthropic
JUDGE_MODEL=claude-haiku-4-5-20251001
JUDGE_API_KEY=...
JUDGE_BASE_URL=https://api.anthropic.com
```

### OpenCode Go judge

```env
JUDGE_PROVIDER=opencode-go
JUDGE_BASE_URL=https://opencode.ai/zen/go/v1
JUDGE_MODEL=qwen3.6-plus
JUDGE_API_KEY=...
```

### OpenAI judge

```env
JUDGE_PROVIDER=openai
JUDGE_BASE_URL=https://api.openai.com/v1
JUDGE_MODEL=gpt-4o-mini
JUDGE_API_KEY=...
```

### Gemini judge

```env
JUDGE_PROVIDER=gemini
JUDGE_MODEL=gemini-2.5-flash
JUDGE_API_KEY=...
```

### Disable judge

Si no hay credenciales:

```text
NL judge disabled → regex sigue funcionando → no se bloquea tráfico legítimo por falta de key
```

---

## Internal contract

```py
@dataclass
class JudgeRequest:
    trace_id: str
    org_id: str
    texts: list[str]
    policies: list[Policy]

@dataclass
class JudgeDecision:
    matched_policy_ids: list[str]
    raw_provider: str
    raw_model: str

class JudgeProvider(Protocol):
    provider: str

    async def judge(self, req: JudgeRequest) -> JudgeDecision: ...
```

La capa pública usada por `main.py` debe seguir siendo simple:

```py
async def run_nl_texts(texts: list[str], policies: list[Policy]) -> list[PolicyHit]: ...
```

---

## Prompt contract

Todos los providers reciben el mismo pedido lógico:

```text
Sos un judge de seguridad de datos.
Recibís reglas activas y texto evaluable del prompt.
Respondé SOLO JSON: {"matched": ["<policy_id>", ...]}
Si nada matchea: {"matched": []}
```

El provider adapter decide cómo serializarlo:

| Provider | Wire format |
|---|---|
| `anthropic` | Messages API con `system` + `messages` |
| `opencode-go` | OpenAI Chat Completions |
| `openai` | OpenAI Chat Completions |
| `gemini` | Gemini `generateContent` |

---

## Provider behavior

### Anthropic provider

- Conserva comportamiento actual.
- Lee `JUDGE_API_KEY` o fallback `ANTHROPIC_JUDGE_API_KEY`.
- Parse JSON desde `content[].text`.

### OpenAI-compatible provider

Aplica a `JUDGE_PROVIDER=opencode-go` y `JUDGE_PROVIDER=openai`.

Request:

```http
POST <JUDGE_BASE_URL>/chat/completions
Authorization: Bearer <JUDGE_API_KEY>
Content-Type: application/json
```

Body:

```json
{
  "model": "qwen3.6-plus",
  "messages": [
    {"role": "system", "content": "...judge system prompt..."},
    {"role": "user", "content": "...rules + prompt..."}
  ],
  "temperature": 0,
  "max_tokens": 256,
  "stream": false
}
```

Parse:

```text
choices[0].message.content → JSON → matched ids
```

### Gemini provider

Request:

```http
POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent?key=<JUDGE_API_KEY>
```

Body:

```json
{
  "contents": [
    {
      "role": "user",
      "parts": [{"text": "...system instructions + rules + prompt..."}]
    }
  ],
  "generationConfig": {
    "temperature": 0,
    "maxOutputTokens": 256,
    "responseMimeType": "application/json"
  }
}
```

Parse:

```text
candidates[0].content.parts[].text → JSON → matched ids
```

---

## Acceptance Criteria

- [x] `run_nl_texts()` ya no construye requests Anthropic inline.
- [x] `JUDGE_PROVIDER=anthropic` conserva compatibilidad con el flujo actual.
- [x] `JUDGE_PROVIDER=opencode-go` llama a OpenCode Go vía Chat Completions y devuelve `PolicyHit`.
- [x] `JUDGE_PROVIDER=openai` llama a OpenAI vía Chat Completions y devuelve `PolicyHit`.
- [x] `JUDGE_PROVIDER=gemini` llama a Gemini `generateContent` y devuelve `PolicyHit`.
- [x] Si falta `JUDGE_API_KEY` y no hay fallback legacy, `is_enabled()` devuelve false.
- [x] Si el provider falla, el judge devuelve `[]` y loggea warning sin imprimir secrets.
- [x] Tests mockean HTTP; no requieren keys reales.
- [x] Regex BLOCK sigue funcionando aunque el judge esté deshabilitado.
- [x] La respuesta del provider puede venir con texto extra o fences; el parser sigue buscando JSON defensivamente.

---

## Tasks

- [x] **T1 — Config unificada.** Agregar `judge_provider`, `judge_base_url`, `judge_model`, `judge_api_key` a settings con fallback legacy Anthropic. Done: config vieja sigue andando.
- [x] **T2 — Tipos base.** Crear `interceptor/app/judge/types.py` con `JudgeRequest`, `JudgeDecision`, `JudgeProvider`. Done: sin imports de Anthropic.
- [x] **T3 — Prompt + parser compartido.** Mover `_format_rules_block`, `_build_judge_messages_for_texts` y `_parse_matched_ids` a helpers compartidos. Done: tests cubren JSON limpio, fenced y con prefijo/sufijo.
- [x] **T4 — Anthropic adapter.** Mover request Anthropic actual a `interceptor/app/judge/anthropic.py`. Done: tests de compatibilidad pasan.
- [x] **T5 — OpenAI-compatible adapter.** Crear `interceptor/app/judge/openai_compatible.py`. Done: mock HTTP valida path `/chat/completions`, auth bearer y parse `choices[0].message.content`.
- [x] **T6 — Gemini adapter.** Crear `interceptor/app/judge/gemini.py`. Done: mock HTTP valida `generateContent` y parse `candidates`.
- [x] **T7 — Factory.** Crear `interceptor/app/judge/factory.py` para resolver provider por config. Done: providers desconocidos deshabilitan judge con warning.
- [x] **T8 — Integrar `nl_layer.py`.** Dejar `run_nl_texts()` como wrapper provider-agnostic. Done: `main.py` no cambia.
- [x] **T9 — Tests de fail-open.** Simular 401/500/timeout/malformed JSON. Done: siempre devuelve `[]` sin excepción.
- [x] **T10 — Smoke OpenCode Go.** Usar key local de OpenCode Go sin imprimirla. Done: una regla NL real (`disclose-pricing-strategy`) devuelve BLOCK vía `JUDGE_PROVIDER=opencode-go` con `qwen3.6-plus`.

---

## Verification

### Unit tests

```bash
cd interceptor
UV_INDEX_URL=https://pypi.org/simple uv run pytest tests/test_judge_providers.py
```

### Regression

```bash
cd interceptor
UV_INDEX_URL=https://pypi.org/simple uv run pytest
```

### OpenCode Go smoke seguro

No imprimir keys. Usar `.env` local o secret manager.

```env
JUDGE_PROVIDER=opencode-go
JUDGE_BASE_URL=https://opencode.ai/zen/go/v1
JUDGE_MODEL=qwen3.6-plus
JUDGE_API_KEY=<redacted>
```

Esperado:

- regex sigue bloqueando sin judge;
- regla NL activa puede matchear vía OpenCode Go;
- si OpenCode Go responde 401/429/500, Tranquera fail-open y registra warning.

---

## Dependency notes

- Depende de `12-provider-abstraction.md` solo conceptualmente: normalized texts ya existen para OpenAI route.
- Complementa `13-openai-compatible-adapter.md`, pero no lo reemplaza.
- No bloquea `14-harness-integrations.md`; el cliente puede ser opencode aunque el judge use Anthropic, OpenCode Go, OpenAI o Gemini.
