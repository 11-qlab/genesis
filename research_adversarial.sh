#!/usr/bin/env bash
set -uo pipefail
if [[ -z "${GROQ_API_KEY:-}" ]]; then read -rsp "Groq key: " GROQ_API_KEY; echo; export GROQ_API_KEY; fi
[[ -z "$GROQ_API_KEY" ]] && { echo "No key"; exit 1; }
[[ -d .venv-nodocker ]] || python3 -m venv .venv-nodocker
source .venv-nodocker/bin/activate
pip install --quiet --upgrade pip openai

cat > tasks_adv.jsonl <<'EOF'
{"task_id":"second_largest","prompt":"Write a Python function second_largest(lst) that returns the second largest *distinct* value in lst, or None if there are fewer than 2 distinct values. Return ONLY executable code, no markdown fences.","test":"assert second_largest([1,2,3,4])==3\nassert second_largest([5,5,4])==4\nassert second_largest([1,1]) is None\nassert second_largest([]) is None\nassert second_largest([3]) is None\nprint('PASS')"}
{"task_id":"binary_search_leftmost","prompt":"Write a Python function binary_search_leftmost(arr,x) returning the LEFTMOST index of x in a sorted list arr (which may contain duplicates), or -1 if absent. Must run in O(log n). Return ONLY executable code, no markdown fences.","test":"assert binary_search_leftmost([1,2,2,2,3],2)==1\nassert binary_search_leftmost([1,2,3],4)==-1\nassert binary_search_leftmost([],1)==-1\nassert binary_search_leftmost([2,2,2],2)==0\nprint('PASS')"}
{"task_id":"rotate_right","prompt":"Write a Python function rotate_right(lst,k) returning lst rotated right by k positions. k may be 0, negative, or larger than len(lst). Empty list returns []. Return ONLY executable code, no markdown fences.","test":"assert rotate_right([1,2,3],1)==[3,1,2]\nassert rotate_right([1,2,3],0)==[1,2,3]\nassert rotate_right([1,2,3],4)==[3,1,2]\nassert rotate_right([],5)==[]\nassert rotate_right([1,2,3],-1)==[2,3,1]\nprint('PASS')"}
{"task_id":"approximately_equal","prompt":"Write a Python function approximately_equal(a,b,rel=1e-9) returning True if a and b are equal up to relative AND absolute tolerance. Handle zero safely. Return ONLY executable code, no markdown fences.","test":"assert approximately_equal(0.1+0.2,0.3)\nassert approximately_equal(0.0,1e-12)\nassert approximately_equal(1.0,1.0)\nassert not approximately_equal(1.0,2.0)\nassert not approximately_equal(1e-9,1e9)\nprint('PASS')"}
{"task_id":"valid_ipv4","prompt":"Write a Python function valid_ipv4(s) returning True iff s is a valid IPv4 address: exactly 4 dot-separated octets, each an integer 0-255, with NO leading zeros (except '0' itself). Return ONLY executable code, no markdown fences.","test":"assert valid_ipv4('192.168.1.1')\nassert not valid_ipv4('256.1.1.1')\nassert not valid_ipv4('01.2.3.4')\nassert not valid_ipv4('1.2.3')\nassert not valid_ipv4('1.2.3.4.5')\nassert valid_ipv4('0.0.0.0')\nassert not valid_ipv4('')\nprint('PASS')"}
{"task_id":"remove_duplicates_in_place","prompt":"Write a Python function remove_duplicates_in_place(lst) that removes duplicates from lst IN PLACE (preserving first-occurrence order) and returns the new length. lst[:return_value] must contain the deduplicated elements. Return ONLY executable code, no markdown fences.","test":"_l=[1,1,2]; _n=remove_duplicates_in_place(_l); assert _n==2 and _l[:_n]==[1,2]\n_l=[]; _n=remove_duplicates_in_place(_l); assert _n==0\n_l=[1,1,1]; _n=remove_duplicates_in_place(_l); assert _n==1 and _l[:_n]==[1]\nprint('PASS')"}
{"task_id":"interp_linspace","prompt":"Write a Python function interp_linspace(start,stop,n) returning a list of n evenly spaced floats from start to stop inclusive. n must be >= 1; n=1 returns [start]. Return ONLY executable code, no markdown fences.","test":"r=interp_linspace(0,10,5); assert len(r)==5 and all(abs(a-b)<1e-9 for a,b in zip(r,[0,2.5,5,7.5,10]))\nassert interp_linspace(0,10,1)==[0.0]\nassert interp_linspace(0,10,2)==[0.0,10.0]\nprint('PASS')"}
{"task_id":"longest_common_prefix","prompt":"Write a Python function longest_common_prefix(strs) returning the longest common prefix of a list of strings, or '' if none. Handle empty list. Return ONLY executable code, no markdown fences.","test":"assert longest_common_prefix(['flower','flow','flight'])=='fl'\nassert longest_common_prefix(['abc'])=='abc'\nassert longest_common_prefix([])==''\nassert longest_common_prefix(['','a'])==''\nassert longest_common_prefix(['ab','a'])=='a'\nprint('PASS')"}
{"task_id":"roman_to_int","prompt":"Write a Python function roman_to_int(s) converting a Roman numeral (with subtractive notation like IV=4, IX=9, XL=40, XC=90, CD=400, CM=900) to its integer value. Return ONLY executable code, no markdown fences.","test":"assert roman_to_int('I')==1\nassert roman_to_int('IV')==4\nassert roman_to_int('IX')==9\nassert roman_to_int('MCMXCIV')==1994\nassert roman_to_int('XLII')==42\nprint('PASS')"}
{"task_id":"is_anagram","prompt":"Write a Python function is_anagram(a,b) returning True iff a and b are anagrams, ignoring spaces and case. Return ONLY executable code, no markdown fences.","test":"assert is_anagram('Listen','Silent')\nassert is_anagram('A man','nam a')\nassert not is_anagram('abc','abd')\nassert is_anagram('','')\nprint('PASS')"}
EOF

