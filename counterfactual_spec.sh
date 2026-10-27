#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
[[ -z "${GROQ_API_KEY:-}" ]] && { read -rsp "Groq key: " GROQ_API_KEY; echo; export GROQ_API_KEY; }
[[ -d .venv-nodocker ]] || python3 -m venv .venv-nodocker
source .venv-nodocker/bin/activate
pip install --quiet --upgrade pip openai

python3 - <<'PY'
import os, subprocess, sys, json, re, hashlib
from collections import Counter
from pathlib import Path
from openai import OpenAI

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"], timeout=90)

PROMPTS = {
  "original": (
    "Write a Python function approximately_equal(a,b,rel=1e-9) returning True if a and b are equal "
    "up to relative AND absolute tolerance. Handle zero safely. Return ONLY executable code."
  ),
  "tightened": (
    "Write a Python function approximately_equal(a,b,rel=1e-9,abs_tol=1e-12) returning True iff "
    "|a-b| <= max(rel*max(|a|,|b|), abs_tol). The default of abs_tol MUST be 1e-12, not 0.0. "
    "Return ONLY executable code."
  ),
}
TEST = (
  "assert approximately_equal(0.1+0.2,0.3)\n"
  "assert approximately_equal(0.0,1e-12)\n"
  "assert approximately_equal(1.0,1.0)\n"
  "assert not approximately_equal(1.0,2.0)\n"
  "assert not approximately_equal(1e-9,1e9)\n"
  "print('PASS')"
)
K = 20
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

def strip_fences(s):
    s = (s or "").strip()
    if s.startswith("```"):
        s = "\n".join(s.split("\n")[1:])
        if s.rstrip().endswith("```"): s = s.rstrip()[:-3]
    return s.strip()

def has_abs_zero(code):
    return bool(re.search(r"abs_tol\s*=\s*0(?:\.0+)?(?:[eE][+-]?\d+)?(?![\.\d])", code))

out = {}
print(f"{'model':16s} {'spec':10s} {'pass':>5s} {'K':>3s} {'abs0':>5s} {'empty':>6s} {'distinct':>9s}")
print("-" * 66)
for model in MODELS:
    out[model] = {}
    for spec_name, prompt in PROMPTS.items():
        passes = empty = abs0 = 0
        hashes = []
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
            if has_abs_zero(code): abs0 += 1
            p = Path(f"/tmp/cf_{model.replace('/','_')}_{spec_name}_{i}.py")
            p.write_text(code + "\n\n" + TEST)
            try:
                r2 = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=15)
                if r2.returncode == 0 and "PASS" in r2.stdout: passes += 1
            except subprocess.TimeoutExpired:
                pass
        out[model][spec_name] = {
            "passes": passes, "K": K, "abs_tol_zero": abs0,
            "empty": empty, "distinct_hashes": len(set(hashes))
        }
        print(f"{model.split('/')[-1]:16s} {spec_name:10s} {passes:>5d} {K:>3d} "
              f"{abs0:>5d} {empty:>6d} {len(set(hashes)):>9d}")

Path("signals_adv/counterfactual_spec.json").write_text(json.dumps(out, indent=2))
print()
print("=== Verdict ===")
for model in MODELS:
    o = out[model]["original"]; t = out[model]["tightened"]
    print(f"{model.split('/')[-1]:16s} original {o['passes']}/{o['K']}  ->  tightened {t['passes']}/{t['K']}  "
          f"(abs_tol=0.0: {o['abs_tol_zero']} -> {t['abs_tol_zero']})")
PY
