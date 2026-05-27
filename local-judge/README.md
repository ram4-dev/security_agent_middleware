# Tranquera Local Judge

Servicio separado para el Specialized Local Judge de Tranquera.

## Quick path

```bash
cd local-judge
uvicorn app.main:app --host 0.0.0.0 --port 8088
```

## Endpoints

- `GET /healthz` — proceso vivo.
- `GET /readyz` — vLLM responde en `/models`.
- `GET /v1/metadata` — modelo, prompt y taxonomía activos.
- `POST /v1/judge` — contrato consumido por el interceptor.

## Config

Ver `specs/18-local-judge-service.md` para el contrato completo.

```env
LOCAL_JUDGE_VLLM_BASE_URL=http://localhost:8000/v1
LOCAL_JUDGE_VLLM_MODEL=Qwen/Qwen3-4B-Instruct-2507
LOCAL_JUDGE_PROMPT_VERSION=local_judge_v1
LOCAL_JUDGE_JSON_MODE=true
```

## Seguridad

El servicio no aplica enforcement ni persiste datos. Solo clasifica y devuelve JSON validado. No loguea prompts ni outputs completos.
