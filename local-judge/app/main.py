from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from .config import settings
from .parser import ModelOutputError, error_payload, parse_model_output
from .prompt import build_messages
from .schemas import LocalJudgeRequest, MetadataResponse
from .vllm_client import VllmClient, VllmClientError, get_default_vllm_client

logger = logging.getLogger("local_judge.main")

app = FastAPI(title="Tranquera Local Judge", version="0.1.0")


def get_vllm_client() -> VllmClient:
    return get_default_vllm_client()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(client: Annotated[VllmClient, Depends(get_vllm_client)]):
    if await client.is_ready():
        return {"status": "ready"}
    return JSONResponse({"status": "not_ready"}, status_code=503)


@app.get("/v1/metadata", response_model=MetadataResponse)
async def metadata() -> MetadataResponse:
    return MetadataResponse(
        service="tranquera-local-judge",
        model=settings.local_judge_vllm_model,
        prompt_version=settings.local_judge_prompt_version,
        risk_taxonomy_version=settings.local_judge_risk_taxonomy_version,
    )


@app.post("/v1/judge")
async def judge(
    request: LocalJudgeRequest,
    client: Annotated[VllmClient, Depends(get_vllm_client)],
):
    try:
        raw_output = await client.complete(build_messages(request))
        response = parse_model_output(
            raw_output,
            default_model_version=f"{settings.local_judge_vllm_model}:{settings.local_judge_prompt_version}",
        )
    except VllmClientError as exc:
        logger.warning("model_unavailable trace=%s error=%s", request.trace_id, exc)
        return JSONResponse(error_payload("model_unavailable", request.trace_id), status_code=503)
    except ModelOutputError as exc:
        logger.warning("invalid_model_output trace=%s error=%s", request.trace_id, exc)
        return JSONResponse(
            error_payload("invalid_model_output", request.trace_id),
            status_code=503,
        )

    return response.model_dump(mode="json")
