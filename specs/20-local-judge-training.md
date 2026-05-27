# 20 — Local Judge Training Pipeline

> Pasos de implementación para preparar, entrenar, evaluar y versionar un modelo especializado de Tranquera. La estrategia acordada es **prompting primero**; el fine-tuning se activa solo si el benchmark de spec 19 no alcanza los gates o si se necesita bajar latencia/costo manteniendo calidad.

---

## Estado actual

Pendiente. No hay pipeline de entrenamiento. Esta spec define el camino completo desde datos curados hasta modelo candidato deployable, sin asumir que el fine-tuning es obligatorio para la primera POC.

## Decisión corta

Implementar un pipeline staged:

```text
Golden dataset → prompting baseline → error analysis → SFT/LoRA dataset → training → eval gates → model card → registry → shadow deploy
```

Primero se mide prompting-only. Si no pasa gates, se entrena con SFT vía LoRA/QLoRA sobre el mejor modelo candidato.

---

## Goals

- Definir todos los pasos necesarios para entrenar un Local Judge especializado.
- Mantener dataset, prompt, modelo base y métricas versionadas.
- Usar Haiku como teacher, pero con revisión humana en casos críticos.
- Entrenar con salida JSON estricta y explicaciones seguras.
- Evaluar el modelo entrenado contra el mismo golden dataset de spec 19.
- Producir artifacts reproducibles: adapter/checkpoint, model card, eval report y deploy manifest.

## Non-Goals

- No entrenar con datos reales no redactados.
- No hacer DPO/preference tuning en v1.
- No auto-promover modelos a producción sin gates.
- No usar training para cambiar las acciones públicas del producto.
- No mezclar entrenamiento con serving runtime.

---

## Training stages

### Stage 0 — Prompting baseline

Entrada: `golden_v1.jsonl` de spec 19.

Pasos:

1. Congelar prompt `local_judge_v1`.
2. Correr modelos candidatos sin fine-tuning.
3. Medir gates.
4. Hacer error analysis por risk type.
5. Decidir si hace falta SFT.

Salida:

- benchmark reports;
- error buckets;
- decisión `prompting_passed` o `training_required`.

### Stage 1 — Training dataset export

Entrada: golden + teacher labels + human curation.

Transformar cada caso a formato instruction-tuning:

```json
{
  "messages": [
    { "role": "system", "content": "<local_judge_system_prompt>" },
    { "role": "user", "content": "<serialized LocalJudgeRequest>" },
    { "role": "assistant", "content": "{\"decision\":\"REDACT\",...}" }
  ],
  "metadata": {
    "case_id": "secret_leak_0001",
    "risk_type": "SECRET_LEAK",
    "critical": true,
    "dataset_version": "golden_v1"
  }
}
```

Reglas:

- La respuesta assistant debe ser JSON válido.
- La explicación no debe repetir secretos ni PII.
- Casos ambiguos deben enseñar `ESCALATE`, no forzar falsa seguridad.
- REDACT debe enseñar targets, no payload completo sanitizado.

### Stage 2 — SFT con LoRA/QLoRA

Default: LoRA/QLoRA por eficiencia.

Candidatos:

1. Qwen3-4B-Instruct-2507
2. Llama 3.2 3B Instruct
3. Gemma 3 4B IT
4. Phi-3 Mini

Training framework sugerido:

- Hugging Face `transformers` + `trl` + `peft`;
- `bitsandbytes` si se usa QLoRA;
- Weights & Biases opcional, deshabilitable;
- seed fija y config YAML versionada.

### Stage 3 — Post-train evaluation

El checkpoint entrenado debe correr contra:

- `golden_v1` completo;
- holdout si existe;
- red-team mini set;
- smoke fixtures de runtime.

Debe superar los gates de spec 19 y no empeorar critical misses.

### Stage 4 — Model packaging

Artifacts mínimos:

```text
artifacts/local-judge/<run_id>/
├── adapter/                 # LoRA/QLoRA adapter o merged model pointer
├── training_config.yaml
├── dataset_manifest.json
├── eval_report.json
├── model_card.md
└── deploy_manifest.json
```

### Stage 5 — Registry + shadow deploy

Un modelo entrenado solo puede pasar a runtime si:

- tiene model card;
- tiene eval report con gates;
- tiene checksum/artifact URI;
- fue probado en Local Judge Service;
- entra primero en shadow mode o canary.

---

## Repository layout target

```text
training/local-judge/
├── README.md
├── configs/
│   ├── qwen3_4b_lora_v1.yaml
│   └── llama32_3b_lora_v1.yaml
├── scripts/
│   ├── prepare_sft_dataset.py
│   ├── train_lora.py
│   ├── merge_adapter.py
│   ├── evaluate_checkpoint.py
│   └── make_model_card.py
├── templates/
│   └── model_card.md
└── reports/
```

Si se prefiere evitar una carpeta nueva, estos scripts pueden vivir bajo `scripts/local-judge/`, pero el pipeline de training debe quedar separado del interceptor.

