#!/usr/bin/env python3
"""
Run fam13 (path ambiguity). Categorize each item's actual tool sequence
into path_A (direct), path_B (check-first), or other. Report path
distribution + pass-by-path + path-invariance verdict.
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "bench" / "families" / "test"


def _check_provider():
    prov = os.environ.get("AGI_PROVIDER", "").strip()
    if not prov or prov == "echo":
        sys.exit(f"FATAL: AGI_PROVIDER is {prov!r}")
    if not os.environ.get("AGI_API_KEY", ""):
        sys.exit(f"FATAL: AGI_API_KEY empty for {prov}")
    r = subprocess.run(
        [sys.executable, "-m", "agi", "chat", "hi"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        sys.exit(f"FATAL: agi chat failed — {r.stderr[:300]}")


def classify(seq):
    if not seq:
        return "empty"
    s = list(seq)
    if "fs_write" not in s or "fs_read" not in s:
        return "no_read" if "fs_write" in s else "no_write"
    i_write = s.index("fs_write")
    after = s[i_write:]
    if "fs_read" not in after:
        return "write_no_read"
    if "fs_list" in s[:i_write]:
        return "path_B"
    return "path_A"


def run_one(bench, tag, delay_ms=500):
    db = f"/tmp/agi_path_{tag}.sqlite3"
    ws = f"/tmp/agi_path_{tag}_ws"
    try: os.remove(db)
    except FileNotFoundError: pass
    shutil.rmtree(ws, ignore_errors=True)

    env = {**os.environ, "AGI_STORAGE_PATH": db, "AGI_FS_ROOT": ws,
           "PYTHONPATH": "src", "AGI_TOOLS_FAMILIES": "1"}
    args = [sys.executable, "-m", "agi", "eval", "run",
            "--bench", str(bench), "--seed", "all",
            "--strategy", "greedy", "--delay-ms", str(delay_ms)]
    try:
        p = subprocess.run(args, cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=1800)
    except Exception as e:
        print(f"  [!] {tag}: {type(e).__name__}: {e}", file=sys.stderr)
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as e:
        print(f"  [!] {tag}: bad JSON — {e}", file=sys.stderr)
        if p.stderr:
            print(f"       stderr: {p.stderr[:400]}", file=sys.stderr)
        return None
    finally:
        try: os.remove(db)
        except FileNotFoundError: pass
        shutil.rmtree(ws, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--delay-ms", type=int, default=500)
    args = ap.parse_args()

    os.chdir(ROOT)
    _check_provider()

    bench = TEST_DIR / "fam13.jsonl"
    if not bench.exists():
        sys.exit("fam13 missing — run scripts/build_fam13_14.py first")

    print("\n=== PATH AMBIGUITY TEST ===\n")
    d = run_one(bench, "fam13", args.delay_ms)
    if d is None:
        sys.exit("fam13 run failed")

    print(f"\n  overall: {d['passed']}/{d['total']} = {d['accuracy']:.3f}")
    print("\n  per-item path analysis:")

    counts = {"path_A": 0, "path_B": 0, "no_write": 0,
              "no_read": 0, "write_no_read": 0, "empty": 0}
    passes = {k: 0 for k in counts}

    for it in d.get("items", []):
        seq = it.get("tool_sequence") or []
        cat = classify(seq)
        counts[cat] += 1
        if it.get("passed"):
            passes[cat] += 1
        print(f"    {it['id']:12s} pass={it['passed']!s:5s} path={cat:15s} seq={seq}")

    print("\n  path distribution:")
    for cat in counts:
        n = counts[cat]
        if n == 0:
            continue
        p = passes[cat]
        print(f"    {cat:15s}  n={n:2d}  passed={p:2d}  acc={p/n:.2f}")

    invariant = passes["path_A"] > 0 and passes["path_B"] > 0
    if invariant:
        verdict = "path-invariant (both paths reach goal)"
    elif counts["path_A"] > 0 and counts["path_B"] == 0:
        verdict = "path-A-only (direct create)"
    elif counts["path_B"] > 0 and counts["path_A"] == 0:
        verdict = "path-B-only (check first)"
    else:
        verdict = "neither path consistently reaches goal"

    print(f"\n  verdict: {verdict}")

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "overall": {"passed": d["passed"], "total": d["total"], "acc": d["accuracy"]},
        "path_distribution": counts,
        "pass_by_path": passes,
        "invariant": invariant,
        "verdict": verdict,
        "model": os.environ.get("AGI_MODEL"),
        "items": [{"id": it["id"], "passed": it["passed"],
                   "path": classify(it.get("tool_sequence") or []),
                   "tool_sequence": it.get("tool_sequence")}
                  for it in d.get("items", [])],
    }, indent=2))
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
