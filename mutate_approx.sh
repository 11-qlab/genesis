#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
[[ -z "${GROQ_API_KEY:-}" ]] && { read -rsp "Groq key: " GROQ_API_KEY; echo; export GROQ_API_KEY; }
[[ -d .venv-nodocker ]] || python3 -m venv .venv-nodocker
source .venv-nodocker/bin/activate
pip install --quiet --upgrade pip openai

python3 - <<'PY'
import os, subprocess, sys, json
from openai import OpenAI
from pathlib import Path

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"], timeout=90)
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

PROMPT = ("Write a Python function approximately_equal(a,b,rel=1e-9) returning True if a and b are equal "
          "up to relative AND absolute tolerance. Handle zero safely. Return ONLY executable code.")

# Each variant adds exactly one assertion — isolates the trap
ASSERTS = {
    "A_trivial":       "assert approximately_equal(1.0,1.0)",
    "B_small_rel":     "assert approximately_equal(0.1+0.2,0.3)",
    "C_zero_vs_tiny":  "assert approximately_equal(0.0,1e-12)",   # ← predicted breaking point
    "D_far_apart":     "assert not approximately_equal(1.0,2.0)",
    "E_degenerate":    "assert not approximately_equal(1e-9,1e9)",
}

results = {}
for model in MODELS:
    print(f"\n=== {model} ===")
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":"Return ONLY executable Python. No fences."},
                      {"role":"user","content":PROMPT}],
            temperature=0.0, max_tokens=1200)
        code = r.choices[0].message.content.strip()
        if code.startswith("```"):
            code = "\n".join(code.split("\n")[1:])
            if code.rstrip().endswith("```"): code = code.rstrip()[:-3]
        code = code.strip()
    except Exception as e:
        print(f"  API error: {e}"); continue

    print(f"  code preview: {code[:120].replace(chr(10),' / ')}...")
    print(f"  uses math.isclose: {'math.isclose(' in code}")
    print(f"  passes abs_tol:    {'abs_tol' in code}")

    per_assert = {}
    for name, assertion in ASSERTS.items():
        sol = Path(f"/tmp/mut_{model.replace('/','_')}_{name}.py")
        sol.write_text(code + "\n\n" + assertion + "\nprint('PASS')")
        try:
            p = subprocess.run([sys.executable, str(sol)], capture_output=True, text=True, timeout=15)
            ok = p.returncode == 0 and "PASS" in p.stdout
            per_assert[name] = "PASS" if ok else "FAIL"
            print(f"    {name:20s} {per_assert[name]}")
        except subprocess.TimeoutExpired:
            per_assert[name] = "TIMEOUT"
            print(f"    {name:20s} TIMEOUT")
    results[model] = per_assert

print("\n" + "=" * 70)
print("MUTATION MATRIX")
print("=" * 70)
cols = list(ASSERTS.keys())
print(f"{'model':20s}" + "".join(f"{c:>18s}" for c in cols))
for m, row in results.items():
    line = f"{m.split('/')[-1]:20s}"
    for c in cols:
        line += f"{row.get(c,'?'):>18s}"
    print(line)

Path("signals_adv/mutation_approx.json").write_text(json.dumps(results, indent=2))
PY
