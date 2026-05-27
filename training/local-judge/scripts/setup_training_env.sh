#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-dry-run}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TRAINING_DIR="$ROOT_DIR/training/local-judge"

case "$MODE" in
  dry-run)
    VENV_DIR="${VENV_DIR:-$TRAINING_DIR/.venv-dry-run}"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip
    "$VENV_DIR/bin/python" -m pip install -r "$TRAINING_DIR/requirements-dry-run.txt"
    echo "Dry-run environment ready: $VENV_DIR"
    echo "Use: $VENV_DIR/bin/python training/local-judge/scripts/train_lora.py --config training/local-judge/configs/qwen3_4b_lora_v0.yaml --dry-run"
    ;;
  cuda)
    VENV_DIR="${VENV_DIR:-$TRAINING_DIR/.venv-cuda}"
    CUDA_INDEX_URL="${CUDA_INDEX_URL:-https://download.pytorch.org/whl/cu121}"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip
    "$VENV_DIR/bin/python" -m pip install torch --index-url "$CUDA_INDEX_URL"
    "$VENV_DIR/bin/python" -m pip install -r "$TRAINING_DIR/requirements-cuda.txt"
    echo "CUDA training environment ready: $VENV_DIR"
    echo "Use: $VENV_DIR/bin/python training/local-judge/scripts/train_lora.py --config training/local-judge/configs/qwen3_4b_lora_v0.yaml"
    ;;
  *)
    echo "Usage: $0 [dry-run|cuda]" >&2
    exit 2
    ;;
esac
