#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[3]
LOCAL_JUDGE_SCRIPTS = ROOT / "scripts" / "local-judge"
sys.path.insert(0, str(LOCAL_JUDGE_SCRIPTS))

from dataset_common import make_local_judge_request, read_jsonl, score_predictions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a Local Judge LoRA adapter against JSONL cases.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--base-model", default="Qwen/Qwen3-4B-Instruct-2507")
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--model-version", default="qwen3-4b-localjudge-sft-v0")
    parser.add_argument("--limit", type=int, default=None, help="Optional smoke limit.")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--load-in-4bit", action="store_true", default=True)
    args = parser.parse_args()

    cases = read_jsonl(args.dataset)
    if args.limit is not None:
        cases = cases[: args.limit]

    model, tokenizer = _load_model(args)
    predictions = [
        _run_case(
            case,
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
        )
        for case in cases
    ]
    scored = score_predictions(cases, predictions)
    report = {
        "run_id": f"{int(time.time())}-{args.model_version}",
        "dataset_version": args.dataset.stem,
        "model_version": args.model_version,
        "base_model": args.base_model,
        "adapter": str(args.adapter),
        "metrics": scored["metrics"],
        "gates": scored["gates"],
        "failed_cases": scored["failed_cases"],
        "recommendation": scored["recommendation"],
        "predictions": predictions,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["metrics", "gates", "recommendation"]}, indent=2, sort_keys=True))
    print(f"Wrote report to {args.out}")
    return 0


def _load_model(args: argparse.Namespace) -> tuple[Any, Any]:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(args.adapter, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = None
    if args.load_in_4bit:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    base = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=quantization_config,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base, args.adapter)
    model.eval()
    return model, tokenizer


def _run_case(
    case: dict[str, Any],
    *,
    model: Any,
    tokenizer: Any,
    max_new_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    import torch

    started = time.perf_counter()
    payload = make_local_judge_request(case)
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
    ]
    inputs = _tokenize_messages(tokenizer, messages)
    inputs = {key: value.to(model.device) for key, value in inputs.items()}
    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0,
            temperature=temperature if temperature > 0 else None,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    prompt_len = inputs["input_ids"].shape[-1]
    generated_ids = output_ids[0][prompt_len:]
    raw = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
    latency_ms = int((time.perf_counter() - started) * 1000)
    parsed, error = _parse_json_object(raw)
    ok = isinstance(parsed, dict) and parsed.get("decision") is not None
    return {
        "case_id": case["case_id"],
        "ok": ok,
        "status_code": 200 if ok else 422,
        "latency_ms": latency_ms,
        "output": parsed if ok else None,
        "raw_output": raw[:2000],
        "error": error if not ok else None,
    }


def _tokenize_messages(tokenizer: Any, messages: list[dict[str, str]]) -> dict[str, Any]:
    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
    prompt = "\n".join(f"{message['role'].upper()}: {message['content']}" for message in messages)
    prompt += "\nASSISTANT:"
    return tokenizer(prompt, return_tensors="pt")


def _parse_json_object(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None, None if isinstance(parsed, dict) else "json_not_object"
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None, "no_json_object"
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None, None if isinstance(parsed, dict) else "json_not_object"
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error: {exc}"


def _system_prompt() -> str:
    return (ROOT / "local-judge" / "prompts" / "local_judge_v1.md").read_text(encoding="utf-8").strip()


if __name__ == "__main__":
    raise SystemExit(main())
