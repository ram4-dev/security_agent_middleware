#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[3]
LOCAL_JUDGE_SCRIPTS = ROOT / "scripts" / "local-judge"
sys.path.insert(0, str(LOCAL_JUDGE_SCRIPTS))

from dataset_common import make_local_judge_request, read_jsonl, validate_dataset, write_jsonl  # noqa: E402

DEFAULT_SYSTEM_PROMPT = ROOT / "local-judge" / "prompts" / "local_judge_v1.md"
RISK_ORDER = [
    "BENIGN_REQUEST",
    "SECRET_LEAK",
    "PII_LEAK",
    "PROMPT_INJECTION",
    "POLICY_BYPASS",
    "DATA_EXFILTRATION",
    "DESTRUCTIVE_ACTION",
    "UNSAFE_TOOL_USE",
    "CREDENTIAL_ABUSE",
    "PRIVATE_CODE_LEAK",
]
SECRETISH_PATTERNS = {
    "openai_real_prefix": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "aws_access_key_prefix": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_pat_prefix": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    "slack_token_prefix": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a curated, split SFT dataset for Tranquera Local Judge fine-tuning."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--dataset-version", default="training_candidate_v1")
    parser.add_argument("--system-prompt", type=Path, default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--seed", type=int, default=22)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument(
        "--balance",
        choices=["min", "none"],
        default="min",
        help="min down-samples every risk type to the smallest class size.",
    )
    args = parser.parse_args()

    _validate_ratios(args.train_ratio, args.validation_ratio, args.test_ratio)
    rows = read_jsonl(args.input)
    result = validate_dataset(rows)
    if not result.ok:
        raise SystemExit("input dataset failed validation:\n" + "\n".join(result.errors[:100]))

    secret_like = _find_secretish_rows(rows)
    if secret_like:
        sample = ", ".join(f"{case_id}:{kind}" for case_id, kind in secret_like[:20])
        raise SystemExit(f"input dataset contains real-looking secrets: {sample}")

    deduped, duplicate_ids = _dedupe_by_request(rows)
    selected, excluded_by_balance = _balance_rows(deduped, balance=args.balance, seed=args.seed)
    splits = _split_by_risk(
        selected,
        seed=args.seed,
        train_ratio=args.train_ratio,
        validation_ratio=args.validation_ratio,
    )

    system_prompt = args.system_prompt.read_text(encoding="utf-8").strip()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    case_paths: dict[str, str] = {}
    sft_paths: dict[str, str] = {}
    for split_name, split_rows in splits.items():
        case_rows = [_with_split(row, split_name) for row in split_rows]
        case_path = args.out_dir / f"{args.dataset_version}_{split_name}.jsonl"
        sft_path = args.out_dir / f"{args.dataset_version}_{split_name}.sft.jsonl"
        write_jsonl(case_path, case_rows)
        write_jsonl(sft_path, [_to_sft_row(row, system_prompt, args.dataset_version) for row in case_rows])
        case_paths[split_name] = str(case_path)
        sft_paths[split_name] = str(sft_path)

    manifest = _manifest(
        args=args,
        input_rows=rows,
        deduped_rows=deduped,
        selected_rows=selected,
        splits=splits,
        duplicate_ids=duplicate_ids,
        excluded_by_balance=excluded_by_balance,
        case_paths=case_paths,
        sft_paths=sft_paths,
    )
    manifest_path = args.out_dir / f"{args.dataset_version}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), **manifest["summary"]}, indent=2, sort_keys=True))
    return 0


def _validate_ratios(train: float, validation: float, test: float) -> None:
    if min(train, validation, test) <= 0:
        raise SystemExit("split ratios must be positive")
    if abs((train + validation + test) - 1.0) > 0.0001:
        raise SystemExit("split ratios must sum to 1.0")


def _dedupe_by_request(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    duplicate_ids: list[str] = []
    for row in rows:
        digest = _request_hash(row)
        if digest in seen:
            duplicate_ids.append(row["case_id"])
            continue
        seen.add(digest)
        deduped.append(row)
    return deduped, duplicate_ids


def _balance_rows(
    rows: list[dict[str, Any]], *, balance: str, seed: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_risk = _by_risk(rows)
    if set(by_risk) != set(RISK_ORDER):
        missing = sorted(set(RISK_ORDER) - set(by_risk))
        raise SystemExit(f"dataset missing risk types: {', '.join(missing)}")
    if balance == "none":
        return list(rows), {risk: 0 for risk in RISK_ORDER}
    target = min(len(by_risk[risk]) for risk in RISK_ORDER)
    selected: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    for risk in RISK_ORDER:
        ordered = _stable_shuffle(by_risk[risk], seed=seed, namespace=f"balance:{risk}")
        selected.extend(ordered[:target])
        excluded[risk] = len(ordered) - target
    return selected, excluded


def _split_by_risk(
    rows: list[dict[str, Any]], *, seed: int, train_ratio: float, validation_ratio: float
) -> dict[str, list[dict[str, Any]]]:
    splits: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    by_risk = _by_risk(rows)
    for risk in RISK_ORDER:
        ordered = _stable_shuffle(by_risk[risk], seed=seed, namespace=f"split:{risk}")
        total = len(ordered)
        train_count = int(total * train_ratio)
        validation_count = int(total * validation_ratio)
        # Keep at least one test case per risk when possible.
        if total >= 3 and total - train_count - validation_count == 0:
            train_count -= 1
        splits["train"].extend(ordered[:train_count])
        splits["validation"].extend(ordered[train_count : train_count + validation_count])
        splits["test"].extend(ordered[train_count + validation_count :])
    for split_name in splits:
        splits[split_name] = sorted(splits[split_name], key=lambda row: row["case_id"])
    return splits


def _to_sft_row(case: dict[str, Any], system_prompt: str, dataset_version: str) -> dict[str, Any]:
    expected = dict(case["expected"])
    expected.setdefault("matched_policy_ids", [])
    expected.setdefault("explanation", _safe_explanation(expected))
    expected.setdefault("model_version", "training_target")
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    make_local_judge_request(case),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    _training_response(expected, case["input"]["normalized_request"]),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ],
        "metadata": {
            "case_id": case["case_id"],
            "risk_type": case["expected"]["risk_type"],
            "decision": case["expected"]["decision"],
            "critical": case["expected"].get("critical", False),
            "split": case["split"],
            "dataset_version": dataset_version,
        },
    }


def _training_response(expected: dict[str, Any], normalized_request: dict[str, Any]) -> dict[str, Any]:
    redaction_targets = []
    for target in expected.get("redaction_targets", []):
        content = _text_at_path(normalized_request, target["path"])
        start = content.index(target["span_text"])
        redaction_targets.append(
            {
                "path": target["path"],
                "span": {"start": start, "end": start + len(target["span_text"])},
                "replacement_type": target["replacement_type"],
            }
        )
    return {
        "decision": expected["decision"],
        "confidence": 1.0,
        "risk_type": expected["risk_type"],
        "severity": expected["severity"],
        "matched_policy_ids": expected.get("matched_policy_ids", []),
        "explanation": expected["explanation"],
        "redaction_targets": redaction_targets,
        "model_version": expected["model_version"],
    }


def _manifest(
    *,
    args: argparse.Namespace,
    input_rows: list[dict[str, Any]],
    deduped_rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    splits: dict[str, list[dict[str, Any]]],
    duplicate_ids: list[str],
    excluded_by_balance: dict[str, int],
    case_paths: dict[str, str],
    sft_paths: dict[str, str],
) -> dict[str, Any]:
    split_counts = {
        split: {
            "total": len(rows),
            "by_risk_type": _risk_counts(rows),
            "by_decision": _decision_counts(rows),
        }
        for split, rows in splits.items()
    }
    return {
        "dataset_version": args.dataset_version,
        "source_dataset": _display_path(args.input),
        "system_prompt": _display_path(args.system_prompt),
        "seed": args.seed,
        "balance": args.balance,
        "split_ratios": {
            "train": args.train_ratio,
            "validation": args.validation_ratio,
            "test": args.test_ratio,
        },
        "summary": {
            "input_rows": len(input_rows),
            "deduped_rows": len(deduped_rows),
            "selected_rows": len(selected_rows),
            "train_rows": len(splits["train"]),
            "validation_rows": len(splits["validation"]),
            "test_rows": len(splits["test"]),
            "duplicates_removed": len(duplicate_ids),
            "secret_scan_issues": 0,
        },
        "input_counts": {
            "by_risk_type": _risk_counts(input_rows),
            "by_decision": _decision_counts(input_rows),
            "by_source": dict(sorted(Counter(row.get("source") for row in input_rows).items())),
        },
        "selected_counts": {
            "by_risk_type": _risk_counts(selected_rows),
            "by_decision": _decision_counts(selected_rows),
        },
        "split_counts": split_counts,
        "excluded_by_balance": excluded_by_balance,
        "duplicate_case_ids_removed": duplicate_ids[:100],
        "case_paths": {split: _display_path(Path(path)) for split, path in case_paths.items()},
        "sft_paths": {split: _display_path(Path(path)) for split, path in sft_paths.items()},
        "checksums": {
            **{f"cases_{split}": _file_sha256(Path(path)) for split, path in case_paths.items()},
            **{f"sft_{split}": _file_sha256(Path(path)) for split, path in sft_paths.items()},
        },
    }


def _with_split(row: dict[str, Any], split: str) -> dict[str, Any]:
    copied = dict(row)
    copied["split"] = split
    return copied


def _by_risk(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_risk: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_risk[row["expected"]["risk_type"]].append(row)
    return by_risk


def _risk_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {risk: count for risk, count in sorted(Counter(row["expected"]["risk_type"] for row in rows).items())}


def _decision_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {decision: count for decision, count in sorted(Counter(row["expected"]["decision"] for row in rows).items())}


def _stable_shuffle(rows: list[dict[str, Any]], *, seed: int, namespace: str) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: _hash_text(f"{seed}:{namespace}:{row['case_id']}"))


def _request_hash(row: dict[str, Any]) -> str:
    payload = make_local_judge_request(row)
    return _hash_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_secretish_rows(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for row in rows:
        flattened = json.dumps(row["input"]["normalized_request"], ensure_ascii=False)
        for name, pattern in SECRETISH_PATTERNS.items():
            if pattern.search(flattened):
                found.append((row["case_id"], name))
    return found


def _safe_explanation(expected: dict[str, Any]) -> str:
    risk = expected["risk_type"].lower().replace("_", " ")
    return f"The request matches {risk} and should be handled with {expected['decision']}."


def _text_at_path(normalized_request: dict[str, Any], path: str) -> str:
    normalized = path[2:] if path.startswith("$.") else path
    if not normalized.startswith("messages[") or not normalized.endswith("].content"):
        raise ValueError(f"unsupported training redaction path: {path}")
    index = int(normalized.removeprefix("messages[").removesuffix("].content"))
    content = normalized_request["messages"][index]["content"]
    if not isinstance(content, str):
        raise ValueError(f"training redaction path is not string content: {path}")
    return content


if __name__ == "__main__":
    raise SystemExit(main())
