#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from dataset_common import make_local_judge_request, post_json, read_jsonl, score_predictions


def run_case(case: dict[str, Any], *, endpoint: str, timeout_seconds: float) -> dict[str, Any]:
    payload = make_local_judge_request(case)
    status_code, response_payload, latency_ms = post_json(endpoint, payload, timeout_seconds)
    ok = status_code == 200 and isinstance(response_payload, dict) and "decision" in response_payload
    return {
        "case_id": case["case_id"],
        "ok": ok,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "output": response_payload if ok else None,
        "error": None if ok else response_payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark a Local Judge Service endpoint.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=20)
    args = parser.parse_args()

    cases = read_jsonl(args.dataset)
    predictions = [
        run_case(case, endpoint=args.endpoint, timeout_seconds=args.timeout_seconds) for case in cases
    ]
    scored = score_predictions(cases, predictions)
    report = {
        "run_id": f"{int(time.time())}-{args.model_version}",
        "dataset_version": args.dataset.stem,
        "model_version": args.model_version,
        "endpoint": args.endpoint,
        "metrics": scored["metrics"],
        "gates": scored["gates"],
        "failed_cases": scored["failed_cases"],
        "recommendation": scored["recommendation"],
        "predictions": predictions,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["metrics", "gates", "recommendation"]}, indent=2))
    print(f"Wrote report to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
