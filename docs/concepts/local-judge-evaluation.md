# Local Judge Evaluation Plan

> Spec conceptual para construir el dataset, baseline y benchmark que determinan si el Specialized Local Judge puede reemplazar a Haiku en la mayoría de requests runtime.

---

## Estado actual

Conceptual. La POC debe arrancar con dataset sintético + curado, sin datos reales, y usar Haiku como baseline/teacher. El objetivo no es elegir el “mejor modelo general”, sino medir desempeño en el dominio de Tranquera.

---

## Decisión corta

Evaluar modelos chicos instruction-tuned de 3B–5B contra un golden dataset versionado. El baseline es el flujo actual `deterministic checks + Haiku`. La POC es exitosa si evita llamar a Haiku en al menos 80% de los casos sin aumentar misses críticos.

---

## Goals

- Construir un golden dataset sintético + curado para tráfico LLM-bound.
- Medir modelos candidatos con el mismo contrato interno.
- Comparar contra `deterministic checks + Haiku`.
- Medir calidad, latencia, parseabilidad JSON, costo y redacción.
- Seleccionar 1–2 modelos finalistas para una spec técnica o POC implementable.

## Non-Goals

- No usar logs reales no redactados.
- No hacer fine-tuning como primer paso obligatorio.
- No optimizar para benchmarks genéricos.
- No introducir DPO/preference tuning hasta tener evidencia de necesidad.
- No declarar reemplazo total de Haiku.

---

## Modelos candidatos iniciales

| Modelo | Por qué entra | Riesgo a medir |
|---|---|---|
| Qwen3-4B-Instruct-2507 | Buen candidato por instruction following, código, contexto y JSON. | Latencia real y serving necesario para P95. |
| Llama 3.2 3B Instruct | Baseline liviano con tooling amplio. | Puede quedarse corto en casos contextuales complejos. |
| Gemma 3 4B IT | Alternativa fuerte de 4B con buen perfil general. | Revisar licencia/terms y costo de capacidades no necesarias. |
| Phi-3 Mini | Liviano y atractivo legalmente. | Puede requerir más adaptación para security judging. |

La selección final se decide por métricas de Tranquera, no por ranking externo.

---

## Dataset inicial

El dataset debe representar requests estructurados hacia LLMs. Cada caso debe incluir:

- input normalizado conceptual;
- señales determinísticas disponibles;
- label esperado;
- risk type;
- severity;
- decisión esperada (`LOG`, `WARN`, `BLOCK`, `REDACT` o `ESCALATE` esperado para baja confianza);
- explicación esperada corta;
- si aplica, targets de redacción esperados;
- marca de caso crítico o no crítico.

### Taxonomía mínima

- `SECRET_LEAK`
- `PII_LEAK`
- `PROMPT_INJECTION`
- `POLICY_BYPASS`
- `DATA_EXFILTRATION`
- `DESTRUCTIVE_ACTION`
- `UNSAFE_TOOL_USE`
- `CREDENTIAL_ABUSE`
- `PRIVATE_CODE_LEAK`
- `BENIGN_REQUEST`

### Composición sugerida para POC

| Grupo | Cantidad mínima | Nota |
|---|---:|---|
| Benignos | 50 | Evitar falsos positivos obvios. |
| Secrets/credentials | 50 | API keys, tokens, private keys, `.env`. |
| PII | 40 | Casos LATAM: DNI, CUIT/RUT, teléfonos, emails. |
| Prompt injection / bypass | 50 | Instrucciones adversariales y evasión de policies. |
| Exfiltración / private code | 40 | Código propietario, paths internos, repos privados. |
| Tool/destructive actions | 30 | Shell, filesystem, red, comandos irreversibles. |
| Ambiguos | 30 | Casos donde escalar a Haiku es correcto. |
| REDACT | 40 | Casos con targets verificables. |

Total inicial sugerido: ~330 casos. Puede achicarse para smoke, pero el golden dataset debe cubrir todos los risk types.

---

## Haiku como teacher

Haiku se usa para:

- generar labels iniciales;
- resolver casos ambiguos;
- producir explicación esperada;
- comparar agreement;
- crear variantes adversariales.

Pero Haiku no es verdad absoluta. Los casos críticos requieren revisión humana puntual antes de entrar al golden dataset.

---

## Métricas de éxito

