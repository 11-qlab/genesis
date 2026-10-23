#!/usr/bin/env python3
"""T13 rich — compare greedy / revision-basic(2) / revision-rich(2).

Benchmark: error_recovery.jsonl (20 items). Items commonly fail on
missing-file errors; the rich revision prompt's "create the file first"
suggestion is directly actionable there.

Runs each condition through `agi eval run --seed all`, so seeding,
per-item isolation, and contamination detection are inherited from the
tested EvalRunner path.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

CONDITIONS = [
    ("greedy", ["--strategy", "greedy"]),
    ("revision-basic(2)",
     ["--strategy", "revision", "--revision-signal", "basic"]),
    ("revision-rich(2)",
     ["--strategy", "revision", "--revision-signal", "rich"]),
]
BENCH = "bench/error_recovery.jsonl"


def run(flags: list[str], tag: str) -> dict | None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(REPO, "src")
    env["AGI_STORAGE_PATH"] = f"/tmp/agi_rev_{tag}_{os.getpid()}.sqlite3"
    env["AGI_FS_ROOT"] = f"/tmp/agi_rev_{tag}_{os.getpid()}_ws"
    os.makedirs(env["AGI_FS_ROOT"], exist_ok=True)
    cmd = [
        sys.executable, "-m", "agi", "eval", "run",
        "--bench", BENCH,
        "--seed", "all",
        "--delay-ms", "3000",
    ] + flags
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        print(f"  {tag}: unparseable. stdout={r.stdout[:400]!r}")
        print(f"  {tag}: stderr={r.stderr[:400]!r}")
        return None


def main() -> int:
    print(f"benchmark: {BENCH}")
    print()
    results: dict[str, dict] = {}
    for label, flags in CONDITIONS:
        print(f"=== {label} ===")
        data = run(flags, label)
        if data is None:
            results[label] = {}
            continue
        results[label] = data
        print(f"  accuracy:     {data.get('accuracy')}")
        print(f"  passed/total: {data.get('passed')}/{data.get('total')}")
        print(f"  contaminated: {data.get('contaminated')}")
        print(f"  rate_limited: {data.get('rate_limited_items')}")
        print()

    print("=" * 62)
    print(f"{'condition':<24} {'passed':>6} {'total':>6} {'accuracy':>9}")
    print("-" * 62)
    for label, _ in CONDITIONS:
        d = results.get(label) or {}
        p_ = d.get("passed", "?")
        t_ = d.get("total", "?")
        a_ = d.get("accuracy")
        acc_str = f"{a_:.4f}" if isinstance(a_, (int, float)) else "?"
        print(
            f"{label:<24} {p_!s:>6} {t_!s:>6} {acc_str:>9}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
