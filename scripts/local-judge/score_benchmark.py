#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dataset_common import read_jsonl, score_predictions


def main() -> int:
    parser = argparse.ArgumentParser(description="Score an existing Local Judge benchmark report.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", required=False, type=Path)
    args = parser.parse_args()

    cases = read_jsonl(args.dataset)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    scored = score_predictions(cases, report.get("predictions", []))
    report.update(scored)

    output = json.dumps({k: report[k] for k in ["metrics", "gates", "recommendation"]}, indent=2)
    print(output)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
