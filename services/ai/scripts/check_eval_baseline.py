#!/usr/bin/env python3
"""Fail if the latest offline eval scored below the recorded baseline.

    python -m eval.harness --offline --full ; python scripts/check_eval_baseline.py

`make eval` exits non-zero whenever any golden question fails, which is the
normal state (77 questions have no page to link). The regression gate is the
per-scorer score, compared with eval/baseline.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    baseline = {k: v for k, v in json.loads((ROOT / "eval" / "baseline.json").read_text()).items()
                if not k.startswith("_")}
    reports = sorted((ROOT / "eval" / "reports").glob("eval-*.json"))
    if not reports:
        print("no eval report found — run: python -m eval.harness --offline --full")
        return 2
    scores = json.loads(reports[-1].read_text())["summary"]["by_scorer"]
    failed = False
    for scorer, minimum in baseline.items():
        score = scores.get(scorer)
        ok = score is not None and score + 1e-9 >= minimum
        failed |= not ok
        print(f"{'ok ' if ok else 'LOW'}  {scorer:<22} {score!s:>6}  (baseline {minimum})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
