# 14 — Harness Integrations

> Cómo Tranquera se instala y se usa desde harnesses que no son Claude Code: **opencode**, **Pi**, **Aider**, **Codex CLI** y, más adelante, **Gemini CLI hooks**. Esta spec define el orden de integración, configs esperadas y criterios de smoke.

---

## Estado actual

Parcial. `opencode` ya funciona vía ruta OpenAI-compatible de spec 13 y registra eventos con metadata de integración/protocolo. Faltan docs copiables (`docs/integrations/*`), smoke scripts formales y el resto de integraciones (Pi, Aider, LiteLLM docs, Codex Responses API, Gemini hooks).

---

## Decisión corta

El orden recomendado es:

1. **opencode** vía OpenAI-compatible custom provider.
2. **Pi** vía provider override / package.
3. **Aider** como smoke simple de OpenAI-compatible.
4. **LiteLLM** como gateway aguas abajo, no como harness.
5. **Codex CLI** cuando exista `/v1/responses`.
6. **Gemini CLI** vía hooks si decidimos soportar enforcement no-proxy.

---

## Criterios de evaluación

| Criterio | Qué buscamos |
|---|---|
| Configurable por base URL | Que el admin/dev pueda rutear tráfico por Tranquera sin forkear el harness |
| Protocolos abiertos | OpenAI Chat/Responses, Anthropic Messages o hooks documentados |
| Tool calling estable | Coding agents necesitan tools; el proxy no debe romperlas |
| Distribución corporativa | Config reproducible por archivo, package o comando |
| Atribución | Poder identificar org/dev vía path token o header |
| Scope razonable | PoC en horas/días, no rewrite del producto |

---

## Integración 1 — opencode

### Por qué primero

opencode soporta muchos providers vía AI SDK/Models.dev y permite configurar `baseURL` por provider. También permite custom providers con `@ai-sdk/openai-compatible`, que encaja directo con spec 13.