---

## Training config example

```yaml
run_id: qwen3-4b-localjudge-sft-v1
base_model: Qwen/Qwen3-4B-Instruct-2507
prompt_version: local_judge_v1
dataset:
  train: datasets/local-judge/train_v1.jsonl
  eval: datasets/local-judge/golden_v1.jsonl
  manifest: datasets/local-judge/manifest_v1.json
method:
  type: qlora
  lora_r: 16
  lora_alpha: 32
  lora_dropout: 0.05
training:
  epochs: 3
  learning_rate: 0.0002
  batch_size: 4
  gradient_accumulation_steps: 8
  max_seq_length: 8192
  seed: 22
output:
  artifact_dir: artifacts/local-judge/qwen3-4b-localjudge-sft-v1
```

---

## Data preparation rules

- Deduplicar casos por hash del request normalizado.
- Separar train/eval/holdout sin leakage por template family.
- Balancear risk types para no sobre-entrenar `LOG`.
- Oversample de críticos permitido, pero reportarlo en manifest.
- Mantener `ESCALATE` como clase explícita para incertidumbre.
- REDACT examples deben tener spans verificables.
- No incluir valores que parezcan secretos reales; correr secret scan sobre dataset.

---

## Evaluation gates for trained model

Mínimo igual a spec 19:

| Métrica | Gate |
|---|---:|
| JSON parse success rate | `>= 99.5%` |
| Critical miss rate | `0` en golden crítico v1 |
| REDACT target accuracy | `>= 97%` |
| False positive rate benignos | `<= 5%` |
| Escalation rate | `<= 20%` |
| P95 latency served via vLLM | menor que Haiku baseline |
| Regression vs prompting baseline | no peor en critical cases |

---

## Model card required fields

- Base model and license.
- Training method and config.
- Dataset versions and sources.
- Known limitations.
- Risk taxonomy version.
- Evaluation metrics.
- Critical misses observed.
- Recommended confidence thresholds.
- Approved serving engine/version.
- Whether model is allowed for shadow/canary/prod.

---

## Commands target

```bash
python training/local-judge/scripts/prepare_sft_dataset.py \
  --golden datasets/local-judge/golden_v1.jsonl \
  --out datasets/local-judge/train_v1.jsonl

python training/local-judge/scripts/train_lora.py \
  --config training/local-judge/configs/qwen3_4b_lora_v1.yaml

python training/local-judge/scripts/evaluate_checkpoint.py \
  --checkpoint artifacts/local-judge/qwen3-4b-localjudge-sft-v1 \
  --dataset datasets/local-judge/golden_v1.jsonl

python training/local-judge/scripts/make_model_card.py \
  --artifact artifacts/local-judge/qwen3-4b-localjudge-sft-v1
```

---

## Acceptance Criteria

- [ ] Prompting baseline se corre antes de entrenar.
- [ ] Existe export SFT desde dataset curado.
- [ ] Configs de training son versionadas y reproducibles.
- [ ] Training no requiere secretos en repo.
- [ ] Checkpoint/adapters se guardan con manifest y checksums.
- [ ] Evaluación post-train usa los mismos gates de spec 19.
- [ ] Model card se genera antes de cualquier deploy.
- [ ] Ningún modelo entrenado se promueve sin shadow/canary.

---

## Tasks

- [ ] **T1 — Prompting baseline gate.** Documentar y automatizar decisión `training_required`. Done: no se entrena por intuición.
- [ ] **T2 — SFT export.** Convertir golden/labels a instruction JSONL. Done: cada sample tiene assistant JSON válido.
- [ ] **T3 — Data QA.** Dedup, split, balance y secret scan. Done: manifest reporta composición y no hay secretos válidos.
- [ ] **T4 — Training configs.** Crear configs para Qwen y Llama baseline. Done: configs tienen seed y artifact_dir.
- [ ] **T5 — LoRA/QLoRA trainer.** Script de entrenamiento reproducible. Done: produce adapter/checkpoint local.
- [ ] **T6 — Checkpoint eval.** Evaluar checkpoint contra golden/holdout. Done: reporte con gates.
- [ ] **T7 — Model card.** Generar model card desde config + report. Done: artifact tiene documentación mínima.
- [ ] **T8 — Deploy manifest.** Crear manifest consumible por spec 21. Done: incluye model_version, prompt_version, checksum y serving requirements.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Overfitting al dataset sintético | Holdout por template family y red-team mini set. |
| Teacher bias de Haiku | Human review de críticos y ambiguous; no usar Haiku como verdad absoluta. |
| Fine-tuning empeora JSON | Gate de parse success más alto que baseline y guided decoding en serving. |
| Licencia del modelo base incompatible | Model card debe registrar licencia antes de entrenar. |
| Costos/GPU fuera de alcance | LoRA/QLoRA, batch chico y prompting-first para evitar training innecesario. |
| Modelo memoriza secretos sintéticos | Usar fake values y no entrenar con secretos reales. |
