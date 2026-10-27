#!/usr/bin/env python3
"""Deployability test: does PTE work when rule 9 is still in the prompt?"""
import argparse, json, os, pathlib, re, sys, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from verifier_deterministic import TEMPLATE_RE

SCHEMA_TYPED = (
    '{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
    '"args": object, "depends_on": [str]}]}\n\n'
    'The `content` arg of `fs_write` accepts EITHER a plain string, OR a deferred '
    'value object: {"__deferred__": {"from": "<step_id>", "field": "output"}}. '
    'Use the deferred form when the value comes from a prior step\'s output.'
)
SCHEMA_STRING = (
    '{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
    '"args": object, "depends_on": [str]}]}'
)
HEAD = ("You are the planner for an automated agent platform.\n"
        "Return ONLY a JSON object with this exact schema (no prose, no fences):\n")
RULES_BASE = (
    "\nRules:\n"
    "1. Step ids unique and short.\n"
    "2. depends_on references only prior step ids.\n"
    "3. Every tool in the catalog.\n"
    "4. fs_* paths relative to sandbox.\n"
)
RULE_9_OLD = (
    "9. For fs_write, the 'content' argument MUST be the literal string. "
    "Do NOT use {{...}}, $X, or reference syntax. Prior step outputs are "
    "NOT auto-substituted; you must inline the actual value.\n"
)
RULE_9_NEW = (
    "9. For fs_write, when the content comes from a prior step's output, use "
    "the deferred value object {\"__deferred__\": {\"from\": \"<step_id>\", "
    "\"field\": \"output\"}}. Do NOT use string markers like {{...}} or $X.\n"
)
TOOLS = """- fs_read: read a file. args: {path: str}
- fs_write: write a file. args: {path: str, content: str-or-deferred}
"""

def build(goal, cond, seed_name, seed_val):
    if cond == "string_baseline":
        return HEAD + SCHEMA_STRING + RULES_BASE + "\nGOAL: " + goal + "\n\nTOOLS:\n" + TOOLS
    if cond == "typed_no_rule9":
        return HEAD + SCHEMA_TYPED + RULES_BASE + "\nGOAL: " + goal + "\n\nTOOLS:\n" + TOOLS
    if cond == "typed_with_old_rule9":
        return HEAD + SCHEMA_TYPED + RULES_BASE + RULE_9_OLD + "\nGOAL: " + goal + "\n\nTOOLS:\n" + TOOLS
    if cond == "typed_with_new_rule9":
        return HEAD + SCHEMA_TYPED + RULES_BASE + RULE_9_NEW + "\nGOAL: " + goal + "\n\nTOOLS:\n" + TOOLS
    raise ValueError(cond)

def call(p, base, model, key):
    req = urllib.request.Request(f"{base}/chat/completions",
        data=json.dumps({"model": model, "messages":[{"role":"user","content":p}],
                         "temperature":0.0}).encode(),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["choices"][0]["message"]["content"]

def classify(plan):
    for s in plan.get("steps", []):
        if s.get("tool") == "fs_write":
            c = (s.get("args") or {}).get("content")
            if isinstance(c, dict) and "__deferred__" in c: return "deferred"
            if isinstance(c, str):
                if TEMPLATE_RE.search(c): return "placeholder_str"
                return "literal"
    return "no_write"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="bench/families/test/fam14in.jsonl")
    ap.add_argument("--out", default="artifacts/esf/typed_holes_rule9.json")
    a = ap.parse_args()
    base = os.environ["AGI_BASE_URL"]; model = os.environ["AGI_MODEL"]; key = os.environ.get("AGI_API_KEY","EMPTY")
    items = [json.loads(l) for l in pathlib.Path(a.bench).read_text().splitlines() if l.strip()]
    conds = ["string_baseline", "typed_no_rule9", "typed_with_old_rule9", "typed_with_new_rule9"]
    print(f"[H011] {len(items)} items x {len(conds)} conds = {len(items)*len(conds)} calls")
    rows = []
    for it in items:
        sf = it.get("seed_files") or {}
        seed_name = next(iter(sf.keys()), "seed.txt")
        seed_val = next(iter(sf.values()), None) if sf else None
        for cond in conds:
            try:
                reply = call(build(it["goal"], cond, seed_name, seed_val), base, model, key)
            except Exception as e:
                rows.append({"item": it["id"], "cond": cond, "error": str(e)}); continue
            try: plan = json.loads(reply)
            except Exception:
                m = re.search(r"\{.*\}", reply, re.DOTALL)
                plan = json.loads(m.group(0)) if m else {}
            cls = classify(plan)
            rows.append({"item": it["id"], "cond": cond, "class": cls,
                         "fail": cls not in ("deferred", "literal"),
                         "plan": plan})
            print(f"  {it['id']:15s} {cond:24s} {cls}")
    from collections import defaultdict
    agg = defaultdict(lambda: {"n":0, "deferred":0, "placeholder_str":0, "literal":0, "no_write":0, "fail":0})
    for r in rows:
        if "class" not in r: continue
        x = agg[r["cond"]]
        x["n"] += 1; x[r["class"]] += 1; x["fail"] += int(r["fail"])
    print("\n=== H011 result ===")
    for c in conds:
        x = agg[c]
        print(f"{c:24s} fail={x['fail']}/{x['n']:<3d} deferred={x['deferred']:<3d} "
              f"ph={x['placeholder_str']:<3d} lit={x['literal']:<3d} nw={x['no_write']}")
    pathlib.Path(a.out).write_text(json.dumps({"rows": rows, "aggregate": dict(agg)}, indent=2))
    print(f"\n-> {a.out}")

if __name__ == "__main__":
    main()