| Métrica | Target POC | Por qué importa |
|---|---:|---|
| Haiku avoidance rate | `>= 80%` | Valida ahorro de latencia/costo. |
| Critical miss rate | cercano a `0` | Evita falsa sensación de seguridad. |
| JSON parse success rate | alto / cercano a `100%` | El interceptor necesita contrato confiable. |
| Agreement con Haiku | alto en riesgo bajo/medio | Mide similitud con baseline actual. |
| Latency P50/P95 | menor que path Haiku | Justifica local judge runtime. |
| Escalation rate | `<= 20%` | Debe sostener la meta de avoidance. |
| REDACT target accuracy | alta | REDACT es más difícil que BLOCK/WARN. |
| False positive rate en benignos | bajo | Protege UX del dev. |
| Costo por 1.000 requests | menor que baseline | Valida beneficio operativo. |

---

## Baseline

Comparar siempre contra:

```text
Baseline actual: deterministic checks + Haiku
POC propuesta: deterministic checks + local judge + Haiku fallback
```

Preguntas que debe responder el benchmark:

- ¿Cuántas requests evita mandar a Haiku?
- ¿Cuánto baja P50/P95?
- ¿Cuánto baja costo por 1.000 requests?
- ¿Cuántas decisiones coinciden con Haiku?
- ¿Cuántos casos críticos se escapan?
- ¿Cuántos outputs son JSON parseable?
- ¿Cuántas redacciones son correctas?

---

## Flujo de evaluación conceptual

1. Crear casos sintéticos por taxonomía.
2. Pedir labels iniciales a Haiku.
3. Revisar manualmente casos críticos y ambiguos.
4. Versionar golden dataset.
5. Ejecutar cada modelo candidato con el mismo prompt/contrato.
6. Validar JSON estricto.
7. Calcular métricas.
8. Comparar contra baseline.
9. Seleccionar finalistas.
10. Decidir si hace falta fine-tuning.

---

## Tasks

- [ ] **T1 — Diseñar formato del golden dataset.** Definir columnas/campos, naming y ejemplos mínimos. Done: un caso por risk type se puede expresar sin ambigüedad.
- [ ] **T2 — Crear seed sintético inicial.** Generar ~330 casos cubriendo la taxonomía. Done: dataset no contiene datos reales ni secretos válidos.
- [ ] **T3 — Labeling con Haiku.** Obtener labels/explicaciones iniciales. Done: cada caso tiene decisión, risk type, severity y confidence baseline.
- [ ] **T4 — Revisión humana de casos críticos.** Validar false negatives potenciales y ambigüedades. Done: golden dataset queda curado.
- [ ] **T5 — Benchmark runner conceptual.** Definir cómo correr modelos con mismo input y capturar output/latencia. Done: resultados son comparables entre modelos.
- [ ] **T6 — Métricas y reporte.** Calcular avoidance, agreement, misses, parse rate, REDACT accuracy, P50/P95 y costo. Done: reporte permite elegir 1–2 finalistas.
- [ ] **T7 — Recomendación de siguiente etapa.** Decidir prompting-only vs fine-tuning. Done: decisión basada en evidencia, no intuición.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Dataset sintético demasiado artificial | Incluir variantes realistas de harnesses y casos ambiguos; sumar logs redactados recién en etapa posterior. |
| Labels de Haiku inconsistentes | Revisión humana en críticos y agreement por mayoría si se generan múltiples labels. |
| Optimizar solo accuracy | Reportar critical miss rate, false positives, REDACT accuracy y parseability por separado. |
| Comparar modelos con prompts distintos | Congelar contrato/prompt por corrida; versionar cambios. |
| Medir latencia sin hardware objetivo | Separar benchmark funcional de benchmark de serving real. |
| Secretos reales en fixtures | Usar tokens falsos con prefijos inválidos y documentar que no son credenciales. |

---

## Preguntas abiertas para diseño técnico

1. ¿Dónde vive físicamente el dataset: repo, bucket privado o DB?
2. ¿Cuál es el formato exacto: JSONL, parquet, fixtures TS/Python?
3. ¿Qué motor de inferencia permite medir todos los modelos de forma comparable?
4. ¿Qué límite de contexto y truncado se usa en evaluación?
5. ¿Qué umbral exacto define “critical miss cercano a cero”?
6. ¿Qué costo operativo se asigna a hardware local/cloud para comparar contra Haiku?
7. ¿Qué revisión humana mínima es aceptable antes de llamar “golden” al dataset?
