# Specialized Local Judge

> Spec conceptual para incorporar un judge local chico, rápido y especializado dentro del flujo de Tranquera. El objetivo es reducir llamadas runtime a Haiku sin bajar la calidad de decisiones de seguridad.

---

## Estado actual

Conceptual. La arquitectura actual de Tranquera usa checks determinísticos y judge externo multiprovider/Haiku para decisiones contextuales. Esta propuesta introduce un **Specialized Local Judge** entre esas capas: más expresivo que regex/patterns, más barato/privado que Haiku.

> Nota de naming: en la documentación canónica, **Layer 2** ya significa `Interceptor Engine`. Para evitar ambigüedad, este doc llama a la nueva pieza **Specialized Local Judge** o **judge local**, no “Layer 2” como capa de producto.

---

## Decisión corta

Agregar un servicio separado de judge local que el interceptor llama después de los checks determinísticos y antes de Haiku. El servicio devuelve una decisión estructurada. El interceptor mantiene el control del enforcement: bloquea, advierte, loguea, redacta o escala a Haiku.

```text
Harness
  ↓
Tranquera Interceptor
  ↓
Deterministic checks: regex / pattern / fast detectors
  ↓
Specialized Local Judge service
  ↓                 ↘ low confidence / ambiguous
Decision              Haiku fallback
  ↓
Target LLM or synthetic BLOCK response
```

---

## Contexto

El path actual resuelve casos obvios con reglas determinísticas y delega comprensión contextual a Haiku. Funciona, pero tiene tres costos:

1. **Latencia**: cada caso contextual espera un proveedor externo.
2. **Costo marginal**: cada evaluación con Haiku cuesta por request.
3. **Exposición**: parte del tráfico sensible puede salir a un tercero para ser evaluado.

La hipótesis es que un modelo local de 3B–5B, especializado en tráfico LLM-bound, puede resolver la mayoría de casos comunes con JSON estricto y escalar a Haiku solo cuando no tenga suficiente confianza.

---

## Goals

- Reducir llamadas runtime a Haiku en al menos 80% durante la POC.
- Mantener `BLOCK | REDACT | WARN | LOG` como acciones públicas del producto.
- Modelar `ESCALATE` como estado interno del judge local, no como acción pública.
- Permitir `REDACT` sin que el modelo generativo modifique libremente el payload completo.
- Registrar decisiones con explicación corta y auditable.
- Comparar modelos candidatos con métricas específicas de Tranquera, no benchmarks genéricos.

## Non-Goals

- No definir todavía el schema final del JSON de entrada/salida.
- No elegir modelo final en esta etapa.
- No implementar auto-learning en producción.
- No reemplazar completamente Haiku.
- No usar logs reales sin redacción como dataset inicial.
- No cambiar las acciones públicas actuales ni los enums de DB por esta POC.
- No resolver multi-tenancy avanzado ni versionado completo de modelos/policies.

---

## Alcance conceptual

### Deterministic checks

Siguen siendo la primera línea. Detectan señales rápidas y obvias:

- secretos y API keys;
- tokens/JWTs;
- PII evidente;
- paths internos o archivos sensibles;
- patrones simples de exfiltración;
- comandos destructivos conocidos.

Sus resultados pasan como señales estructuradas al judge local.

### Specialized Local Judge

Servicio separado, model-agnostic, llamado por el interceptor. Su único trabajo es juzgar tráfico hacia LLMs; no conversa con usuarios ni genera respuestas libres.

Optimiza para:

- latencia baja;
- JSON estricto;
- explicaciones cortas;
- buena comprensión contextual;
- baja tasa de escalación;
- alta parseabilidad;
- decisiones conservadoras ante riesgo alto.

### Haiku fallback

Haiku queda para:

- baja confianza del judge local;
- casos ambiguos;
- riesgo alto no resuelto localmente;
- baseline de calidad;
- labeler/teacher del dataset.

---

## Decisiones soportadas

| Decisión interna | Acción pública | Qué significa |
|---|---|---|
| `LOG` | `LOG` | El tráfico puede continuar. En esta POC `LOG` representa el “allow/pass” público sin agregar una acción nueva. |
| `WARN` | `WARN` | El tráfico continúa, pero queda marcado para revisión o alerta. |
| `BLOCK` | `BLOCK` | El request no llega al LLM; el interceptor sintetiza una respuesta bloqueada compatible con el harness. |
| `REDACT` | `REDACT` | El request continúa después de que el interceptor aplique redacción determinística. |
| `ESCALATE` | ninguna | Estado técnico interno: el interceptor pide decisión a Haiku. |

---

## Riesgos iniciales a detectar

La POC debe cubrir una taxonomía acotada:

