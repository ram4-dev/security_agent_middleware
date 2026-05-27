#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dataset_common import read_jsonl, validate_dataset, write_jsonl
from generate_synthetic_with_gpt import (
    PROVIDER_PRESETS,
    _build_user_prompt,
    _chat_completion,
    _count_risk,
    _read_api_key,
    _resolve_provider,
    _target_risk_types,
    validate_dataset as validate_cases,
)


@dataclass(frozen=True)
class BatchTask:
    task_index: int
    risk_type: str
    count: int
    batch_seed_ids: set[str]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Local Judge synthetic data with parallel OpenAI-compatible requests. "
            "Writes only after all returned rows validate, avoiding concurrent JSONL writes."
        )
    )
    parser.add_argument("--seed", type=Path, default=Path("datasets/local-judge/golden_v1.jsonl"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDER_PRESETS),
        default=os.getenv("SYNTH_PROVIDER", "local-os"),
    )
    parser.add_argument("--model", default=os.getenv("SYNTH_MODEL"))
    parser.add_argument("--base-url", default=os.getenv("SYNTH_BASE_URL"))
    parser.add_argument("--api-key-env", default=os.getenv("SYNTH_API_KEY_ENV"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--api-key-stdin",
        action="store_true",
        help="Read bearer API key from stdin instead of the environment. Safe for secure_exec.",
    )
    parser.add_argument("--auth", choices=["auto", "bearer", "none"], default=os.getenv("SYNTH_AUTH", "auto"))
    parser.add_argument("--risk-types", default=None, help="Comma-separated subset of risk types.")
    parser.add_argument("--per-risk", type=int, default=20)
    parser.add_argument(
        "--target-per-risk",
        type=int,
        default=None,
        help="Generate enough new rows to reach this total per selected risk type in --out.",
    )
    parser.add_argument(
        "--count-source",
        default=None,
        help="When using --target-per-risk, count only existing rows with this source value.",
    )
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--request-timeout-seconds", type=float, default=120)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--append", action="store_true")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Keep successful batches and exit 0 even if some parallel batches fail.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=1,
        help="Write validated progress after this many successful batches.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Stable id namespace for generated case ids. Defaults to p<unix time>.",
    )
    args = parser.parse_args()

    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")
    if args.checkpoint_every < 1:
        raise SystemExit("--checkpoint-every must be >= 1")

    provider = _resolve_provider(args)
    api_key = _read_api_key(provider, use_stdin=args.api_key_stdin, env_file=args.env_file)
    if provider["auth"] == "bearer" and not api_key:
        raise SystemExit(
            f"Missing {provider['api_key_env']}. Set it out-of-band; do not paste it into chat. "
            "For local open-source generation use --provider local-os or --auth none."
        )

    seed_cases = read_jsonl(args.seed) if args.seed.exists() else []
    base_rows = read_jsonl(args.out) if args.append and args.out.exists() else []
    existing_ids = {case["case_id"] for case in [*seed_cases, *base_rows]}
    target_risk_types = _target_risk_types(args.risk_types)
    tasks = _build_tasks(
        args=args,
        base_rows=base_rows,
        target_risk_types=target_risk_types,
        existing_ids=existing_ids,
    )

    run_id = args.run_id or f"p{int(time.time())}"
    generated: list[dict[str, Any]] = []
    rows = list(base_rows)
    failures: list[str] = []
    successful_batches = 0
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                _generate_batch_task,
                task=task,
                args=args,
                provider=provider,
                api_key=api_key,
                seed_cases=seed_cases,
                run_id=run_id,
            )
            for task in tasks
        ]
        for future in as_completed(futures):
            try:
                batch_rows = future.result()
            except BaseException as exc:  # noqa: BLE001 - worker may raise SystemExit.
                failures.append(str(exc))
                continue
            generated.extend(batch_rows)
            rows.extend(batch_rows)
            successful_batches += 1
            if successful_batches % args.checkpoint_every == 0:
                _validate_and_write(args.out, rows)

    rows = [*base_rows, *sorted(generated, key=lambda row: row["case_id"])]
    _validate_and_write(args.out, rows)
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "out": str(args.out),
                "provider": args.provider,
                "base_url": provider["base_url"],
                "model": provider["model"],
                "auth": provider["auth"],
                "workers": args.workers,
                "batch_size": args.batch_size,
                "batches": len(tasks),
                "successful_batches": successful_batches,
                "failed_batches": len(failures),
                "failures_sample": failures[:10],
                "generated": len(generated),
                "total": len(rows),
                "seconds": round(elapsed, 3),
                "rows_per_second": round(len(generated) / elapsed, 3) if elapsed > 0 else None,
                "target_per_risk": args.target_per_risk,
                "count_source": args.count_source,
                "risk_types": target_risk_types,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if failures and not args.allow_partial:
        raise SystemExit(f"{len(failures)} batch(es) failed; successful batches were checkpointed")
    return 0


