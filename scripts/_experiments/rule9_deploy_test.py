import json, os, pathlib, re, sys, urllib.request
sys.path.insert(0, "scripts")
from verifier_deterministic import TEMPLATE_RE

HEAD = ("You are the planner for an automated agent platform.\n"
        "Return ONLY a JSON object with this exact schema (no prose, no fences):\n")
SCHEMA_STRING = ('{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
                 '"args": object, "depends_on": [str]}]}')
SCHEMA_TYPED = SCHEMA_STRING + (
    '\n\nFor fs_write, `content` accepts EITHER a plain string OR a deferred '
    'value object: {"__deferred__": {"from": "<step_id>", "field": "output"}}. '
    'Use the deferred form when the value comes from a prior step\'s output.')
RULES_BASE = ("\nRules:\n1. Step ids unique.\n2. depends_on only prior ids.\n"
              "3. Every tool in catalog.\n4. fs_* paths relative.\n")
RULE_9_OLD = ("9. For fs_write, the 'content' argument MUST be the literal string. "
              "Do NOT use {{...}}, $X, or reference syntax. Prior step outputs "
              "are NOT auto-substituted; you must inline the actual value.\n")
TOOLS = ("- fs_read: read file. args: {path: str}\n"
         "- fs_write: write file. args: {path: str, content: str-or-deferred}\n")

def build(goal, cond):
    if cond == "string_rule9":
        return HEAD + SCHEMA_STRING + RULES_BASE + RULE_9_OLD + f"\nGOAL: {goal}\n\nTOOLS:\n{TOOLS}"
    if cond == "typed_rule9":
        return HEAD + SCHEMA_TYPED + RULES_BASE + RULE_9_OLD + f"\nGOAL: {goal}\n\nTOOLS:\n{TOOLS}"
    raise ValueError(cond)

def call(p, base, model, key):
    req = urllib.request.Request(f"{base}/chat/completions",
        data=json.dumps({"model": model, "messages":[{"role":"user","content":p}],
                         "temperature":0.0}).encode(),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["choices"][0]["message"]["content"]

def classify(reply):
    try: plan = json.loads(reply)
    except Exception:
        m = re.search(r"\{.*\}", reply, re.DOTALL)
        plan = json.loads(m.group(0)) if m else {}
    for s in plan.get("steps", []):
        if s.get("tool") == "fs_write":
            c = (s.get("args") or {}).get("content")
            if isinstance(c, dict) and "__deferred__" in c: return "deferred"
            if isinstance(c, str):
                if TEMPLATE_RE.search(c): return "placeholder_str"
                return "literal"
    return "no_write"

def main():
    base = os.environ["AGI_BASE_URL"]; model = os.environ["AGI_MODEL"]; key = os.environ.get("AGI_API_KEY","EMPTY")
    items = [json.loads(l) for l in pathlib.Path("bench/families/test/fam14in.jsonl").read_text().splitlines() if l.strip()]
    conds = ["string_rule9", "typed_rule9"]
    print(f"[rule9] {len(items)} items x {len(conds)} conds = {len(items)*len(conds)} calls")
    rows = []
    for it in items:
        for cond in conds:
            reply = call(build(it["goal"], cond), base, model, key)
            cls = classify(reply)
            rows.append({"item": it["id"], "cond": cond, "class": cls,
                         "fail": cls not in ("deferred", "literal")})
            print(f"  {it['id']:15s} {cond:15s} {cls}")
    from collections import defaultdict
    agg = defaultdict(lambda: {"n":0, "deferred":0, "placeholder_str":0, "literal":0, "no_write":0, "fail":0})
    for r in rows:
        x = agg[r["cond"]]; x["n"] += 1; x[r["class"]] += 1; x["fail"] += int(r["fail"])
    print("\n=== rule9 deployability ===")
    for c in conds:
        x = agg[c]
        print(f"{c:15s} fail={x['fail']}/{x['n']} deferred={x['deferred']} ph={x['placeholder_str']} lit={x['literal']} nw={x['no_write']}")
    pathlib.Path("artifacts/esf/rule9_deploy.json").write_text(json.dumps({"rows": rows, "aggregate": dict(agg)}, indent=2))

main()
