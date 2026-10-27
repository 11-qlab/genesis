#!/usr/bin/env bash
set -uo pipefail
if [[ -z "${GROQ_API_KEY:-}" ]]; then read -rsp "Groq key: " GROQ_API_KEY; echo; export GROQ_API_KEY; fi
[[ -z "$GROQ_API_KEY" ]] && { echo "No key"; exit 1; }

[[ -d .venv-nodocker ]] || python3 -m venv .venv-nodocker
source .venv-nodocker/bin/activate
pip install --quiet --upgrade pip openai

cat > tasks_hard.jsonl <<'EOF'
{"task_id":"factorial_large","prompt":"Write a Python function factorial(n) that returns n! as an exact integer for n>=0. Must handle n=1000. Return ONLY executable code, no markdown fences.","test":"import math\nassert factorial(0)==1\nassert factorial(100)==math.factorial(100)\nassert factorial(1000)==math.factorial(1000)\nprint('PASS')"}
{"task_id":"safe_divide","prompt":"Write a Python function safe_divide(a,b) that returns a/b as a float, or None if b is zero. Return ONLY executable code, no markdown fences.","test":"assert safe_divide(10,2)==5.0\nassert safe_divide(1,0) is None\nassert safe_divide(0,5)==0.0\nprint('PASS')"}
{"task_id":"merge_intervals","prompt":"Write a Python function merge_intervals(intervals) that merges overlapping or touching closed intervals. Return ONLY executable code, no markdown fences.","test":"assert merge_intervals([[1,3],[2,6],[8,10],[15,18]])==[[1,6],[8,10],[15,18]]\nassert merge_intervals([])==[]\nassert merge_intervals([[1,4],[4,5]])==[[1,5]]\nassert merge_intervals([[1,4]])==[[1,4]]\nprint('PASS')"}
{"task_id":"rle","prompt":"Write a Python function rle(s) that run-length encodes a string into tuples (char,count). Empty string returns []. Return ONLY executable code, no markdown fences.","test":"assert rle('aaabbc')==[('a',3),('b',2),('c',1)]\nassert rle('')==[]\nassert rle('a')==[('a',1)]\nprint('PASS')"}
{"task_id":"top_k_words","prompt":"Write a Python function top_k_words(s,k) returning the k most frequent words in s, sorted by count descending then word ascending, as (word,count) tuples. Return ONLY executable code, no markdown fences.","test":"assert top_k_words('a b a c b a',2)==[('a',3),('b',2)]\nassert top_k_words('a b b',1)==[('b',2)]\nassert top_k_words('',3)==[]\nprint('PASS')"}
{"task_id":"parse_query","prompt":"Write a Python function parse_query(s) parsing '?a=1&b=2' into a dict. Duplicate keys become a list. Empty string returns {}. Return ONLY executable code, no markdown fences.","test":"assert parse_query('?a=1&b=2')=={'a':'1','b':'2'}\nassert parse_query('')=={}\nassert parse_query('?a=1&a=2')=={'a':['1','2']}\nprint('PASS')"}
{"task_id":"chunk_list","prompt":"Write a Python function chunk_list(lst,size) splitting lst into consecutive chunks of length size (last may be shorter). Empty list returns []. Return ONLY executable code, no markdown fences.","test":"assert chunk_list([1,2,3,4,5],2)==[[1,2],[3,4],[5]]\nassert chunk_list([],2)==[]\nassert chunk_list([1],2)==[[1]]\nprint('PASS')"}
{"task_id":"balanced_parens","prompt":"Write a Python function is_balanced(s) returning True if brackets (),[],{} are properly balanced. Empty string is balanced. Return ONLY executable code, no markdown fences.","test":"assert is_balanced('([]{})')==True\nassert is_balanced('([)]')==False\nassert is_balanced('')==True\nassert is_balanced('(')==False\nprint('PASS')"}
{"task_id":"binary_search","prompt":"Write a Python function binary_search(arr,x) returning the index of x in sorted arr, or -1 if absent. Return ONLY executable code, no markdown fences.","test":"assert binary_search([1,3,5,7],3)==1\nassert binary_search([1,3,5,7],4)==-1\nassert binary_search([],1)==-1\nassert binary_search([1,1,1],1) in (0,1,2)\nprint('PASS')"}
{"task_id":"capitalize_words","prompt":"Write a Python function capitalize_words(s) returning s with the first letter of each word uppercased and the rest lowercased, words separated by single spaces. Empty returns ''. Return ONLY executable code, no markdown fences.","test":"assert capitalize_words('hello world')=='Hello World'\nassert capitalize_words('')==''\nassert capitalize_words('HELLO')=='Hello'\nprint('PASS')"}
{"task_id":"flatten_deep","prompt":"Write a Python function flatten_deep(lst) fully flattening arbitrarily nested lists. Empty returns []. Return ONLY executable code, no markdown fences.","test":"assert flatten_deep([1,[2,[3,[4]]]])==[1,2,3,4]\nassert flatten_deep([])==[]\nassert flatten_deep([[[]]])==[]\nprint('PASS')"}
{"task_id":"unique_preserve","prompt":"Write a Python function unique_preserve(lst) removing duplicates while preserving first-occurrence order. Return ONLY executable code, no markdown fences.","test":"assert unique_preserve([1,2,1,3,2])==[1,2,3]\nassert unique_preserve([])==[]\nassert unique_preserve(['a','a'])==['a']\nprint('PASS')"}
EOF

rm -rf runs_hard signals_hard; mkdir -p runs_hard signals_hard

