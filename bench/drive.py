#!/usr/bin/env python3
# bench/drive.py  — run error_recovery across strategies, aggregate, diff items
import json, os, subprocess, sys, shutil
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[1]
BENCH  = "bench/error_recovery.jsonl"
ARMS   = [
    ("greedy",   ["--strategy", "greedy"]),
    ("revision", ["--strategy", "revision", "--revision-signal", "basic"]),
]
N_RUNS = 2
DELAY  = "5000"


def run_one(arm_name, extra, run_idx):
    tag  = f"{arm_name}_{run_idx}"
    db   = f"/tmp/agi_{tag}.sqlite3"
    ws   = f"/tmp/agi_{tag}_ws"
    err  = f"/tmp/agi_{tag}.stderr"
    env  = {**os.environ,
            "AGI_STORAGE_PATH": db,
            "AGI_FS_ROOT": ws,
            "PYTHONPATH": "src"}
    cmd  = [sys.executable, "-m", "agi", "eval", "run",
            "--bench", BENCH, "--seed", "all",
            "--delay-ms", DELAY, *extra]
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=1800)
        Path(err).write_text(p.stderr)
        if p.returncode != 0 or not p.stdout.strip():
            print(f"  [{tag}] FAILED rc={p.returncode}  see {err}", file=sys.stderr)
            return None
        return json.loads(p.stdout)
    finally:
        try:
            os.remove(db)
        except FileNotFoundError:
            pass
        shutil.rmtree(ws, ignore_errors=True)


def item_vector(d):
    items = d.get("items") or d.get("results") or []
    return {it.get("id", f"idx{i}"): it.get("status") or it.get("passed")
            for i, it in enumerate(items)}


summary, vectors = {}, {}
for name, extra in ARMS:
    rows = []
    for i in range(1, N_RUNS + 1):
        d = run_one(name, extra, i)
        if d is None:
            continue
        rows.append(d)
        vectors.setdefault(name, []).append(item_vector(d))
        print(f"  {name} run {i}: {d['passed']}/{d['total']} "
              f"acc={d['accuracy']}  rl={d['rate_limited_items']}")
    if rows:
        summary[name] = {
            "acc_mean": sum(r["accuracy"] for r in rows) / len(rows),
            "rl_total": sum(r["rate_limited_items"] for r in rows),
            "n":        len(rows),
        }

print("\n=== summary ===")
for k, v in summary.items():
    print(f"{k:10s} acc_mean={v['acc_mean']:.3f}  "
          f"rl={v['rl_total']}  n={v['n']}")

if "greedy" in vectors and "revision" in vectors:
    g = vectors["greedy"][0]
    r = vectors["revision"][0]
    ids = sorted(set(g) | set(r))
    print("\n=== per-item (run 1, greedy vs revision) ===")
    for i in ids:
        if g.get(i) != r.get(i):
            print(f"  {i:12s} greedy={g.get(i)}  revision={r.get(i)}")
