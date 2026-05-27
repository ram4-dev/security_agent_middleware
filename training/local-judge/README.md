# Local Judge training

Pipeline de fine-tuning para el Specialized Local Judge de Tranquera.

## Estado v0

El primer candidato de training usa solo filas `synthetic_gpt` generadas con OpenCode Go y pasa por QA antes de exportarse a SFT.

```bash
python training/local-judge/scripts/prepare_sft_dataset.py \
  --input datasets/local-judge/generated/synthetic_opencode_go_quality_v1.jsonl \
  --out-dir datasets/local-judge/training \
  --dataset-version training_candidate_v1 \
  --balance min
```

Artifacts esperados:

- `datasets/local-judge/training/training_candidate_v1_train.jsonl`
- `datasets/local-judge/training/training_candidate_v1_validation.jsonl`
- `datasets/local-judge/training/training_candidate_v1_test.jsonl`
- `datasets/local-judge/training/training_candidate_v1_train.sft.jsonl`
- `datasets/local-judge/training/training_candidate_v1_validation.sft.jsonl`
- `datasets/local-judge/training/training_candidate_v1_test.sft.jsonl`
- `datasets/local-judge/training/training_candidate_v1_manifest.json`

## Setup local de validación

Este repo corre en macOS/arm64 sin CUDA, así que localmente usamos un entorno liviano para validar config/dataset sin bajar PyTorch ni modelos grandes:

```bash
./training/local-judge/scripts/setup_training_env.sh dry-run

training/local-judge/.venv-dry-run/bin/python \
  training/local-judge/scripts/train_lora.py \
  --config training/local-judge/configs/qwen3_4b_lora_v0.yaml \
  --dry-run
```

`ready_to_train: false` es esperado en este host si no hay CUDA.

## Setup GPU/CUDA

En una máquina con GPU NVIDIA:

```bash
./training/local-judge/scripts/setup_training_env.sh cuda

training/local-judge/.venv-cuda/bin/python \
  training/local-judge/scripts/train_lora.py \
  --config training/local-judge/configs/qwen3_4b_lora_v0.yaml
```

También hay imagen base:

```bash
docker build -f training/local-judge/Dockerfile.cuda -t tranquera-local-judge-train .
docker run --gpus all --rm -v "$PWD/artifacts:/workspace/security_agent_middleware/artifacts" tranquera-local-judge-train
```

## Configs

- `configs/qwen3_4b_lora_v0.yaml` — QLoRA full v0 sobre `Qwen/Qwen3-4B-Instruct-2507`.
- `configs/qwen3_4b_lora_debug.yaml` — smoke corto con `max_steps: 20` para validar la máquina GPU antes del run largo.

## Pipeline completo

```bash
PYTHON_BIN=training/local-judge/.venv-cuda/bin/python TRAIN=1 \
  ./training/local-judge/scripts/run_training_pipeline.sh
```

Sin `TRAIN=1`, el pipeline prepara datos y hace dry-run.

## Reglas

- No entrenar con filas que fallen secret scan.
- No mezclar `synthetic_variant` en el candidato principal.
- Mantener `test` como holdout: no usarlo para early stopping.
- Evaluar contra golden + holdout antes de cualquier shadow deploy.
