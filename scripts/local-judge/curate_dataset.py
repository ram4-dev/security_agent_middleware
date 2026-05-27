#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dataset_common import read_jsonl, validate_dataset, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze a validated Local Judge dataset as a curated golden file.")
    parser.add_argument("--in", dest="input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--manifest", required=False, type=Path)
    args = parser.parse_args()

    cases = read_jsonl(args.input)
    result = validate_dataset(cases)
    if not result.ok:
        raise SystemExit("dataset is invalid:\n" + "\n".join(result.errors))

    curated = []
    for case in cases:
        row = dict(case)
        row["split"] = "golden"
        curated.append(row)
    write_jsonl(args.out, curated)

    manifest = {
        "source": str(args.input),
        "out": str(args.out),
        "cases": len(curated),
        "critical_cases": sum(1 for case in curated if case["expected"].get("critical")),
        "requires_human_review": [
            case["case_id"] for case in curated if case["expected"].get("critical")
        ],
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
