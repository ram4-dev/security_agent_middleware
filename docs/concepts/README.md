# Concept specs — Tranquera

Specs conceptuales para explorar cambios de arquitectura antes de convertirlos en specs canónicas de implementación.

## Quick path

1. Leer la spec conceptual principal: [`specialized-local-judge.md`](./specialized-local-judge.md).
2. Revisar el plan de evaluación: [`local-judge-evaluation.md`](./local-judge-evaluation.md).
3. Para implementación, seguir las specs canónicas 17–21 en [`../../specs/`](../../specs/).

## Índice

| Doc | Para qué sirve | Estado |
|---|---|---|
| [`specialized-local-judge.md`](./specialized-local-judge.md) | Define el objetivo, alcance, arquitectura runtime y tareas para incorporar un judge local especializado dentro del interceptor. | conceptual |
| [`local-judge-evaluation.md`](./local-judge-evaluation.md) | Define dataset, baseline, métricas y benchmark para comparar modelos 3B–5B contra Layer 1 + Haiku. | conceptual |

## Decisiones tomadas en esta etapa

| Tema | Decisión |
|---|---|
| Ubicación de los docs | Mantenerlos en `docs/concepts/`, no como specs canónicas todavía. |
| Nivel de detalle | Conceptual + tasks concretas, sin cerrar schemas técnicos finales. |
| Serving del judge | Servicio separado llamado por el interceptor. |
| Acciones públicas | Mantener `BLOCK | REDACT | WARN | LOG`; `LOG` representa allow/pass en el contrato público. |
| Escalación | `ESCALATE` queda como estado técnico interno, no como acción pública. |
| Redacción | El proxy/interceptor redacta de forma determinística; el judge devuelve señalización/spans/paths. |
| Dataset POC | Dataset sintético + curado, versionado y sin datos reales. |

## Specs canónicas derivadas

| Spec | Tema |
|---|---|
| [`../../specs/17-local-judge-runtime.md`](../../specs/17-local-judge-runtime.md) | Integración runtime en el interceptor. |
| [`../../specs/18-local-judge-service.md`](../../specs/18-local-judge-service.md) | Servicio separado con vLLM. |
| [`../../specs/19-local-judge-dataset-eval.md`](../../specs/19-local-judge-dataset-eval.md) | Dataset sintético + curado, teacher labels y benchmark. |
| [`../../specs/20-local-judge-training.md`](../../specs/20-local-judge-training.md) | Pipeline completo de entrenamiento, empezando por prompting baseline. |
| [`../../specs/21-local-judge-deployment-observability.md`](../../specs/21-local-judge-deployment-observability.md) | Registry, shadow/canary, métricas y rollback. |

## Criterio para seguir evolucionando

Las specs 17–21 son ahora la fuente canónica para implementación. Este directorio queda como contexto conceptual y no debe contradecirlas.
