# 17 — Local Judge Runtime Integration

> Cambios de implementación en el **Interceptor Engine** para insertar el Specialized Local Judge entre los checks determinísticos y el judge externo. Esta spec define wiring runtime, contratos mínimos, fallback y persistencia de decisiones.

---

## Estado actual

Pendiente. Hoy el interceptor ejecuta regex/pattern/NL judge multiprovider según specs 01 y 15. La nueva pieza debe ser aditiva: si el Local Judge está deshabilitado o falla, el flujo vuelve al comportamiento actual con fallback externo/fail-open según corresponda.

## Decisión corta

Agregar una etapa opcional en la cascada:

```text
Regex / Pattern → LocalJudgeClient → Haiku/JudgeProvider fallback → resolveAction → upstream
```

- Las acciones públicas siguen siendo `BLOCK | REDACT | WARN | LOG`.
- `LOG` representa el allow/pass público.
- `ESCALATE` es solo estado interno del Local Judge.
- El interceptor aplica enforcement y redacción; el modelo no reescribe payloads completos.

---

## Contexto

El Local Judge busca reducir llamadas a Haiku sin perder seguridad. Para lograrlo, el interceptor debe enviarle un request normalizado, validar su JSON estrictamente y decidir si acepta la decisión local o escala al judge externo.

Esta spec toca runtime del proxy; el servicio de inferencia vive en spec 18, evaluación en spec 19, entrenamiento en spec 20 y despliegue/observabilidad en spec 21.

---

## Goals

- Integrar un `LocalJudgeClient` configurable en el interceptor.
- Construir un `LocalJudgeRequest` a partir del request Anthropic/OpenAI-compatible normalizado.
- Validar `LocalJudgeResponse` con schema estricto antes de usarlo.
- Aplicar `LOG`, `WARN`, `BLOCK`, `REDACT` sin cambiar las acciones públicas existentes.
- Ejecutar fallback a JudgeProvider/Haiku ante `ESCALATE`, baja confianza, timeout, JSON inválido o error del servicio.
- Persistir `judge_source`, `risk_type`, `severity`, `confidence`, `latency_by_layer.local_judge` y explicación sanitizada.

## Non-Goals

- No implementar el servidor de inferencia local en esta spec.
- No entrenar ni seleccionar el modelo final.
- No agregar una acción pública `PASS`.
- No persistir `ESCALATE` como acción en DB.
- No permitir que el modelo devuelva payloads reescritos completos.
- No cambiar compatibilidad con Anthropic/OpenAI-compatible routes.

---

## Config contract

```env
LOCAL_JUDGE_ENABLED=false
LOCAL_JUDGE_BASE_URL=http://localhost:8088
LOCAL_JUDGE_TIMEOUT_MS=800
LOCAL_JUDGE_CONFIDENCE_THRESHOLD=0.75
LOCAL_JUDGE_HIGH_RISK_THRESHOLD=0.90
LOCAL_JUDGE_MODEL_VERSION=qwen3-4b-localjudge-prompt-v1
LOCAL_JUDGE_FAIL_OPEN=true
```

Reglas:

- Si `LOCAL_JUDGE_ENABLED` no es `true`, no se llama al servicio local.
- Si falta `LOCAL_JUDGE_BASE_URL`, el Local Judge se considera deshabilitado.
- `LOCAL_JUDGE_TIMEOUT_MS` debe ser menor al timeout del request upstream.
- `LOCAL_JUDGE_FAIL_OPEN=true` significa: si Local Judge y fallback externo fallan, continuar con `LOG` salvo que regex/pattern haya decidido `BLOCK` antes.

Toda env nueva debe documentarse también en `.env.example` y spec 07 cuando se implemente.

---

## Internal contracts

### `LocalJudgeRequest`

```json
{
  "trace_id": "01HXYZ",
  "org_id": "demo",
  "integration": "claude-code",
  "wire_api": "anthropic_messages",
  "model_requested": "claude-sonnet-4-6",
  "normalized_request": {
    "system": "...",
    "messages": [
      { "role": "user", "content": "..." }
    ],
    "tools": []
  },
  "deterministic_signals": [
    {
      "type": "SECRET_PATTERN",
      "path": "$.messages[0].content",
      "span": { "start": 10, "end": 42 },
      "confidence": 1.0
    }
  ],
  "candidate_policies": [
    {
      "id": "policy_123",
      "slug": "no_customer_names",
      "action": "REDACT",
      "layer": "nl",
      "rule": "No enviar nombres de clientes reales al LLM."
    }
  ]
}
```

### `LocalJudgeResponse`

```json
{
  "decision": "REDACT",
  "confidence": 0.94,
  "risk_type": "SECRET_LEAK",
  "severity": "HIGH",
  "matched_policy_ids": ["policy_123"],
  "explanation": "The prompt includes a value that looks like a secret.",
  "redaction_targets": [
    {
      "path": "$.messages[0].content",
      "span": { "start": 10, "end": 42 },
      "replacement_type": "SECRET"
    }
  ],
  "model_version": "qwen3-4b-localjudge-prompt-v1"
}
```

### Decision enum interno

```text
LOG | WARN | BLOCK | REDACT | ESCALATE
```

`ESCALATE` nunca sale por headers, API pública ni DB como `action` final.

---

## Runtime flow

