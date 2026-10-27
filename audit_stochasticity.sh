#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
[[ -z "${GROQ_API_KEY:-}" ]] && { read -rsp "Groq key: " GROQ_API_KEY; echo; export GROQ_API_KEY; }
[[ -d .venv-nodocker ]] || python3 -m venv .venv-nodocker
source .venv-nodocker/bin/activate
pip install --quiet --upgrade pip openai

python3 - <<'PY'
import os, subprocess, sys, json, hashlib, re
from collections import Counter
from pathlib import Path
from openai import OpenAI

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"], timeout=90)

PROMPTS = {
    "approximately_equal": ("Write a Python function approximately_equal(a,b,rel=1e-9) returning True if "
                            "a and b are equal up to relative AND absolute tolerance. Handle zero safely. "
                            "Return ONLY executable code."),
    "is_anagram":          ("Write a Python function is_anagram(a,b) returning True iff a and b are anagrams, "
                            "ignoring spaces and case. Return ONLY executable code."),
}
TESTS = {
    "approximately_equal": ("assert approximately_equal(0.1+0.2,0.3)\n"
                            "assert approximately_equal(0.0,1e-12)\n"
                            "assert approximately_equal(1.0,1.0)\n"
                            "assert not approximately_equal(1.0,2.0)\n"
                            "assert not approximately_equal(1e-9,1e9)\n"
                            "print('PASS')"),
    "is_anagram": ("assert is_anagram('Listen','Silent')\n"
                   "assert is_anagram('A man','nam a')\n"
                   "assert not is_anagram('abc','abd')\n"
                   "assert is_anagram('','')\n"
                   "print('PASS')"),
}

K = 10
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

def strip_fences(s):
    s = (s or "").strip()
    if s.startswith("```"):
        s = "\n".join(s.split("\n")[1:])
        if s.rstrip().endswith("```"): s = s.rstrip()[:-3]
    return s.strip()

out = {}
for model in MODELS:
    out[model] = {}
    for task, prompt in PROMPTS.items():
        passes = empty = abs_zero = 0; hashes = []
        for i in range(K):
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role":"system","content":"Return ONLY executable Python."},
                              {"role":"user","content":prompt}],
                    temperature=0.0, max_tokens=1200)
                code = strip_fences(r.choices[0].message.content)
            except Exception as e:
                continue
            if not code.strip():
                empty += 1; hashes.append("EMPTY"); continue
            hashes.append(hashlib.md5(code.encode()).hexdigest()[:8])
            if task == "approximately_equal" and re.search(r"abs_tol\s*=\s*0(?:\.0)?\b", code):
                abs_zero += 1
            p = Path(f"/tmp/aud_{model.replace('/','_')}_{task}_{i}.py")
            p.write_text(code + "\n\n" + TESTS[task])
            try:
                res = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=15)
                if res.returncode == 0 and "PASS" in res.stdout: passes += 1
            except subprocess.TimeoutExpired: pass
        out[model][task] = {"passes": passes, "K": K, "empty": empty,
                            "distinct_hashes": len(set(hashes)),
                            "abs_tol_zero": abs_zero}
        print(f"[{model.split('/')[-1]:14s}] {task:24s} pass {passes}/{K}  "
              f"distinct {len(set(hashes)):2d}  empty {empty}  abs_tol=0.0 {abs_zero}")

Path("signals_adv/stochasticity_audit.json").write_text(json.dumps(out, indent=2))
PY
