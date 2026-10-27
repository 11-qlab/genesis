#!/usr/bin/env bash
set -uo pipefail

if [[ -z "${GROQ_API_KEY:-}" ]]; then
  read -rsp "Groq key: " GROQ_API_KEY; echo; export GROQ_API_KEY
fi
[[ -z "$GROQ_API_KEY" ]] && { echo "No key"; exit 1; }

python3 -m venv .venv-nodocker 2>/dev/null || true
# shellcheck disable=SC1091
source .venv-nodocker/bin/activate
pip install --quiet --upgrade pip
pip install --quiet openai

cat > tasks.jsonl <<'EOF'
{"task_id":"factorial","prompt":"Write a Python function factorial(n) that returns n! for n>=0. Return ONLY executable code, no markdown fences.","test":"assert factorial(0)==1\nassert factorial(1)==1\nassert factorial(5)==120\nprint('PASS')"}
{"task_id":"is_palindrome","prompt":"Write a Python function is_palindrome(s) that returns True if s is a palindrome (case-insensitive), else False. Return ONLY executable code, no markdown fences.","test":"assert is_palindrome('racecar')==True\nassert is_palindrome('hello')==False\nprint('PASS')"}
{"task_id":"fibonacci","prompt":"Write a Python function fib(n) that returns the nth Fibonacci number (0-indexed). Return ONLY executable code, no markdown fences.","test":"assert fib(0)==0\nassert fib(1)==1\nassert fib(10)==55\nprint('PASS')"}
{"task_id":"is_prime","prompt":"Write a Python function is_prime(n) that returns True if n is prime, else False. Return ONLY executable code, no markdown fences.","test":"assert is_prime(2)==True\nassert is_prime(17)==True\nassert is_prime(20)==False\nprint('PASS')"}
{"task_id":"reverse_words","prompt":"Write a Python function reverse_words(s) that reverses the word order. Return ONLY executable code, no markdown fences.","test":"assert reverse_words('hello world')=='world hello'\nassert reverse_words('a b c')=='c b a'\nprint('PASS')"}
EOF

rm -rf runs signals
mkdir -p runs signals

python3 - <<'PY'
import json, os, subprocess, sys, time, uuid
from collections import Counter
from pathlib import Path
from openai import OpenAI

client = OpenAI(base_url="https://api.groq.com/openai/v1",
                api_key=os.environ["GROQ_API_KEY"], timeout=90)
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
tasks  = [json.loads(l) for l in open("tasks.jsonl") if l.strip()]

def strip_fences(s):
    s = s.strip()
    if s.startswith("```"):
        lines = s.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines)
    return s.strip()

def classify(stdout, stderr, code):
    blob = (stdout + "\n" + stderr).lower()
    if "modulenotfounderror" in blob or "no module named" in blob: return "dependency_missing"
    if "syntaxerror" in blob:        return "syntax_error"
    if "nameerror" in blob:          return "name_error"
    if "assertionerror" in blob:     return "assertion_failure"
    if "typeerror" in blob:          return "type_error"
    if "traceback" in blob:          return "runtime_exception"
    if not code.strip():             return "empty_output"
    if "```" in code:                return "unfenced_persisted"
    return "unclassified"

results = []
for model in MODELS:
    for task in tasks:
        tid = f"{model.replace('/','_')}__{task['task_id']}__{uuid.uuid4().hex[:6]}"
        d = Path("runs") / tid
        d.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {"role":"system","content":"Return ONLY executable Python. No markdown fences, no commentary."},
                    {"role":"user","content":task["prompt"]},
                ],
                temperature=0.0, max_tokens=1024)
            code = strip_fences(r.choices[0].message.content)
        except Exception as e:
            rec = {"task":task["task_id"],"model":model,"passed":False,
                   "reason":"api_error","error":str(e),"elapsed":round(time.time()-t0,2)}
            (d/"result.json").write_text(json.dumps(rec, indent=2))
            results.append(rec)
            print(f"[{model}] {task['task_id']}: API_ERROR"); continue

        (d/"solution.py").write_text(code + "\n\n" + task["test"])
        try:
            p = subprocess.run([sys.executable, str(d/"solution.py")],
                               capture_output=True, text=True, timeout=30)
            passed = p.returncode == 0 and "PASS" in p.stdout
            rec = {"task":task["task_id"],"model":model,"passed":passed,
                   "reason": None if passed else classify(p.stdout, p.stderr, code),
                   "stdout": p.stdout[-2000:], "stderr": p.stderr[-2000:],
                   "code": code, "elapsed": round(time.time()-t0,2)}
        except subprocess.TimeoutExpired:
            rec = {"task":task["task_id"],"model":model,"passed":False,
                   "reason":"timeout","code":code,"elapsed":round(time.time()-t0,2)}

        (d/"result.json").write_text(json.dumps(rec, indent=2))
        results.append(rec)
        tag = "PASS" if rec["passed"] else "FAIL/" + (rec.get("reason") or "?")
        print(f"[{model}] {task['task_id']}: {tag}")

with open("signals/runs.jsonl","w") as f:
    for r in results: f.write(json.dumps(r)+"\n")

by = {}
for r in results:
    s = by.setdefault(r["model"], {"n":0,"p":0}); s["n"] += 1
    if r["passed"]: s["p"] += 1

print("\n── Pass rate by model ──────────────────────────")
for m, s in by.items():
    print(f"{m:35s} {s['p']}/{s['n']}  ({100*s['p']/s['n']:.0f}%)")

causes = Counter(r.get("reason") or "PASS" for r in results)
print("\n── Failure causes ──────────────────────────────")
for c, n in causes.most_common():
    print(f"{c:30s} {n}")

json.dump(dict(causes), open("signals/causes.json","w"), indent=2)
PY

echo
echo "✅ done"
echo "  runs/               per-trial solution.py + result.json"
echo "  signals/runs.jsonl  flat result table"
echo "  signals/causes.json failure-cause histogram"