rm -rf runs_adv signals_adv; mkdir -p runs_adv signals_adv

python3 - <<'PY'
import json, os, subprocess, sys, uuid, re
from collections import Counter, defaultdict
from pathlib import Path
from openai import OpenAI

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"], timeout=120)
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
TASKS  = [json.loads(l) for l in open("tasks_adv.jsonl") if l.strip()]
TRIALS = 3

# ── Code-level bug classification (mechanism, not symptom) ──────────────────
BUG_PATTERNS = [
  ("dup_max_bug",       r"sorted\(\s*\w+\s*\)\s*\[\s*-\s*2\s*\]"),                  # second_largest w/ dups
  ("index_not_leftmost",r"\.index\("),                                              # binary_search uses .index
  ("range_off_by_one",  r"for\s+\w+\s+in\s+range\(\s*len\(\s*\w+\s*\)\s*-\s*1\s*\)"),
  ("abs_only_tol",      r"abs\([^)]+\)\s*<[^)]*rel\s*$"),                          # approximately_equal
  ("missing_zero_check",r"int\([^)]+\)"),                                          # valid_ipv4 int() w/o leading-zero check
  ("returns_new_list",  r"return\s+\w+\s*$"),                                      # remove_duplicates returns new
  ("div_by_n_minus_1",  r"/\s*\(\s*n\s*-\s*1\s*\)"),                                # linspace n=1
  ("empty_index",       r"\w+\[\s*0\s*\]\s*$"),                                    # lcp returns strs[0]
  ("no_subtractive",    r"sum\("),                                                  # roman_to_int
  ("strict_lt_interval",r"if\s+\w+\[\s*1\s*\]\s*<\s*\w+\[\s*0\s*\]"),              # merge_intervals touch
  ("no_strip_case",     r"\.lower\(\)"),                                            # is_anagram
  ("none_handling_missing", r"if\s+not\s+\w+\s*:"),
]

def classify_bug(code, task_id):
    hits = []
    for name, pat in BUG_PATTERNS:
        if re.search(pat, code, re.MULTILINE):
            hits.append(name)
    return hits[:3]  # top 3 hits

def classify_runtime(stdout, stderr):
    b = (stdout + "\n" + stderr).lower()
    if "recursionerror" in b: return "recursion_limit"
    if "syntaxerror" in b: return "syntax_error"
    if "nameerror" in b: return "name_error"
    if "typeerror" in b: return "type_error"
    if "indexerror" in b: return "index_error"
    if "zerodivision" in b: return "zero_division"
    if "assertionerror" in b: return "assertion_failure"
    if "traceback" in b: return "runtime_exception"
    return "unclassified"

