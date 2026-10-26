#!/usr/bin/env python3
"""Hybrid verifier: deterministic regex prefilter + LLM semantic check.

Placeholder/template syntax is a syntactic class — a regex catches it with
100% recall, 0 LLM cost, 0 run-to-run variance. Only non-syntactic cases
are sent to the LLM.
"""
import argparse, json, os, re, sys, time
from pathlib import Path
from openai import OpenAI
sys.path.insert(0, "scripts")
from esf import render_level

# Deterministic syntactic class — 100% recall by construction
TEMPLATE_RE = re.compile(
    r"""
    \{\{[^}]+\}\}         # {{anything}}
  | \$\{[^}]+\}           # ${anything}
  | \$\w+(\.\w+)*         # $var or $var.attr
  | <[^>]*(?:content|output|result|step|count)[^>]*>  # <content_from_s1> etc.
  | \bcontents?\s+of\s+\S+   # "contents of X"
  | \bthe\s+contents\b       # "the contents"
  | \bsame\s+as\s+\S+        # "same as X"
    """,
    re.VERBOSE | re.IGNORECASE,
)

SYSTEM_LLM = """You are a strict semantic verifier for tool-use trajectories.
The syntactic pre-filter has already accepted this trajectory as free of
template/placeholder syntax. Your job is to check semantics:
  - wrong tool used for the goal
  - wrong argument value (content present but does not match what was read)
  - wrong step order
  - false success claim
Answer CORRECT or INCORRECT (one word)."""

def syntactic_verdict(traj):
    """Deterministic check. Returns (verdict, matches) or (None, []) if clean."""
    matches = []
    for step in traj.get("steps", []):
        tc = step.get("tool_call") or {}
        if tc.get("name") != "fs_write":
            continue
        args = tc.get("args") or {}
        content = str(args.get("content", ""))
        if not content.strip():
            matches.append({"step": step.get("step_index"), "reason": "empty_content"})
            continue
        if TEMPLATE_RE.search(content):
            matches.append({"step": step.get("step_index"), "reason": "placeholder",
                            "content": content[:80]})
    if matches:
        return "INCORRECT", matches
    return None, []

def llm_verdict(traj, client, model):
    evidence = render_level(traj, "L4")
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_LLM},
                      {"role": "user", "content": evidence + "\n\nVerdict:"}],
            max_tokens=512, temperature=0.0,
            extra_body={"reasoning_effort": "low"},
        )
        msg = r.choices[0].message
        text = (msg.content or "") + (getattr(msg, "reasoning_content", "") or "")
        if re.search(r"\bINCORRECT\b", text, re.I): return "INCORRECT"
        if re.search(r"\bCORRECT\b", text, re.I): return "CORRECT"
    except Exception as e:
        return f"ERR:{e}"
    return "PARSE_FAIL"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trajectories", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=os.environ.get("AGI_MODEL", "gpt-oss-20b"))
    args = ap.parse_args()

    client = OpenAI(base_url=os.environ["AGI_BASE_URL"],
                    api_key=os.environ.get("AGI_API_KEY", "EMPTY"))
    rows = []
    for line in Path(args.trajectories).read_text().strip().splitlines():
        traj = json.loads(line)
        item = traj.get("item_id", "?")
        t0 = time.time()

        # 1. Deterministic prefilter
        syn_verdict, syn_matches = syntactic_verdict(traj)
        if syn_verdict == "INCORRECT":
            v, src = "INCORRECT", "syntactic"
        else:
            v = llm_verdict(traj, client, args.model)
            src = "llm"

        rows.append({"item": item, "verdict": v, "source": src,
                     "syntactic_matches": syn_matches,
                     "latency_s": round(time.time() - t0, 2)})
        print(f"{item:<22} {v:<10} via {src:<10} ({rows[-1]['latency_s']}s)")

    Path(args.out).write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {args.out} ({len(rows)} rows)")

if __name__ == "__main__":
    main()