def _validate_and_write(path: Path, rows: list[dict[str, Any]]) -> None:
    result = validate_dataset(rows)
    if not result.ok:
        errors = "\n".join(result.errors[:100])
        raise SystemExit(f"Generated dataset failed validation:\n{errors}")
    write_jsonl(path, rows)


def _build_tasks(
    *,
    args: argparse.Namespace,
    base_rows: list[dict[str, Any]],
    target_risk_types: list[str],
    existing_ids: set[str],
) -> list[BatchTask]:
    tasks: list[BatchTask] = []
    task_index = 0
    count_rows = (
        [row for row in base_rows if row.get("source") == args.count_source]
        if args.count_source
        else base_rows
    )
    for risk_type in target_risk_types:
        desired = args.per_risk
        if args.target_per_risk is not None:
            desired = max(0, args.target_per_risk - _count_risk(count_rows, risk_type))
        remaining = desired
        while remaining > 0:
            count = min(args.batch_size, remaining)
            tasks.append(
                BatchTask(
                    task_index=task_index,
                    risk_type=risk_type,
                    count=count,
                    batch_seed_ids=set(existing_ids),
                )
            )
            remaining -= count
            task_index += 1
    return tasks


def _generate_batch_task(
    *,
    task: BatchTask,
    args: argparse.Namespace,
    provider: dict[str, str | None],
    api_key: str | None,
    seed_cases: list[dict[str, Any]],
    run_id: str,
) -> list[dict[str, Any]]:
    last_error = "unknown"
    for attempt in range(1, args.max_retries + 1):
        prompt = _build_user_prompt(
            risk_type=task.risk_type,
            count=task.count,
            seed_cases=seed_cases,
            existing_ids=task.batch_seed_ids,
        )
        status, payload = _chat_completion(
            base_url=str(provider["base_url"]),
            api_key=api_key,
            model=str(provider["model"]),
            temperature=args.temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate synthetic evaluation data for Tranquera Local Judge. "
                        "Return ONLY valid JSON. Use only fake/test/invalid/example.com values."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            timeout_seconds=args.request_timeout_seconds,
        )
        if status != 200:
            last_error = f"provider HTTP {status}"
            time.sleep(min(2**attempt, 10))
            continue
        try:
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            cases = parsed["cases"]
            if not isinstance(cases, list):
                raise ValueError("cases is not a list")
            if len(cases) != task.count:
                raise ValueError(f"expected {task.count} cases, got {len(cases)}")
            normalized = [
                _normalize_generated_case(
                    case=case,
                    task=task,
                    run_id=run_id,
                    case_index=case_index,
                )
                for case_index, case in enumerate(cases, start=1)
            ]
            result = validate_cases(normalized)
            if not result.ok:
                raise ValueError("; ".join(result.errors[:10]))
            return normalized
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            time.sleep(min(2**attempt, 10))
    raise SystemExit(
        f"Could not generate valid {task.risk_type} batch {task.task_index} after retries: {last_error}"
    )


def _normalize_generated_case(
    *,
    case: dict[str, Any],
    task: BatchTask,
    run_id: str,
    case_index: int,
) -> dict[str, Any]:
    normalized = dict(case)
    normalized["case_id"] = (
        f"{task.risk_type.lower()}_opencode_parallel_{run_id}_{task.task_index:04d}_{case_index:02d}"
    )
    normalized["split"] = normalized.get("split") or "synthetic_seed"
    normalized["source"] = "synthetic_gpt"
    normalized["notes"] = normalized.get("notes") or "Synthetic OpenCode Go parallel generated case."
    return normalized


if __name__ == "__main__":
    raise SystemExit(main())