### Config target

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
        "gpt-5.1-codex": {"name": "GPT 5.1 Codex via Tranquera"},
        "qwen-coder": {"name": "Qwen Coder via Tranquera"}
      }
    }
  },
  "model": "tranquera/gpt-5.1-codex"
}
```

### Acceptance

- [x] `opencode` puede mandar un prompt benigno y recibir respuesta normal.
- [x] Un prompt con credencial/NL policy devuelve BLOCK renderizable en la TUI.
- [ ] Tool calls no se rompen en LOG passthrough. Pendiente de smoke formal.
- [x] El admin ve el evento con `integration='opencode'` cuando `OPENAI_COMPAT_INTEGRATION=opencode`.
- [ ] La guía de setup cabe en menos de 10 líneas para el dev.

### Tasks

- [ ] **T1 — Config sample.** Agregar `docs/integrations/opencode.md` con config mínima. Done: copia/pega funciona local.
- [ ] **T2 — Smoke script.** Crear smoke manual con prompt benigno + BLOCK. Runtime smoke manual realizado, script/doc pendiente.
- [x] **T3 — Integration label.** Route OpenAI usa config `OPENAI_COMPAT_INTEGRATION`/`OPENAI_COMPAT_PROVIDER`. Done: eventos muestran opencode cuando la config lo define.

---

## Integración 2 — Pi

### Por qué segundo

Pi tiene soporte amplio de providers y permite:

- override de built-in providers con `baseUrl`;
- custom providers en `~/.pi/agent/models.json`;
- extensions para provider registration;
- packages para distribuir configuración y comandos.

### Modos posibles

#### Modo A — `models.json` simple

```json
{
  "providers": {
    "tranquera-openai": {
      "baseUrl": "https://proxy.tranquera.dev/openai/cli/<token>/v1",
      "api": "openai-completions",
      "apiKey": "TRANQUERA_UPSTREAM_API_KEY",
      "models": [
        {"id": "gpt-5.1-codex", "name": "GPT 5.1 Codex via Tranquera", "reasoning": true}
      ]
    }
  }
}
```

#### Modo B — override Anthropic existente

```json
{
  "providers": {
    "anthropic": {
      "baseUrl": "https://proxy.tranquera.dev/cli/<token>/v1"
    }
  }
}
```

#### Modo C — Pi package/extension

Un package `tranquera-pi` podría:

- pedir login/device flow;
- escribir `models.json` sin exponer secretos;
- registrar providers `tranquera-openai` y `tranquera-anthropic`;
- agregar comando `/tranquera-status`;
- validar health del proxy.

### Acceptance

- [ ] Pi puede usar `tranquera-openai/<model>` vía OpenAI-compatible endpoint.
- [ ] Pi puede seguir usando Claude vía Anthropic override si el usuario lo quiere.
- [ ] BLOCK se muestra como respuesta del modelo, no como stacktrace.
- [ ] El evento queda atribuido al token del dev.
- [ ] No se leen ni imprimen API keys en setup.

### Tasks

- [ ] **T1 — models.json sample.** Documentar configuración manual mínima. Done: `pi --provider tranquera-openai --model gpt-5.1-codex` funciona.
- [ ] **T2 — Anthropic override smoke.** Probar modo actual usando `baseUrl` de Anthropic. Done: Claude path sigue OK.
- [ ] **T3 — Package design.** Especificar comandos del package Pi. Done: mini-RFC con install/setup/logout/status.
- [ ] **T4 — Secret-safe setup.** Definir cómo escribir env/config sin imprimir keys. Done: guía usa referencias de env, no valores literales.

---

## Integración 3 — Aider

### Por qué incluirlo

Aider es un smoke simple y conocido para OpenAI-compatible APIs. No es el principal target enterprise, pero sirve para validar que el endpoint es estándar.

### Config target

```bash
export OPENAI_API_BASE=https://proxy.tranquera.dev/openai/cli/$TOKEN/v1
export OPENAI_API_KEY=$UPSTREAM_OR_GATEWAY_KEY
aider --model openai/gpt-5.1-codex
```

### Acceptance

- [ ] Prompt benigno completa una edición simple.
- [ ] Prompt bloqueado se muestra como respuesta textual.
- [ ] No hay errores por shape inválido de Chat Completions.

---

## Integración 4 — LiteLLM como gateway

### Rol correcto

LiteLLM no reemplaza a Tranquera. Queda aguas abajo como gateway de providers:

```text
harness → Tranquera → LiteLLM → OpenAI / Anthropic / Gemini / Bedrock / etc.
```

Tranquera aplica políticas antes de que el prompt llegue a LiteLLM. LiteLLM se ocupa de routing, keys, budgets y normalización de 100+ providers.

### Acceptance

- [ ] Tranquera puede forwardear a `LITELLM_UPSTREAM_URL` como OpenAI-compatible upstream.
- [ ] `upstream_provider='litellm'` queda persistido.
- [ ] Si LiteLLM devuelve error de provider, Tranquera lo propaga sin filtrar secretos en logs.

---

## Integración 5 — Codex CLI

### Por qué no primero

Codex CLI es estratégico, pero su camino natural es **OpenAI Responses API** (`/v1/responses`), no Chat Completions. Eso requiere otro adapter.

### Target futuro

```text
codex → /openai/cli/<token>/v1/responses → OpenAIResponsesAdapter → cascade → upstream
```

### Acceptance futura

- [ ] `~/.codex/config.toml` puede definir un provider con `base_url` apuntando a Tranquera.
- [ ] `wire_api='responses'` funciona para LOG passthrough.
- [ ] BLOCK se sintetiza con Responses-shaped output.
- [ ] Tool calls / reasoning summaries no se corrompen.

### Tasks futuras

- [ ] **T1 — Codex provider config research.** Validar config real actual en una instalación local.
- [ ] **T2 — Responses schema subset.** Definir Pydantic models permissive para `/v1/responses`.
- [ ] **T3 — Responses BLOCK synthesizer.** Crear response y stream compatibles.
- [ ] **T4 — Codex smoke.** Prompt benigno + BLOCK desde Codex CLI.

---

## Integración 6 — Gemini CLI hooks

### Por qué es distinto

Gemini CLI parece más cerrado al ecosistema Gemini/Vertex, pero expone hooks `BeforeModel` y `AfterModel`. Eso permite enforcement sin proxy de red:

```text
Gemini CLI BeforeModel hook → Tranquera policy check → allow/block/redact
```

No es equivalente a interceptar todo tráfico HTTP, pero puede ser aceptable para clientes que ya usan Gemini CLI.

### Riesgos

- El hook puede ser deshabilitado por el usuario si no hay control corporativo.
- Hay que entender bien el payload del hook antes de prometer BLOCK/REDACT.
- Puede no cubrir todos los caminos internos del CLI.

### Acceptance futura

- [ ] Hook `BeforeModel` manda prompt normalizado a Tranquera.
- [ ] Tranquera devuelve `ALLOW | BLOCK | REDACT`.
- [ ] BLOCK corta la ejecución antes de llamar al modelo.
- [ ] Evento queda auditado con `integration='gemini-cli-hook'`.

---

## Distribución corporativa

### Ideal común

Cada integración debería tener un comando equivalente a:

```bash
npx tranquera setup --integration opencode
npx tranquera setup --integration pi
npx tranquera setup --integration aider
```

Ese comando debe:

1. autenticar al dev;
2. obtener token path-based;
3. escribir config del harness;
4. verificar `/health`;
5. ejecutar un smoke benigno opcional;
6. explicar cómo hacer logout.

### No negociable

- No imprimir secretos.
- No modificar configs sin marker reversible.
- `logout` debe remover token/config o dejar instrucciones claras.
- Toda config generada debe indicar que Tranquera es el proxy activo.

---

## Matriz de prioridad

| Target | Protocolo | Esfuerzo | Impacto | Prioridad |
|---|---|---:|---:|---:|
| opencode | OpenAI Chat | bajo/medio | alto | P0 |
| Pi | OpenAI Chat + Anthropic | medio | alto | P0 |
| Aider | OpenAI Chat | bajo | medio | P1 |
| LiteLLM | OpenAI Chat upstream | bajo | alto | P1 |
| Codex CLI | OpenAI Responses | medio/alto | alto | P2 |
| Gemini CLI | hooks | medio | medio | P3 |
| Cursor/Cline/Roo/Continue | variable | medio | medio | P3 |

---

## Acceptance Criteria

Para considerar una integración lista:

- [ ] Setup documentado desde cero.
- [ ] Prompt benigno llega al upstream y responde.
- [ ] Prompt con credencial queda bloqueado antes del upstream.
- [ ] Si aplica, prompt REDACT llega upstream sin secreto.
- [ ] `interactions` registra `org_id`, `user_id`, `integration`, `protocol`, `request_model`, `action`.
- [ ] Logout/desconexión documentado.

## Verification global

- [ ] Cada integración P0 tiene una guía de setup copiable.
- [ ] Cada integración P0 tiene smoke benigno + BLOCK.
- [ ] Cada integración P0 registra `integration` y `protocol` en audit.

---

## Dependencias

- [12 — Provider Abstraction](./12-provider-abstraction.md)
- [13 — OpenAI-compatible Adapter](./13-openai-compatible-adapter.md)
- [07 — Requirements & Docs técnicos](./07-requirements-docs.md)
