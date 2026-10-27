#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

python3 - <<'PY'
import json, re
from collections import Counter, defaultdict
from pathlib import Path

BUG_PATTERNS = [
    ("dup_max_bug",        r"sorted\(\s*\w+\s*\)\s*\[\s*-\s*2\s*\]"),
    ("index_not_leftmost", r"\.index\("),
    ("range_off_by_one",   r"for\s+\w+\s+in\s+range\(\s*len\(\s*\w+\s*\)\s*-\s*1\s*\)"),
    ("abs_tol_zero_default", r"abs_tol\s*=\s*0(?:\.0)?\b"),
    ("div_by_n_minus_1",   r"/\s*\(\s*n\s*-\s*1\s*\)"),
    ("strict_lt_interval", r"if\s+\w+\[\s*1\s*\]\s*<\s*\w+\[\s*0\s*\]"),
]

def classify_bug(code, task_id):
    if not code.strip():
        return ["empty_output"]
    hits = []
    for name, pat in BUG_PATTERNS:
        if re.search(pat, code, re.MULTILINE):
            hits.append(name)
    # fire only on isclose calls that omit abs_tol
    for m in re.finditer(r"math\.isclose\(([^)]*)\)", code):
        if "abs_tol" not in m.group(1):
            hits.append("isclose_no_abs_tol"); break
    # restricted to the in-place task
    if task_id == "remove_duplicates_in_place" and re.search(r"return\s+\w+\s*$", code, re.MULTILINE):
        hits.append("returns_new_list")
    return hits[:3]

def classify_runtime(stdout, stderr, code):
    if not code.strip():
        return "empty_output"
    b = (stdout + "\n" + stderr).lower()
    for k, v in [
        ("recursion_limit", "recursionerror"),
        ("syntax_error", "syntaxerror"),
        ("name_error", "nameerror"),
        ("type_error", "typeerror"),
        ("index_error", "indexerror"),
        ("zero_division", "zerodivision"),
        ("assertion_failure", "assertionerror"),
        ("runtime_exception", "traceback"),
    ]:
        if v in b: return k
    return "unclassified"

records = [json.loads(l) for l in open("signals_adv/runs.jsonl") if l.strip()]
for r in records:
    code = r.get("code", "") or ""
    if r["passed"]:
        r["reason_v2"] = None; r["bugs_v2"] = []
    else:
        r["reason_v2"] = classify_runtime(r.get("stdout",""), r.get("stderr",""), code)
        r["bugs_v2"] = classify_bug(code, r["task"])

Path("signals_adv/runs_v2.jsonl").write_text("".join(json.dumps(r)+"\n" for r in records))

print("=== Mechanism distribution (v2) ===")
mech = Counter()
for r in records:
    if r["passed"]: continue
    for b in (r["bugs_v2"] or [r["reason_v2"]]):
        mech[b] += 1
for m,n in mech.most_common(): print(f"  {m:30s} {n}")

print("\n=== Per-task failure rate by model (v2) ===")
cells = defaultdict(lambda: [0,0])
for r in records:
    cells[(r["task"], r["model"])][1] += 1
    if not r["passed"]: cells[(r["task"], r["model"])][0] += 1
models = sorted(set(r["model"] for r in records))
print(f"{'task':28s}" + "".join(f"{m.split('/')[-1][:14]:>18s}" for m in models))
for task in sorted(set(r["task"] for r in records)):
    row = "".join(f"{cells[(task,m)][0]}/{cells[(task,m)][1]}".rjust(18) for m in models)
    print(f"{task:28s}{row}")

print("\n=== Empty-output cases (v2) ===")
for r in records:
    if r.get("reason_v2") == "empty_output":
        print(f"  {r['model']} / {r['task']} / trial {r.get('trial')}")
PY
