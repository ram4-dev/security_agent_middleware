#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dataset_common import read_jsonl, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create teacher-label JSONL. v1 supports offline labels from expected values only."
    )
    parser.add_argument("--in", dest="input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--offline-from-expected",
        action="store_true",
        help="Use expected labels as teacher_label for safe local bootstrapping.",
    )
    args = parser.parse_args()

    if not args.offline_from_expected:
        raise SystemExit(
            "Online teacher labeling is intentionally not wired yet. "
            "Use --offline-from-expected for local bootstrap, or implement a secret-safe JudgeProvider call."
        )

    rows = []
    for case in read_jsonl(args.input):
        rows.append(
            {
                "case_id": case["case_id"],
                "teacher": "offline_expected_bootstrap",
                "teacher_label": case["expected"],
                "review_required": bool(case["expected"].get("critical")),
            }
        )
    write_jsonl(args.out, rows)
    print(f"Wrote {len(rows)} teacher-label rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
