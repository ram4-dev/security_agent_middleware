# 18 — Local Judge Service

> Servicio separado que expone el Specialized Local Judge al interceptor. La implementación default usa **vLLM** como motor de serving, con contrato HTTP propio y modelo/prompt versionados.

---

## Estado actual

Pendiente. No existe todavía un servicio dedicado de Local Judge. La spec 17 define cómo lo consume el interceptor; esta spec define cómo se empaqueta, sirve y valida el judge local.

## Decisión corta

Crear un servicio Python separado, deployable como contenedor, que reciba `LocalJudgeRequest`, construya un prompt de clasificación/decisión, llame a vLLM y devuelva `LocalJudgeResponse` JSON estricto.

```text
interceptor → local-judge-service → vLLM engine → model 3B–5B → strict JSON response
```

---

## Goals

- Exponer endpoint `POST /v1/judge` para el interceptor.
- Usar vLLM como motor default de serving.
- Mantener el servicio model-agnostic vía config de modelo/prompt.
- Forzar salida JSON estricta cuando el motor lo permita.
- Validar salida antes de responder al interceptor.
- Proveer `/healthz`, `/readyz` y metadata de versión.
- No depender de claves de proveedores externos para el path local.

## Non-Goals

- No reemplazar al interceptor ni aplicar enforcement dentro del servicio.
- No persistir interacciones en DB desde este servicio.
- No hacer training dentro del proceso de serving.
- No exponer endpoint público a usuarios finales.
- No soportar multi-tenant avanzado en v1 más allá de recibir `org_id` y policies del interceptor.

---

## Service layout target

```text
local-judge/
├── pyproject.toml
├── Dockerfile
├── README.md
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # env/settings
│   ├── schemas.py           # request/response validation
│   ├── prompt.py            # prompt builder versioned
│   ├── vllm_client.py        # vLLM/OpenAI-compatible client
│   ├── parser.py            # strict JSON parse + repair-free validation
│   └── risk_taxonomy.py
├── prompts/
│   └── local_judge_v1.md
└── tests/
    ├── fixtures/
    └── test_judge_contract.py
```

Puede vivir en `local-judge/` o `services/local-judge/`. Si se prefiere mantener todo Python junto, también puede vivir bajo `interceptor/local_judge_service/`, pero debe correr como proceso separado.

---

## Config contract

```env
LOCAL_JUDGE_SERVICE_HOST=0.0.0.0
LOCAL_JUDGE_SERVICE_PORT=8088
LOCAL_JUDGE_VLLM_BASE_URL=http://localhost:8000/v1
LOCAL_JUDGE_VLLM_MODEL=Qwen/Qwen3-4B-Instruct-2507
LOCAL_JUDGE_PROMPT_VERSION=local_judge_v1
LOCAL_JUDGE_MAX_INPUT_CHARS=30000
LOCAL_JUDGE_MAX_OUTPUT_TOKENS=512
LOCAL_JUDGE_TEMPERATURE=0
LOCAL_JUDGE_TOP_P=1
LOCAL_JUDGE_JSON_MODE=true
LOCAL_JUDGE_REQUEST_TIMEOUT_MS=700
```

---

## API contract

### `POST /v1/judge`

Request: `LocalJudgeRequest` de spec 17.

Response 200:

```json
{
  "decision": "LOG",
  "confidence": 0.91,
  "risk_type": "BENIGN_REQUEST",
  "severity": "LOW",
  "matched_policy_ids": [],
  "explanation": "The request is a benign coding question and no sensitive data is present.",
  "redaction_targets": [],
  "model_version": "Qwen3-4B-Instruct-2507:local_judge_v1"
}
```

Response 422:

```json
{ "error": "invalid_judge_request", "trace_id": "01HXYZ" }
```

Response 503:

```json
{ "error": "model_unavailable", "trace_id": "01HXYZ" }
```

El servicio nunca debe incluir contenido sensible original en errores.

### `GET /healthz`

Proceso vivo.

### `GET /readyz`

Modelo listo y vLLM responde.

### `GET /v1/metadata`

```json
{
  "service": "tranquera-local-judge",
  "model": "Qwen/Qwen3-4B-Instruct-2507",
  "prompt_version": "local_judge_v1",
  "risk_taxonomy_version": "risk_taxonomy_v1"
}
```

---

## Prompt contract

El prompt debe:

- indicar que el modelo es un judge de seguridad, no un asistente;
- listar decisiones válidas: `LOG`, `WARN`, `BLOCK`, `REDACT`, `ESCALATE`;
- listar taxonomía de riesgos;
- exigir JSON sin markdown;
- prohibir repetir secretos en `explanation`;
- ordenar que `REDACT` devuelva targets, no payload completo;
- ordenar `ESCALATE` ante ambigüedad o baja confianza.

Skeleton:

```text
You are Tranquera Local Judge, a security classifier for LLM-bound traffic.
Return ONLY valid JSON matching the schema.
Never quote secrets or PII in explanations.
If uncertain, choose ESCALATE.
...
```

---

## vLLM integration

Default: vLLM con endpoint OpenAI-compatible local.

Request interno:

```json
{
  "model": "Qwen/Qwen3-4B-Instruct-2507",
  "messages": [
    { "role": "system", "content": "<prompt system>" },
    { "role": "user", "content": "<serialized judge request>" }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 512,
  "stream": false
}
```

Si vLLM soporta guided decoding / JSON schema en el entorno objetivo, activarlo. Si no, la respuesta se valida y ante error el servicio devuelve 503/invalid_model_output para que el interceptor escale.

---

## Output validation

El servicio valida:

- `decision` dentro del enum interno;
- `confidence` en `[0,1]`;
- `risk_type` dentro de taxonomía;
- `severity` dentro de `LOW | MEDIUM | HIGH | CRITICAL`;
- `matched_policy_ids` subset de policies recibidas;
- `explanation` corta y sin patrones de secretos;
- `redaction_targets` presentes si `decision=REDACT`;
- paths/spans bien formados.

No se hace “JSON repair” mágico en v1. Si no parsea, se considera fallo del modelo y el interceptor escala.

---

## Model candidates for service smoke

Orden para smoke inicial:

1. `Qwen/Qwen3-4B-Instruct-2507`
2. `meta-llama/Llama-3.2-3B-Instruct`
3. `google/gemma-3-4b-it`
4. `microsoft/Phi-3-mini-4k-instruct`

El servicio debe permitir cambiar modelo por env sin cambiar el contrato HTTP.

---

## Acceptance Criteria

- [ ] `POST /v1/judge` acepta el request de spec 17 y devuelve JSON validado.
- [ ] `/healthz`, `/readyz` y `/v1/metadata` funcionan.
- [ ] vLLM puede correr al menos un modelo candidato con temperatura 0.
- [ ] Outputs inválidos no llegan al interceptor como decisiones válidas.
- [ ] Explicaciones no reproducen secretos/PII detectados.
- [ ] `REDACT` sin targets válidos se rechaza.
- [ ] Tests no requieren GPU ni modelo real: usan vLLM client mock.
- [ ] Smoke manual con modelo real queda documentado.

---

## Tasks

- [ ] **T1 — Crear scaffold del servicio.** FastAPI app, settings, schemas y tests base. Done: `/healthz` responde localmente.
- [ ] **T2 — Implementar schemas.** Pydantic para request/response y taxonomía. Done: fixtures válidos/ inválidos pasan.
- [ ] **T3 — Prompt builder versionado.** Crear `prompts/local_judge_v1.md` y serializer estable. Done: prompt snapshot testeado.
- [ ] **T4 — vLLM client.** Cliente OpenAI-compatible contra `LOCAL_JUDGE_VLLM_BASE_URL`. Done: mock y contrato real documentados.
- [ ] **T5 — Parser estricto.** Parsear JSON sin repair y validar semántica. Done: invalid output devuelve error controlado sin secretos.
- [ ] **T6 — Endpoints operativos.** `/readyz` verifica disponibilidad de modelo. Done: healthchecks sirven para deploy.
- [ ] **T7 — Dockerfile.** Imagen reproducible separando servicio y vLLM cuando corresponda. Done: `docker build` funciona.
- [ ] **T8 — Smoke con modelo real.** Correr 10 fixtures contra Qwen vía vLLM. Done: reporte con parse rate y latencia básica.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| vLLM requiere GPU o setup pesado | Separar tests mock de smoke real; documentar hardware mínimo en spec 21. |
| Modelo devuelve texto fuera de JSON | Guided decoding cuando esté disponible + fallback por invalid output. |
| Servicio filtra secretos en logs | Logging estructurado sin body completo; solo trace_id, risk_type, decision, latencia. |
| Prompt drift rompe training/eval | Prompt versionado y compartido con eval/training. |
| Modelo no soporta bien español/inglés mixto | Dataset debe incluir ambos idiomas y tráfico realista de coding agents. |