python3 - <<'PY'
import json, os, subprocess, sys, uuid
from collections import Counter, defaultdict
from pathlib import Path
from openai import OpenAI

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"], timeout=120)
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
tasks = [json.loads(l) for l in open("tasks_hard.jsonl") if l.strip()]

def strip_fences(s):
    s = (s or "").strip()
    if s.startswith("```"):
        s = "\n".join(s.split("\n")[1:])
        if s.rstrip().endswith("```"): s = s.rstrip()[:-3]
    return s.strip()

def classify(stdout, stderr, code):
    b = (stdout + "\n" + stderr).lower()
    if "modulenotfounderror" in b or "no module named" in b: return "dependency_missing"
    if "recursionerror" in b: return "recursion_limit"
    if "syntaxerror" in b: return "syntax_error"
    if "nameerror" in b: return "name_error"
    if "typeerror" in b: return "type_error"
    if "assertionerror" in b: return "assertion_failure"
    if "traceback" in b: return "runtime_exception"
    if not code.strip(): return "empty_output"
    return "unclassified"

def run_trial(model, task, retry_hint=None):
    tid = f"{model.replace('/','_')}__{task['task_id']}__{uuid.uuid4().hex[:6]}"
    d = Path("runs_hard")/tid; d.mkdir(parents=True, exist_ok=True)
    usr = task["prompt"] + ("\n\n" + retry_hint if retry_hint else "")
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":"Return ONLY executable Python. No markdown fences, no commentary."},
                      {"role":"user","content":usr}],
            temperature=0.0, max_tokens=1500)
        code = strip_fences(r.choices[0].message.content)
    except Exception as e:
        rec = {"task":task["task_id"],"model":model,"passed":False,"reason":"api_error","error":str(e),"retry":bool(retry_hint)}
        (d/"result.json").write_text(json.dumps(rec, indent=2)); return rec
    (d/"solution.py").write_text(code + "\n\n" + task["test"])
    try:
        p = subprocess.run([sys.executable, str(d/"solution.py")], capture_output=True, text=True, timeout=30)
        passed = p.returncode == 0 and "PASS" in p.stdout
        rec = {"task":task["task_id"],"model":model,"passed":passed,
               "reason": None if passed else classify(p.stdout,p.stderr,code),
               "stdout":p.stdout[-2000:],"stderr":p.stderr[-2000:],"code":code,"retry":bool(retry_hint)}
    except subprocess.TimeoutExpired:
        rec = {"task":task["task_id"],"model":model,"passed":False,"reason":"timeout","code":code,"retry":bool(retry_hint)}
    (d/"result.json").write_text(json.dumps(rec, indent=2)); return rec

results = []
for model in MODELS:
    for task in tasks:
        rec = run_trial(model, task)
        results.append(rec)
        print(f"P1 [{model}] {task['task_id']}: {'PASS' if rec['passed'] else 'FAIL/'+rec['reason']}")

failed = [r for r in results if not r["passed"]]
print(f"\nPhase 2: retrying {len(failed)} failures with verification framing...")
retries = []
for r in failed:
    task = next(t for t in tasks if t["task_id"] == r["task"])
    hint = ("Your previous attempt FAILED hidden unit tests. Before responding, mentally trace "
            "your code on edge cases (empty input, single element, duplicates, large n, boundary values). "
            "Return ONLY corrected executable code.")
    rr = run_trial(r["model"], task, retry_hint=hint)
    retries.append(rr)
    print(f"P2 [{r['model']}] {r['task']}: {'RECOVERED' if rr['passed'] else 'STILL_FAIL/'+str(rr['reason'])}")

with open("signals_hard/runs.jsonl","w") as f:
    for r in results + retries: f.write(json.dumps(r)+"\n")

print("\n── Pass rate by model (Phase 1) ──")
by = defaultdict(lambda: [0,0])
for r in results:
    by[r["model"]][1] += 1
    if r["passed"]: by[r["model"]][0] += 1
for m,(p,n) in by.items(): print(f"{m:32s} {p:2d}/{n:2d}  ({100*p/n:.0f}%)")

print("\n── Per-task failure matrix (Phase 1) ──")
all_tasks = [t["task_id"] for t in tasks]
print(f"{'task':24s}" + "".join(f"{m.split('/')[-1][:14]:>16s}" for m in MODELS))
for t in all_tasks:
    row = ""
    for m in MODELS:
        r = next((r for r in results if r["task"]==t and r["model"]==m), None)
        row += f"{(r['reason'] or 'PASS')[:15]:>16s}" if r else f"{'?':>16s}"
    print(f"{t:24s}{row}")

print("\n── Failure causes (Phase 1) ──")
causes = Counter(r.get("reason") or "PASS" for r in results)
for c,n in causes.most_common(): print(f"{c:24s} {n}")

if retries:
    recovered = sum(1 for r in retries if r["passed"])
    print(f"\n── Retry recovery (Phase 2) ──")
    print(f"{recovered}/{len(retries)} recovered under verification framing ({100*recovered/len(retries):.0f}%)")
    still = Counter(r["reason"] for r in retries if not r["passed"])
    if still:
        print("Remaining failure classes:")
        for c,n in still.most_common(): print(f"  {c:22s} {n}")

json.dump({"phase1_causes": dict(causes),
           "phase2_recovered": sum(1 for r in retries if r["passed"]),
           "phase2_total": len(retries)},
          open("signals_hard/summary.json","w"), indent=2)
PY

echo
echo "✅ done — inspect runs_hard/, signals_hard/runs.jsonl, signals_hard/summary.json"
