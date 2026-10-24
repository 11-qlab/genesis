#!/usr/bin/env python3
"""
Run fam14in (inside hull, fs_read) and fam14out (outside hull, text_regex).
Same 3-step plan shape, different tools. Report accuracy gap and verdict.
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


def run_one(bench, tag, delay_ms=500):
    db = f"/tmp/agi_hull_{tag}.sqlite3"
    ws = f"/tmp/agi_hull_{tag}_ws"
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

    bench_in = TEST_DIR / "fam14in.jsonl"
    bench_out = TEST_DIR / "fam14out.jsonl"
    if not bench_in.exists() or not bench_out.exists():
        sys.exit("fam14 benches missing — run scripts/build_fam13_14.py first")

    print("\n=== HULL BOUNDARY TEST ===\n")
    print("  inside-hull (fs_read, matched difficulty)...", flush=True)
    d_in = run_one(bench_in, "in", args.delay_ms)
    if d_in is None:
        sys.exit("inside-hull run failed")

    print("  outside-hull (text_regex, same plan shape)...", flush=True)
    d_out = run_one(bench_out, "out", args.delay_ms)
    if d_out is None:
        sys.exit("outside-hull run failed")

    acc_in = d_in["accuracy"]
    acc_out = d_out["accuracy"]
    gap = acc_in - acc_out

    print("\n--- results ---")
    print(f"  inside-hull  : {d_in['passed']}/{d_in['total']} = {acc_in:.3f}")
    print(f"  outside-hull : {d_out['passed']}/{d_out['total']} = {acc_out:.3f}")
    print(f"  gap (in - out): {gap:+.3f}")

    if gap < 0.10:
        verdict = "NOT hull-bounded (or matched difficulty)"
    elif gap < 0.30:
        verdict = "weak hull effect"
    else:
        verdict = "strongly hull-bounded"
    print(f"  verdict: {verdict}")

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "inside": {"passed": d_in["passed"], "total": d_in["total"], "acc": acc_in},
        "outside": {"passed": d_out["passed"], "total": d_out["total"], "acc": acc_out},
        "gap": gap,
        "verdict": verdict,
        "model": os.environ.get("AGI_MODEL"),
    }, indent=2))
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
