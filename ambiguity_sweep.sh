#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
[[ -z "${GROQ_API_KEY:-}" ]] && { read -rsp "Groq key: " GROQ_API_KEY; echo; export GROQ_API_KEY; }
[[ -d .venv-nodocker ]] || python3 -m venv .venv-nodocker
source .venv-nodocker/bin/activate
pip install --quiet --upgrade pip openai

python3 - <<'PY'
import os, subprocess, sys, json, hashlib, re
from collections import defaultdict
from pathlib import Path
from openai import OpenAI

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"], timeout=90)

# Only the tasks that had at least one failure somewhere, plus the confirmed one.
TASKS = {
  "approximately_equal": {
    "original": "Write a Python function approximately_equal(a,b,rel=1e-9) returning True if a and b are equal up to relative AND absolute tolerance. Handle zero safely. Return ONLY executable code.",
    "tightened": "Write a Python function approximately_equal(a,b,rel=1e-9,abs_tol=1e-12) returning True iff |a-b| <= max(rel*max(|a|,|b|), abs_tol). The default of abs_tol MUST be 1e-12, not 0.0. Return ONLY executable code.",
    "test": "assert approximately_equal(0.1+0.2,0.3)\nassert approximately_equal(0.0,1e-12)\nassert approximately_equal(1.0,1.0)\nassert not approximately_equal(1.0,2.0)\nassert not approximately_equal(1e-9,1e9)\nprint('PASS')",
  },
  "merge_intervals": {
    "original": "Write a Python function merge_intervals(intervals) that merges overlapping or touching closed intervals. Return ONLY executable code.",
    "tightened": "Write a Python function merge_intervals(intervals) that merges overlapping AND touching closed intervals (e.g. [[1,4],[4,5]] must merge to [[1,5]]). Empty list returns []. Return ONLY executable code.",
    "test": "assert merge_intervals([[1,3],[2,6],[8,10],[15,18]])==[[1,6],[8,10],[15,18]]\nassert merge_intervals([])==[]\nassert merge_intervals([[1,4],[4,5]])==[[1,5]]\nprint('PASS')",
  },
  "binary_search_leftmost": {
    "original": "Write a Python function binary_search_leftmost(arr,x) returning the LEFTMOST index of x in a sorted list arr (which may contain duplicates), or -1 if absent. Must run in O(log n). Return ONLY executable code.",
    "tightened": "Write a Python function binary_search_leftmost(arr,x) returning the LEFTMOST index of x in a sorted list arr. If arr contains duplicates, MUST return min(index). Empty list returns -1. Must run in O(log n). Return ONLY executable code.",
    "test": "assert binary_search_leftmost([1,2,2,2,3],2)==1\nassert binary_search_leftmost([1,2,3],4)==-1\nassert binary_search_leftmost([],1)==-1\nassert binary_search_leftmost([2,2,2],2)==0\nprint('PASS')",
  },
  "valid_ipv4": {
    "original": "Write a Python function valid_ipv4(s) returning True iff s is a valid IPv4 address: exactly 4 dot-separated octets, each an integer 0-255, with NO leading zeros (except '0' itself). Return ONLY executable code.",
    "tightened": "Write a Python function valid_ipv4(s) returning True iff s is a valid IPv4 address: exactly 4 dot-separated octets, each an integer 0-255. Must reject '01.2.3.4' (leading zero), '0.0.0.0' is valid, '' is invalid. Return ONLY executable code.",
    "test": "assert valid_ipv4('192.168.1.1')\nassert not valid_ipv4('256.1.1.1')\nassert not valid_ipv4('01.2.3.4')\nassert not valid_ipv4('1.2.3')\nassert valid_ipv4('0.0.0.0')\nprint('PASS')",
  },
}

K = 10
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

def strip_fences(s):
    s = (s or "").strip()
    if s.startswith("```"):
        s = "\n".join(s.split("\n")[1:])
        if s.rstrip().endswith("```"): s = s.rstrip()[:-3]
    return s.strip()

print(f"{'task':24s} {'spec':10s} {'model':16s} {'pass':>5s} {'distinct':>9s} {'empty':>6s}")
print("-" * 78)
results = defaultdict(dict)
for task, cfg in TASKS.items():
    for spec_name in ("original", "tightened"):
        prompt, test = cfg[spec_name], cfg["test"]
        for model in MODELS:
            passes = empty = 0
            hashes = []
            for i in range(K):
                try:
                    r = client.chat.completions.create(
                        model=model,
                        messages=[{"role":"system","content":"Return ONLY executable Python."},
                                  {"role":"user","content":prompt}],
                        temperature=0.0, max_tokens=1500)
                    code = strip_fences(r.choices[0].message.content)
                except Exception:
                    continue
                if not code.strip():
                    empty += 1; hashes.append("EMPTY"); continue
                hashes.append(hashlib.md5(code.encode()).hexdigest()[:8])
                p = Path(f"/tmp/as_{model.replace('/','_')}_{task}_{spec_name}_{i}.py")
                p.write_text(code + "\n\n" + test)
                try:
                    r2 = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=15)
                    if r2.returncode == 0 and "PASS" in r2.stdout: passes += 1
                except subprocess.TimeoutExpired:
                    pass
            d = len(set(hashes))
            results[(task, spec_name, model)] = {"passes": passes, "K": K, "distinct": d, "empty": empty}
            print(f"{task:24s} {spec_name:10s} {model.split('/')[-1]:16s} {passes:>5d} {d:>9d} {empty:>6d}")

print()
print("=== Ambiguity-sensitive tasks (distinct>1 on original, distinct=1 on tightened) ===")
for task in TASKS:
    for model in MODELS:
        o = results[(task, "original", model)]
        t = results[(task, "tightened", model)]
        flag = "AMBI-SENSITIVE" if (o["distinct"] > 1 and t["distinct"] == 1) else ""
        delta = f"pass {o['passes']}->{t['passes']}" if o["passes"] != t["passes"] else ""
        print(f"  {task:24s} {model.split('/')[-1]:16s} "
              f"orig dist={o['distinct']:2d} tight dist={t['distinct']:2d}  {delta:12s} {flag}")

Path("signals_adv/ambiguity_sweep.json").write_text(
    json.dumps({f"{t}__{s}__{m}": v for (t,s,m),v in results.items()}, indent=2))
PY
