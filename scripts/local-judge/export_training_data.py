#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dataset_common import make_local_judge_request, read_jsonl, write_jsonl

SYSTEM_PROMPT_PLACEHOLDER = "<local_judge_system_prompt>"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export curated Local Judge cases to SFT messages JSONL.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    rows = []
    for case in read_jsonl(args.dataset):
        expected = dict(case["expected"])
        expected.setdefault("matched_policy_ids", [])
        expected.setdefault("explanation", _safe_explanation(expected))
        expected.setdefault("model_version", "training_target")
        response = _training_response(expected, case["input"]["normalized_request"])
        rows.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_PLACEHOLDER},
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
                            response,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    },
                ],
                "metadata": {
                    "case_id": case["case_id"],
                    "risk_type": case["expected"]["risk_type"],
                    "critical": case["expected"].get("critical", False),
                    "dataset_version": args.dataset.stem,
                },
            }
        )
    write_jsonl(args.out, rows)
    print(f"Wrote {len(rows)} SFT rows to {args.out}")
    return 0


def _training_response(expected: dict, normalized_request: dict) -> dict:
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


def _safe_explanation(expected: dict) -> str:
    risk = expected["risk_type"].lower().replace("_", " ")
    return f"The request matches {risk} and should be handled with {expected['decision']}."


def _text_at_path(normalized_request: dict, path: str) -> str:
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
