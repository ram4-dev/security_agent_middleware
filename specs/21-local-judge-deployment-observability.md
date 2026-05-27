# 21 — Local Judge Deployment & Observability

> Cómo desplegar, versionar, monitorear y operar el Local Judge en Tranquera sin promover modelos inseguros ni perder trazabilidad.

---

## Estado actual

Pendiente. No existe aún deployment separado del Local Judge ni model registry. Esta spec conecta runtime (17), service (18), dataset/eval (19) y training (20) con operación segura.

## Decisión corta

Desplegar Local Judge como servicio separado, con vLLM como serving default, versionado explícito de modelo/prompt/dataset y rollout por etapas: local smoke → shadow mode → canary → enabled por org.

---

## Goals

- Definir artifact registry mínimo para modelos/prompts/datasets.
- Desplegar Local Judge sin acoplarlo al proceso del interceptor.
- Medir latencia, avoidance, fallback, parse errors y misses.
- Permitir shadow mode antes de enforcement real.
- Soportar rollback rápido a `LOCAL_JUDGE_ENABLED=false`.
- Evitar logs con secretos/PII.

## Non-Goals

- No construir plataforma MLOps completa.
- No auto-entrenar con tráfico productivo.
- No hacer per-tenant model fine-tuning.
- No reemplazar el JudgeProvider externo como fallback.
- No agregar UI avanzada de model registry en v1.

---

## Deployment modes

### Mode 0 — Local dev

```text
interceptor local → local-judge-service → vLLM local/Ollama-equivalent smoke
```

Sirve para contrato y smoke, no para métricas finales.

### Mode 1 — Benchmark environment

```text
benchmark runner → local-judge-service → vLLM on GPU host
```

Sirve para medir modelos y training artifacts sin afectar tráfico real.

### Mode 2 — Shadow mode

```text
production/staging interceptor → current enforcement path
                         ↘ local judge decision logged only
```

El Local Judge decide, pero no modifica enforcement. Permite comparar contra Haiku y reglas actuales.

### Mode 3 — Canary enforcement

Activar Local Judge para una org/demo o porcentaje bajo de tráfico. Fallback externo activo.

### Mode 4 — Default runtime

Local Judge habilitado por default, con fallback externo y kill switch.

---

## Model registry mínimo

Puede empezar como archivo versionado en repo + artifacts externos:

```text
models/local-judge/registry.yaml
```

Ejemplo:

```yaml
models:
  - model_version: qwen3-4b-localjudge-prompt-v1
    base_model: Qwen/Qwen3-4B-Instruct-2507
    prompt_version: local_judge_v1
    dataset_version: golden_v1
    artifact_uri: hf://tranquera/qwen3-4b-localjudge-prompt-v1
    checksum: sha256:...
    status: shadow-approved
    eval_report: datasets/local-judge/reports/benchmark_qwen3_4b_v1.json
    serving:
      engine: vllm
      min_gpu_memory_gb: 16
      max_context_tokens: 8192
    gates:
      json_parse_success_rate: 0.997
      critical_miss_rate: 0
      haiku_avoidance_rate: 0.82
```

Estados permitidos:

```text
candidate → eval-passed → shadow-approved → canary → production → deprecated
```

---

## Runtime config

```env
LOCAL_JUDGE_ENABLED=false
LOCAL_JUDGE_SHADOW_MODE=true
LOCAL_JUDGE_BASE_URL=http://local-judge:8088
LOCAL_JUDGE_MODEL_VERSION=qwen3-4b-localjudge-prompt-v1
LOCAL_JUDGE_ROLLOUT_PERCENT=0
LOCAL_JUDGE_ALLOWED_ORGS=demo
LOCAL_JUDGE_KILL_SWITCH=false
```

Reglas:

- `LOCAL_JUDGE_KILL_SWITCH=true` deshabilita todo aunque el resto esté enabled.
- `SHADOW_MODE=true` nunca cambia la acción final.
- `ROLLOUT_PERCENT` solo aplica si shadow false y enabled true.
- `ALLOWED_ORGS` permite canary por tenant/demo.

---

## Observability events

Cada request debe poder registrar:

```json
{
  "trace_id": "01HXYZ",
  "org_id": "demo",
  "local_judge_enabled": true,
  "local_judge_shadow": false,
  "local_judge_model_version": "qwen3-4b-localjudge-prompt-v1",
  "local_judge_decision": "REDACT",
  "final_action": "REDACT",
  "risk_type": "SECRET_LEAK",
  "severity": "HIGH",
  "confidence": 0.94,
  "fallback_used": false,
  "fallback_reason": null,
  "latency_by_layer": {
    "regex": 3,
    "pattern": 8,
    "local_judge": 72,
    "haiku": null,
    "upstream": 900
  }
}
```

