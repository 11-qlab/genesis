#!/usr/bin/env python3
"""Run absolute verification at L1-L4 using gpt-oss-20b (vLLM OpenAI-compatible endpoint)."""
import argparse, json, os, re, sys, time
from pathlib import Path
from openai import OpenAI

LEVELS = ["L1", "L2", "L3", "L4"]

SYSTEM = """You are a strict trajectory verifier for a tool-using agent.
You will be shown a trajectory at a specific evidence level.
Decide whether the trajectory is CORRECT (it accomplished the goal, or is a valid execution)
or INCORRECT (a step is wrong, an argument is wrong, the order is wrong, or it claims success it did not achieve).
Answer with exactly one token: CORRECT or INCORRECT."""

def parse_verdict(text: str):
    t = text.strip().upper()
    if re.search(r"\bINCORRECT\b", t):
        return "INCORRECT"
    if re.search(r"\bCORRECT\b", t):
        return "CORRECT"
    return "PARSE_FAIL"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rendered-dir", required=True, help="dir from esf_render_ladder.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--base-url", default=os.environ.get("AGI_BASE_URL", "http://localhost:8000/v1"))
    ap.add_argument("--model", default=os.environ.get("AGI_MODEL", "openai/gpt-oss-20b"))
    ap.add_argument("--api-key", default=os.environ.get("AGI_API_KEY", "EMPTY"))
    ap.add_argument("--goal", default="", help="optional global goal / task description")
    ap.add_argument("--max-tokens", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    client = OpenAI(base_url=args.base_url, api_key=args.api_key)
    files = sorted(Path(args.rendered_dir).glob("*.L[1-4].txt"))
    if not files:
        print(f"no rendered L1-L4 files in {args.rendered_dir}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for f in files:
        stem = f.name.rsplit(".", 2)[0]   # remove .Lx.txt
        level = f.name.rsplit(".", 2)[1]
        evidence = f.read_text()
        user = f"Goal: {args.goal}\n\n{evidence}\n\nVerdict (CORRECT or INCORRECT):"
        t0 = time.time()
        resp = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": user}],
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
        raw = resp.choices[0].message.content or ""
        verdict = parse_verdict(raw)
        rows.append({
            "traj": stem, "level": level, "verdict": verdict,
            "raw": raw.strip()[:80], "latency_s": round(time.time() - t0, 2),
        })
        print(f"{stem} {level} -> {verdict}  ({rows[-1]['latency_s']}s)")

    Path(args.out).write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {args.out} ({len(rows)} rows)")

if __name__ == "__main__":
    main()