def strip_fences(s):
    s = (s or "").strip()
    if s.startswith("```"):
        s = "\n".join(s.split("\n")[1:])
        if s.rstrip().endswith("```"): s = s.rstrip()[:-3]
    return s.strip()

def run_trial(model, task, trial_idx):
    tid = f"{model.replace('/','_')}__{task['task_id']}__t{trial_idx}__{uuid.uuid4().hex[:4]}"
    d = Path("runs_adv")/tid; d.mkdir(parents=True, exist_ok=True)
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":"Return ONLY executable Python. No markdown fences, no commentary."},
                      {"role":"user","content":task["prompt"]}],
            temperature=0.0, max_tokens=1500)
        code = strip_fences(r.choices[0].message.content)
    except Exception as e:
        return {"task":task["task_id"],"model":model,"trial":trial_idx,"passed":False,
                "reason":"api_error","error":str(e),"bugs":[],"code":""}

    (d/"solution.py").write_text(code + "\n\n" + task["test"])
    try:
        p = subprocess.run([sys.executable, str(d/"solution.py")], capture_output=True, text=True, timeout=30)
        passed = p.returncode == 0 and "PASS" in p.stdout
        reason = None if passed else classify_runtime(p.stdout, p.stderr)
        bugs = [] if passed else classify_bug(code, task["task_id"])
        return {"task":task["task_id"],"model":model,"trial":trial_idx,"passed":passed,
                "reason":reason,"bugs":bugs,"stdout":p.stdout[-1500:],"stderr":p.stderr[-1500:],"code":code}
    except subprocess.TimeoutExpired:
        return {"task":task["task_id"],"model":model,"trial":trial_idx,"passed":False,
                "reason":"timeout","bugs":["infinite_loop_or_heavy"],"code":code}

results = []
for model in MODELS:
    for task in TASKS:
        for t in range(TRIALS):
            r = run_trial(model, task, t)
            results.append(r)
            mark = "✓" if r["passed"] else f"✗ {r['reason']}:{','.join(r['bugs']) or '?'}"
            print(f"[{model.split('/')[-1]:14s}] {task['task_id']:28s} t{t} {mark}")

with open("signals_adv/runs.jsonl","w") as f:
    for r in results: f.write(json.dumps(r)+"\n")

# ── Per-cell failure rate (out of TRIALS) ───────────────────────────────────
print("\n── Per-cell failure rate (failed / trials) ──")
cells = defaultdict(lambda: [0,0])
for r in results:
    cells[(r["task"], r["model"])][1] += 1
    if not r["passed"]: cells[(r["task"], r["model"])][0] += 1

short = lambda m: m.split("/")[-1][:14]
print(f"{'task':28s}" + "".join(f"{short(m):>16s}" for m in MODELS))
for task in [t["task_id"] for t in TASKS]:
    row = ""
    for m in MODELS:
        f,n = cells[(task,m)]
        row += f"{f}/{n}".rjust(16)
    print(f"{task:28s}{row}")

# ── Failure mechanism distribution ─────────────────────────────────────────
print("\n── Mechanism distribution (all failures) ──")
mech = Counter()
for r in results:
    if r["passed"]: continue
    if r["bugs"]:
        for b in r["bugs"]: mech[b] += 1
    else:
        mech[r["reason"]] += 1
for m,n in mech.most_common(): print(f"  {m:28s} {n}")

# ── Model-specific vs task-specific vs universal ────────────────────────────
print("\n── Failure scope per task ──")
for task in [t["task_id"] for t in TASKS]:
    models_failed = [m for m in MODELS if cells[(task,m)][0] > 0]
    if not models_failed: scope = "clean (all pass)"
    elif len(models_failed) == 1: scope = f"model_specific ({models_failed[0].split('/')[-1]})"
    elif len(models_failed) == len(MODELS): scope = "universal (task too hard?)"
    else: scope = f"partial ({len(models_failed)}/{len(MODELS)} models)"
    print(f"  {task:28s} {scope}")

json.dump({"cells": {f"{t}__{m}": {"fail": c[0], "n": c[1]} for (t,m),c in cells.items()},
           "mechanisms": dict(mech),
           "total_runs": len(results),
           "total_failures": sum(1 for r in results if not r["passed"])},
          open("signals_adv/summary.json","w"), indent=2)
PY

echo
echo "✅ done — inspect runs_adv/, signals_adv/runs.jsonl, signals_adv/summary.json"