No loguear prompt completo ni valores redactados originales.

---

## Core metrics

| Métrica | Uso |
|---|---|
| `local_judge_requests_total` | Volumen del servicio. |
| `local_judge_latency_ms` | P50/P95/P99. |
| `local_judge_parse_errors_total` | Salud del contrato JSON. |
| `local_judge_timeouts_total` | Señal de serving/hardware. |
| `local_judge_fallback_total` | Cuánto se sigue usando Haiku. |
| `haiku_avoidance_rate` | KPI principal de POC. |
| `local_vs_fallback_disagreement_rate` | Calidad en shadow mode. |
| `critical_shadow_miss_total` | Bloqueador de rollout. |
| `redact_invalid_targets_total` | Calidad de REDACT. |
| `kill_switch_activated` | Incidente operativo. |

---

## Promotion gates

### candidate → eval-passed

- Gates de spec 19 pasan.
- Model card existe.
- Licencia revisada.

### eval-passed → shadow-approved

- Local Judge Service smoke real OK.
- P95 menor que baseline Haiku en benchmark environment.
- Parse errors bajo umbral.

### shadow-approved → canary

- Shadow mode corre N requests sin critical misses confirmados.
- Disagreement con fallback revisado.
- REDACT targets inválidos bajo umbral.

### canary → production

- Canary por org/demo sin incidentes.
- Kill switch probado.
- Rollback documentado.

---

## Rollback

Rollback inmediato:

```env
LOCAL_JUDGE_KILL_SWITCH=true
```

Rollback normal:

```env
LOCAL_JUDGE_ENABLED=false
LOCAL_JUDGE_SHADOW_MODE=false
```

Rollback de modelo:

1. Cambiar `LOCAL_JUDGE_MODEL_VERSION` a versión anterior aprobada.
2. Reiniciar Local Judge Service o recargar config.
3. Verificar `/v1/metadata`.
4. Confirmar caída de parse errors/timeouts.

---

## Security and privacy

- Logs nunca incluyen body completo.
- Errores nunca incluyen prompts ni secrets.
- Dataset productivo no se genera automáticamente desde logs.
- Shadow mode debe registrar decisión, no contenido sensible.
- Artifacts de training con datos derivados deben tener acceso restringido.
- No imprimir env vars ni tokens en scripts.

---

## Acceptance Criteria

- [ ] Existe registry mínimo de modelos/prompts/datasets.
- [ ] Local Judge puede correr en shadow mode sin afectar enforcement.
- [ ] Canary por org o porcentaje funciona.
- [ ] Kill switch deshabilita Local Judge sin deploy de código.
- [ ] Métricas principales están disponibles.
- [ ] Rollback está documentado y probado.
- [ ] Logs y errores no exponen secretos.
- [ ] Ningún modelo entra a canary sin eval report/model card.

---

## Tasks

- [ ] **T1 — Registry YAML.** Crear formato y validación de `models/local-judge/registry.yaml`. Done: modelos tienen status y eval report linkeado.
- [ ] **T2 — Shadow mode.** Agregar modo donde Local Judge corre pero no decide enforcement. Done: se persiste comparación con acción final.
- [ ] **T3 — Rollout controls.** Implementar allowed orgs, percent rollout y kill switch. Done: config permite canary seguro.
- [ ] **T4 — Metrics.** Emitir latencia, fallback, parse errors, avoidance y invalid redactions. Done: dashboard/logs permiten evaluar POC.
- [ ] **T5 — Deployment docs.** Documentar contenedor, vLLM host, healthchecks y envs. Done: una persona puede levantar staging.
- [ ] **T6 — Rollback drill.** Probar deshabilitar Local Judge y volver al flujo actual. Done: runbook con evidencia.
- [ ] **T7 — Promotion checklist.** Checklist candidate→shadow→canary→prod. Done: no hay promoción manual sin gates.
- [ ] **T8 — Privacy audit.** Revisar logs, errores y reports. Done: no hay prompt completo ni secretos originales.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Modelo inseguro llega a enforcement | Gates, shadow mode, canary y kill switch. |
| GPU/serving inestable genera latencia | Timeouts cortos y fallback externo. |
| Observabilidad filtra datos sensibles | Structured logs sin body y sanitización de explanations. |
| Registry manual se desactualiza | Validación en CI y model card obligatoria. |
| Rollback lento en incidente | Kill switch por env/config operacional. |
