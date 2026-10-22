#!/usr/bin/env python3
"""
AGI-signal probes that need no code changes.

  --mode transfer      measure cross-bench tool-sequence similarity
  --mode composition   3-arm strategy comparison (greedy / rev-basic / rev-rich)
  --mode contamination bench-A-before-B vs B-fresh

Writes JSON + text matrix to stdout.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHES = [
    "bench/workspace_list.jsonl",
    "bench/error_recovery.jsonl",
    "bench/task_chain.jsonl",
    "bench/memory_search.jsonl",
]


def run_bench(bench, strategy="greedy", signal=None, tag="", delay_ms=1500):
    db = f"/tmp/agi_sig_{tag}.sqlite3"
    ws = f"/tmp/agi_sig_{tag}_ws"
    with contextlib.suppress(FileNotFoundError):
        os.remove(db)
    shutil.rmtree(ws, ignore_errors=True)

    args = [
        sys.executable, "-m", "agi", "eval", "run",
        "--bench", bench, "--seed", "all",
        "--strategy", strategy, "--delay-ms", str(delay_ms),
    ]
    if signal:
        args += ["--revision-signal", signal]

    env = {
        **os.environ,
        "AGI_STORAGE_PATH": db,
        "AGI_FS_ROOT": ws,
        "PYTHONPATH": "src",
    }
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


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def mode_transfer(delay_ms):
    print("\n=== TRANSFER PROXY (sequence similarity) ===\n")
    data = {}
    for i, b in enumerate(BENCHES):
        name = Path(b).stem
        print(f"  running {name} ...", flush=True)
        d = run_bench(b, tag=f"tr_{i}", delay_ms=delay_ms)
        if d is None:
            continue
        data[name] = d
        print(f"    {d['passed']}/{d['total']}  acc={d['accuracy']:.3f}  rl={d['rate_limited_items']}")

    if len(data) < 2:
        print("  need >=2 successful benches")
        return

    seqs = {}
    for name, d in data.items():
        seqs[name] = [it.get("tool_sequence") or [] for it in d.get("items", [])]

    print("\n--- tool-multiset Jaccard between benches ---")
    names = list(data)
    header = "  " + " " * 18 + "".join(f"{n:>18}" for n in names)
    print(header)
    for a in names:
        flat_a = [t for s in seqs[a] for t in s]
        row = f"  {a:>18}"
        for b in names:
            flat_b = [t for s in seqs[b] for t in s]
            row += f"{jaccard(flat_a, flat_b):>18.3f}"
        print(row)

    print("\n--- most-common tool sequence per bench ---")
    for name in names:
        c = Counter(tuple(s) for s in seqs[name] if s)
        print(f"  {name}:")
        for seq, n in c.most_common(3):
            print(f"    {n:>2}x  {list(seq)}")

    out = ROOT / "artifacts" / "agi_signal_transfer.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "accuracies": {n: data[n]["accuracy"] for n in names},
        "sequences": {n: seqs[n] for n in names},
    }, indent=2))
    print(f"\n  wrote {out}")


def mode_composition(delay_ms):
    print("\n=== COMPOSITION VIA STRATEGY ===")
    print("  arms: greedy / rev-basic / rev-rich\n")

    bench = "bench/error_recovery.jsonl"
    arms = [
        ("greedy",    "greedy",   None,   "g"),
        ("rev-basic", "revision", "basic", "b"),
        ("rev-rich",  "revision", "rich",  "r"),
    ]
    results = {}
    for name, strat, sig, tag in arms:
        print(f"  running {name} ...", flush=True)
        d = run_bench(bench, strategy=strat, signal=sig, tag=f"cp_{tag}", delay_ms=delay_ms)
        if d is None:
            continue
        results[name] = d
        print(f"    {d['passed']}/{d['total']}  acc={d['accuracy']:.3f}")

    if not results:
        return
    print("\n--- composition summary ---")
    for name, d in results.items():
        print(f"  {name:>10}  acc={d['accuracy']:.3f}  rl={d['rate_limited_items']}")

    if "greedy" in results:
        base = results["greedy"]["accuracy"]
        for name in ("rev-basic", "rev-rich"):
            if name in results:
                delta = results[name]["accuracy"] - base
                verdict = (
                    "improves" if delta > 0.05
                    else ("interferes" if delta < -0.05 else "within noise")
                )
                print(f"  delta({name} - greedy) = {delta:+.3f}  ({verdict})")

    out = ROOT / "artifacts" / "agi_signal_composition.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        k: {"accuracy": v["accuracy"], "passed": v["passed"], "total": v["total"]}
        for k, v in results.items()
    }, indent=2))
    print(f"\n  wrote {out}")


def mode_contamination(delay_ms):
    print("\n=== CONTAMINATION PROBE ===")
    print("  compare: [fresh B] vs [A then B]\n")

    B = "bench/error_recovery.jsonl"
    A = "bench/workspace_list.jsonl"

    print("  running B fresh ...", flush=True)
    d_fresh = run_bench(B, tag="ct_fresh", delay_ms=delay_ms)
    if d_fresh is None:
        return
    print(f"    B fresh: {d_fresh['passed']}/{d_fresh['total']}  acc={d_fresh['accuracy']:.3f}")

    print("  running A (prep) ...", flush=True)
    run_bench(A, tag="ct_prep", delay_ms=delay_ms)

    print("  running B after A ...", flush=True)
    d_after = run_bench(B, tag="ct_after", delay_ms=delay_ms)
    if d_after is None:
        return
    print(f"    B after A: {d_after['passed']}/{d_after['total']}  acc={d_after['accuracy']:.3f}")

    delta = d_after["accuracy"] - d_fresh["accuracy"]
    print(f"\n  delta(B_after - B_fresh) = {delta:+.3f}")
    print(f"  verdict: {'CONTAMINATED' if abs(delta) > 0.10 else 'clean (within noise)'}")

    out = ROOT / "artifacts" / "agi_signal_contamination.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "fresh": d_fresh["accuracy"],
        "after": d_after["accuracy"],
        "delta": delta,
    }, indent=2))
    print(f"\n  wrote {out}")



def _check_provider():
    """Fail loud if the shell's provider env is stale or unreachable.

    Detects the three failure modes seen this session:
      - AGI_PROVIDER unset (falls back to echo)
      - AGI_API_KEY missing for a cloud provider
      - llama-server not listening on the local port
    """
    prov = os.environ.get("AGI_PROVIDER", "").strip()
    if not prov or prov == "echo":
        print(f"FATAL: AGI_PROVIDER is '{prov or '<unset>'}' — run would use echo stub.",
              file=sys.stderr)
        print("       Set AGI_PROVIDER (groq / huggingface / nvidia / local) first.",
              file=sys.stderr)
        sys.exit(1)

    if prov in ("groq", "huggingface", "nvidia", "openai_compat"):
        key = os.environ.get("AGI_API_KEY", "")
        if not key:
            print(f"FATAL: AGI_API_KEY empty for provider '{prov}'.", file=sys.stderr)
            sys.exit(1)
        if prov == "groq" and not key.startswith("gsk_"):
            print(f"FATAL: groq key must start gsk_, got '{key[:6]}...'", file=sys.stderr)
            sys.exit(1)
        if prov == "huggingface" and not key.startswith("hf_"):
            print(f"FATAL: huggingface key must start hf_, got '{key[:6]}...'", file=sys.stderr)
            sys.exit(1)
        if prov == "nvidia" and not key.startswith("nvapi-"):
            print(f"FATAL: nvidia key must start nvapi-, got '{key[:6]}...'", file=sys.stderr)
            sys.exit(1)

    if prov in ("local", "ollama"):
        base = os.environ.get("AGI_BASE_URL", "")
        if not base:
            print(f"FATAL: AGI_BASE_URL unset for provider '{prov}'.", file=sys.stderr)
            sys.exit(1)
        import urllib.request
        try:
            urllib.request.urlopen(base.rstrip("/") + "/models", timeout=5)
        except Exception as e:
            print(f"FATAL: provider '{prov}' unreachable at {base}: {e}", file=sys.stderr)
            sys.exit(1)

    # Final smoke: real chat call, reject echo-canned output.
    import subprocess
    try:
        r = subprocess.run(
            [sys.executable, "-m", "agi", "chat", "hi"],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        print("FATAL: agi chat timed out (60s) — provider likely dead.", file=sys.stderr)
        sys.exit(1)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        print(f"FATAL: agi chat exited {r.returncode}:", file=sys.stderr)
        print(out[:400], file=sys.stderr)
        sys.exit(1)
    if "How can I assist you today" in out and "echo" in out.lower():
        print("FATAL: provider is echo stub — env is stale.", file=sys.stderr)
        sys.exit(1)

def main():
    _check_provider()
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all",
                    choices=["transfer", "composition", "contamination", "all"])
    ap.add_argument("--delay-ms", type=int, default=1500)
    args = ap.parse_args()

    os.chdir(ROOT)
    if args.mode in ("transfer", "all"):
        mode_transfer(args.delay_ms)
    if args.mode in ("composition", "all"):
        mode_composition(args.delay_ms)
    if args.mode in ("contamination", "all"):
        mode_contamination(args.delay_ms)


if __name__ == "__main__":
    main()