| Risk type | Ejemplo |
|---|---|
| `SECRET_LEAK` | API keys, tokens, private keys, `.env`. |
| `PII_LEAK` | DNI, emails, teléfonos, datos personales sensibles. |
| `PROMPT_INJECTION` | Instrucciones para ignorar políticas o revelar secretos. |
| `POLICY_BYPASS` | Intentos explícitos de evadir Tranquera o reglas corporativas. |
| `DATA_EXFILTRATION` | Pedidos de empaquetar/subir/transferir información interna. |
| `DESTRUCTIVE_ACTION` | Acciones irreversibles o comandos destructivos. |
| `UNSAFE_TOOL_USE` | Uso riesgoso de tools, shell o red. |
| `CREDENTIAL_ABUSE` | Uso indebido o request de credenciales. |
| `PRIVATE_CODE_LEAK` | Envío de código propietario o repos privados. |
| `BENIGN_REQUEST` | Caso seguro que no debería ser bloqueado. |

---

## Contrato conceptual

El contrato final queda para una spec técnica. Conceptualmente, el judge recibe:

- metadata del harness/integración;
- request normalizado;
- contenido relevante del mensaje;
- señales de deterministic checks;
- policies activas aplicables;
- contexto mínimo de org/dev si corresponde;
- límites de redacción permitidos.

Y responde JSON estricto con:

```json
{
  "decision": "REDACT",
  "confidence": 0.94,
  "risk_type": "SECRET_LEAK",
  "severity": "HIGH",
  "explanation": "The request appears to include an API key that should not be sent to the target LLM.",
  "redaction_targets": [
    {
      "path": "$.messages[2].content",
      "span": { "start": 42, "end": 78 },
      "replacement_type": "SECRET"
    }
  ],
  "should_escalate_to_haiku": false
}
```

Regla importante: el judge **no** devuelve el payload completo reescrito. El interceptor aplica la redacción.

---

## User Stories

- **Como empresa**, quiero que la mayoría de decisiones de seguridad no salgan a un proveedor externo.
- **Como admin**, quiero ver una explicación breve y auditable de por qué se bloqueó, redactó o advirtió un request.
- **Como dev**, quiero que las decisiones benignas agreguen la menor latencia posible.
- **Como equipo de producto**, quiero comparar modelos por calidad real en Tranquera, no por benchmarks generales.

---

## Acceptance Criteria conceptuales

- [ ] El interceptor puede llamar a un servicio separado de judge local.
- [ ] El servicio devuelve JSON parseable en el golden dataset.
- [ ] `LOG`, `WARN`, `BLOCK` y `REDACT` se mapean sin cambiar las acciones públicas del producto.
- [ ] `ESCALATE` dispara fallback a Haiku sin persistirse como acción pública.
- [ ] `REDACT` devuelve targets suficientes para que el interceptor aplique redacción determinística.
- [ ] Las decisiones quedan logueadas con `risk_type`, `severity`, `confidence`, `judge_source` y explicación corta.
- [ ] La POC mide avoidance, latencia, costo, agreement y critical miss rate.

---

## Tasks

- [ ] **T1 — Definir contrato interno mínimo.** Especificar campos conceptuales de entrada/salida para el judge local. Done: contrato documentado con ejemplos y mapeo de acciones.
- [ ] **T2 — Diseñar integración interceptor → judge service.** Definir endpoint, timeout, retry, error handling y fallback a Haiku. Done: secuencia runtime y fallbacks quedan claros.
- [ ] **T3 — Definir mapping de decisiones.** Formalizar `LOG` como allow/pass público y `ESCALATE` como estado interno. Done: no requiere migración de acciones públicas.
- [ ] **T4 — Diseñar REDACT determinístico.** Definir cómo el judge expresa targets y cómo el interceptor aplica reemplazos. Done: no hay payload libre reescrito por el modelo.
- [ ] **T5 — Definir observabilidad.** Campos mínimos para auditar decisiones y comparar judge local vs Haiku. Done: eventos permiten evaluación offline.
- [ ] **T6 — Preparar spec técnica posterior.** Promover a spec canónica cuando se cierren schemas, thresholds y serving engine. Done: lista de bloqueadores resuelta.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Falsa sensación de seguridad | Medir critical miss rate por taxonomía, no solo accuracy promedio. |
| JSON inválido | Validación estricta, retries acotados, fallback a Haiku y evaluar constrained decoding. |
| Latencia peor a la esperada | Benchmark P50/P95 con hardware objetivo y payloads representativos. |
| REDACT incorrecto | El modelo solo señala targets; el interceptor aplica transformaciones determinísticas. |
| Confusión de capas | Documentar que el judge local vive dentro del Interceptor Engine, no reemplaza la Layer 2 del producto. |
| Dependencia del teacher | Labels de Haiku se validan contra golden dataset curado y revisión humana puntual. |

---

## Preguntas abiertas para la spec técnica

1. ¿Cuál es el schema exacto del request normalizado?
2. ¿Qué policies activas se incluyen en el input del judge y con qué límite de tokens?
3. ¿Qué threshold de confidence dispara `ESCALATE`?
4. ¿Qué timeout máximo se acepta antes de fallback a Haiku?
5. ¿Qué motor de inferencia se benchmarkea primero: vLLM, SGLang, llama.cpp u Ollama?
6. ¿Qué hardware mínimo se usa para medir P95?
7. ¿Cómo se versionan prompts, modelos y datasets?
8. ¿Cómo se evita que explicaciones auditables incluyan secretos?
9. ¿Qué casos críticos tienen tolerancia casi cero a false negatives?