```text
incoming request
  ↓
normalize request by wire API
  ↓
run regex/pattern deterministic checks
  ↓
if deterministic BLOCK → enforce immediately
  ↓
if LOCAL_JUDGE_ENABLED → call LocalJudgeClient
  ↓
validate JSON response
  ↓
if invalid/timeout/error → fallback external judge
  ↓
if response.decision == ESCALATE → fallback external judge
  ↓
if confidence below threshold → fallback external judge
  ↓
if accepted → map local decision to PolicyHit/action
  ↓
resolveAction(BLOCK > REDACT > WARN > LOG)
  ↓
apply enforcement and persist interaction
```

---

## Fallback policy

| Caso | Resultado |
|---|---|
| Local Judge disabled | Flujo actual sin cambios. |
| Local Judge timeout | Fallback a JudgeProvider externo. |
| Local Judge JSON inválido | Fallback a JudgeProvider externo + warning sanitizado. |
| `ESCALATE` | Fallback a JudgeProvider externo. |
| Confidence `< LOCAL_JUDGE_CONFIDENCE_THRESHOLD` | Fallback a JudgeProvider externo. |
| High-risk con confidence baja | Fallback obligatorio. |
| Fallback externo falla | Fail-open `LOG` si no hubo decisión determinística previa. |
| Regex/pattern decide `BLOCK` | No llamar al Local Judge. |

---

## REDACT enforcement

El Local Judge solo devuelve `redaction_targets`. El interceptor:

1. valida que cada `path` exista;
2. valida que `span.start/end` estén dentro del string;
3. rechaza targets superpuestos o inconsistentes;
4. aplica replacement determinístico: `[REDACTED:<replacement_type>]`;
5. persiste prompt ya redactado;
6. nunca loguea el valor original.

Si targets son inválidos pero la decisión es `REDACT`, el interceptor debe escalar a Haiku o degradar a `BLOCK` para casos high severity. No debe reenviar payload sensible sin resolver.

---

## Data model / logging

Sin exigir migración inmediata, la implementación debe poder registrar:

```json
{
  "judge_source": "local_judge",
  "judge_model_version": "qwen3-4b-localjudge-prompt-v1",
  "risk_type": "SECRET_LEAK",
  "severity": "HIGH",
  "confidence": 0.94,
  "local_judge_latency_ms": 72,
  "fallback_used": false,
  "fallback_reason": null
}
```

Si la tabla `interactions` no tiene columnas dedicadas, usar campo JSON existente si lo hay; si no, crear migración desde `web/prisma/` en PR separado.

---

## Acceptance Criteria

- [ ] El interceptor puede activar/desactivar Local Judge por env sin cambiar código.
- [ ] El flujo actual sigue funcionando si `LOCAL_JUDGE_ENABLED=false`.
- [ ] Un `LOG` local forwardea el request al upstream.
- [ ] Un `BLOCK` local devuelve respuesta sintética compatible con el wire API.
- [ ] Un `WARN` local forwardea y persiste warning.
- [ ] Un `REDACT` local aplica redacción determinística antes de forwardear.
- [ ] `ESCALATE`, baja confianza, timeout y JSON inválido llaman al JudgeProvider externo.
- [ ] `ESCALATE` no aparece como acción pública ni persistida en `interactions.action`.
- [ ] `latency_by_layer.local_judge` queda disponible para evaluación.
- [ ] Tests cubren happy path, timeout, JSON inválido, low confidence, REDACT inválido y fallback.

---

## Tasks

- [ ] **T1 — Config del Local Judge.** Agregar settings/env con defaults seguros. Done: config deshabilitada por default y documentada.
- [ ] **T2 — Normalizador de request.** Convertir Anthropic/OpenAI-compatible payloads a `normalized_request`. Done: fixtures de ambos wire APIs pasan tests.
- [ ] **T3 — Cliente HTTP.** Implementar `LocalJudgeClient` con timeout, parse JSON y errores tipados. Done: tests mockean success/timeout/invalid JSON.
- [ ] **T4 — Schema validation.** Validar response con Pydantic/Zod equivalente Python. Done: responses inválidas no afectan enforcement.
- [ ] **T5 — Integración en cascada.** Insertar Local Judge después de deterministic checks y antes de JudgeProvider externo. Done: flujo actual se mantiene con feature flag off.
- [ ] **T6 — Mapping a PolicyHit.** Convertir respuesta local aceptada a hits/acción existentes. Done: `resolveAction` no necesita conocer provider internals.
- [ ] **T7 — REDACT deterministic.** Aplicar redaction targets validados sobre payload normalizado/original. Done: no se loguean secretos originales.
- [ ] **T8 — Persistencia y métricas.** Registrar source/model/confidence/risk/latency/fallback. Done: dataset offline puede comparar decisiones.
- [ ] **T9 — Tests de cascada.** Cubrir acciones y fallback. Done: suite interceptor verde sin credenciales reales.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Romper compatibilidad con rutas existentes | Feature flag off por default y tests con fixtures reales de Anthropic/OpenAI-compatible. |
| Latencia extra cuando Local Judge falla | Timeout corto y fallback medido. |
| REDACT inválido deja pasar secretos | Validación estricta; high severity inválido escala o bloquea. |
| Confundir `LOG` con auditoría pasiva | Documentar que en esta POC `LOG` es allow/pass público y también genera audit trail. |
| Drift entre contrato runtime y training | Versionar schema/prompt y compartir fixtures con specs 19–20. |
