#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
DATASET_VERSION="${DATASET_VERSION:-training_candidate_v1}"
CONFIG="${CONFIG:-training/local-judge/configs/qwen3_4b_lora_v0.yaml}"
SOURCE_DATASET="${SOURCE_DATASET:-datasets/local-judge/generated/synthetic_opencode_go_quality_v1.jsonl}"
OUT_DIR="${OUT_DIR:-datasets/local-judge/training}"

$PYTHON_BIN training/local-judge/scripts/prepare_sft_dataset.py \
  --input "$SOURCE_DATASET" \
  --out-dir "$OUT_DIR" \
  --dataset-version "$DATASET_VERSION" \
  --balance min

$PYTHON_BIN training/local-judge/scripts/train_lora.py \
  --config "$CONFIG" \
  --dry-run

if [[ "${TRAIN:-0}" == "1" ]]; then
  $PYTHON_BIN training/local-judge/scripts/train_lora.py \
    --config "$CONFIG"
else
  echo "Dry-run complete. Set TRAIN=1 to start LoRA/QLoRA training."
fi
