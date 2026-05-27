# Local Judge dataset

Dataset y reportes para evaluar el Specialized Local Judge de Tranquera.

## Quick path

```bash
# Validar golden dataset
python scripts/local-judge/validate_dataset.py \
  --dataset datasets/local-judge/golden_v1.jsonl \
  --taxonomy datasets/local-judge/taxonomy.yaml

# Generar seed sintético reproducible
python scripts/local-judge/generate_synthetic_dataset.py \
  --taxonomy datasets/local-judge/taxonomy.yaml \
  --out datasets/local-judge/generated/synthetic_seed_v1.jsonl

# Generar más datos sintéticos con un modelo open-source local vía vLLM/OpenAI-compatible.
# No requiere API key si el server local no requiere auth.
python scripts/local-judge/generate_synthetic_with_gpt.py \
  --provider local-os \
  --base-url http://localhost:8000/v1 \
  --model Qwen/Qwen3-4B-Instruct-2507 \
  --per-risk 100 \
  --out datasets/local-judge/generated/synthetic_local_os_v1.jsonl

# Alternativa OpenCode Go. Si tu endpoint requiere auth, seteá OPENCODE_API_KEY fuera del chat.
python scripts/local-judge/generate_synthetic_with_gpt.py \
  --provider opencode-go \
  --per-risk 100 \
  --out datasets/local-judge/generated/synthetic_opencode_go_v1.jsonl

# Alternativa Codex/OpenAI. Requiere OPENAI_API_KEY fuera del chat.
python scripts/local-judge/generate_synthetic_with_gpt.py \
  --provider codex \
  --per-risk 100 \
  --out datasets/local-judge/generated/synthetic_codex_v1.jsonl

# Correr benchmark contra un Local Judge Service levantado
python scripts/local-judge/run_benchmark.py \
  --dataset datasets/local-judge/golden_v1.jsonl \
  --endpoint http://localhost:8088/v1/judge \
  --model-version local-judge-v1 \
  --out datasets/local-judge/reports/benchmark_local_v1.json
```

## Reglas de seguridad

- No guardar secretos reales.
- Usar valores `fake_`, `test_`, `invalid_` o dominios reservados (`example.com`).
- No derivar casos desde logs productivos sin redacción y aprobación explícita.
- El golden dataset debe pasar `validate_dataset.py` antes de usarse para benchmark o training.
- Para generación con providers hosted, el script lee la key desde el entorno pero nunca la imprime. No pegar keys en chat ni commitearlas.
- Preferencia actual: `--provider local-os` con un modelo open-source servido localmente; `codex` queda como alternativa si hay key y presupuesto.

## Versiones

- `golden_v1.jsonl`: smoke golden inicial, mínimo un caso por risk type.
- `generated/synthetic_seed_v1.jsonl`: salida reproducible del generador sintético.
- `reports/`: resultados de benchmark versionables cuando sean relevantes para decisiones.
