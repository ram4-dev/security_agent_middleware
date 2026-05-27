#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dataset_common import read_jsonl, validate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Local Judge JSONL dataset.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--taxonomy", required=False, type=Path)
    args = parser.parse_args()

    cases = read_jsonl(args.dataset)
    result = validate_dataset(cases)
    if not result.ok:
        for error in result.errors:
            print(error, file=sys.stderr)
        return 1
    print(f"OK: {args.dataset} ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
