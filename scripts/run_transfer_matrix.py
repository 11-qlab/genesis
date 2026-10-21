#!/usr/bin/env python3
"""
Real transfer matrix.

For each (source, target) pair: prepend k examples from source to
every goal in target, run target under greedy, record accuracy.

No code changes. The few-shot examples live in the goal string;
the planner sees them as part of the user message.

Note: with k=3, each target goal grows by ~600 chars. Fine for
120b-class models; watch 3B on-device runs for context overflow.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHES = [
    "bench/workspace_list.jsonl",
    "bench/error_recovery.jsonl",
    "bench/task_chain.jsonl",
    "bench/memory_search.jsonl",
]


def load_examples(bench_path, k):
    """Read first k items, synthesize (goal, steps) pairs."""
    ex = []
    with open(bench_path) as f:
        for i, line in enumerate(f):
            if i >= k:
                break
            if not line.strip():
                continue
            it = json.loads(line)
            goal = it.get("goal", "")
            tool = it.get("expect_tool") or "fs_read"
            seq = it.get("expect_subsequence") or [tool]
            steps = [{"id": f"s{j + 1}", "tool": t, "args": {}} for j, t in enumerate(seq)]
            ex.append({"goal": goal, "steps": steps})
    return ex


def build_augmented_bench(target_bench, examples, out_path):
    """Prepend few-shot prefix to every goal in target bench."""
    prefix = ""
    if examples:
        prefix = f"Here are {len(examples)} example plans for reference:\n"
        for i, ex in enumerate(examples, 1):
            prefix += (
                f"\nExample {i}:\n"
                f"  Goal: {ex['goal']}\n"
                f"  Plan: {json.dumps(ex['steps'])}\n"
            )
        prefix += "\nNow plan the following goal in the same style:\n"

    with open(target_bench) as f_in, open(out_path, "w") as f_out:
        for line in f_in:
            if not line.strip():
                continue
            it = json.loads(line)
            it["goal"] = prefix + it["goal"]
            f_out.write(json.dumps(it) + "\n")


def run_bench(bench, tag, delay_ms=1500):
    db = f"/tmp/agi_tm_{tag}.sqlite3"
    ws = f"/tmp/agi_tm_{tag}_ws"
    with contextlib.suppress(FileNotFoundError):
        os.remove(db)
    shutil.rmtree(ws, ignore_errors=True)

    env = {
        **os.environ,
        "AGI_STORAGE_PATH": db,
        "AGI_FS_ROOT": ws,
        "PYTHONPATH": "src",
    }
    args = [
        sys.executable, "-m", "agi", "eval", "run",
        "--bench", bench, "--seed", "all",
        "--strategy", "greedy", "--delay-ms", str(delay_ms),
    ]
    try:
        p = subprocess.run(
            args, cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=3600,
        )
        return json.loads(p.stdout)
    except Exception as e:
        print(f"  [!] {tag}: {type(e).__name__}: {e}", file=sys.stderr)
        return None
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.remove(db)
        shutil.rmtree(ws, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay-ms", type=int, default=1500)
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    os.chdir(ROOT)
    names = [Path(b).stem for b in BENCHES]

    ex_by_src = {name: load_examples(b, args.k) for name, b in zip(names, BENCHES, strict=False)}

    matrix = {}
    for src in names:
        row = {}
        for tgt, b in zip(names, BENCHES, strict=False):
            tag = f"{src}__{tgt}".replace("/", "_")
            aug_path = f"/tmp/agi_tm_aug_{tag}.jsonl"
            build_augmented_bench(b, ex_by_src[src], aug_path)
            print(f"  {src:>16} -> {tgt:<16} ...", end="", flush=True)
            d = run_bench(aug_path, tag, args.delay_ms)
            if d is None:
                row[tgt] = None
                print(" FAIL")
            else:
                row[tgt] = d["accuracy"]
                print(f" {d['accuracy']:.3f}")
            with contextlib.suppress(FileNotFoundError):
                os.remove(aug_path)
        matrix[src] = row

    print("\n=== TRANSFER MATRIX (rows = source few-shot, cols = target bench) ===")
    header = "  " + " " * 16 + "".join(f"{t:>16}" for t in names)
    print(header)
    for src in names:
        line = f"  {src:>16}"
        for tgt in names:
            v = matrix[src].get(tgt)
            line += f"{v:>16.3f}" if v is not None else f"{'FAIL':>16}"
        print(line)

    out = ROOT / "artifacts" / "agi_signal_transfer_matrix.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(matrix, indent=2))
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
