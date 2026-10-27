#!/usr/bin/env python3
"""H009: does a deferral-supporting schema close Subproblem B?"""
import argparse, json, os, pathlib, re, sys, urllib.request

REPO = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from verifier_deterministic import TEMPLATE_RE

STRING_SCHEMA = (
    '{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
    '"args": object, "depends_on": [str]}]}'
)
TYPED_SCHEMA = (
    '{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
    '"args": object, "depends_on": [str]}]}\n\n'
    'The `content` arg of `fs_write` accepts EITHER:\n'
    '  - a plain string, OR\n'
    '  - a deferred value object: {"__deferred__": {"from": "<step_id>", "field": "output"}}\n'
    'Use the deferred form when the value will be produced by a prior step\'s output.'
)

SYSTEM_HEAD = (
    "You are the planner for an automated agent platform.\n"
    "Return ONLY a JSON object with this exact schema (no prose, no fences):\n"
)
RULES = (
    "\nRules:\n"
    "1. Step ids unique and short.\n"
    "2. depends_on references only prior step ids.\n"
    "3. Every tool in the catalog.\n"
    "4. fs_* paths relative to sandbox.\n"
)
TOOLS = """- fs_read: read a file. args: {path: str}
- fs_write: write a file. args: {path: str, content: str-or-deferred}
"""

def build(goal, cond, seed_name, seed_val):
    if cond.startswith("typed_holes"):
        schema = TYPED_SCHEMA
    else:
        schema = STRING_SCHEMA
    p = SYSTEM_HEAD + schema + RULES + "\nGOAL: " + goal + "\n\nTOOLS:\n" + TOOLS
    if "oracle" in cond and seed_val is not None:
        p += f"\nContext: {seed_name!r} contains {seed_val!r}\n"
    return p

def call(prompt, base, model, key):
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps({"model": model,
                         "messages": [{"role": "user", "content": prompt}],
                         "temperature": 0.0}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["choices"][0]["message"]["content"]

def parse(reply):
    try: return json.loads(reply)
    except Exception:
        m = re.search(r"\{.*\}", reply, re.DOTALL)
        return json.loads(m.group(0)) if m else {}

def classify(plan, expected):
    """Return 'deferred', 'literal_correct', 'literal_wrong', 'placeholder_str', 'no_write'."""
    for s in plan.get("steps", []):
        if s.get("tool") == "fs_write":
            c = (s.get("args") or {}).get("content")
            if isinstance(c, dict) and "__deferred__" in c:
                return "deferred"
            if isinstance(c, str):
                if TEMPLATE_RE.search(c): return "placeholder_str"
                if expected is not None and c != expected: return "literal_wrong"
                return "literal_correct"
    return "no_write"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--bench", default="bench/families/test/fam14in.jsonl")
    ap.add_argument("--out", default="artifacts/esf/typed_holes_probe.json")
    a = ap.parse_args()
    base = os.environ["AGI_BASE_URL"]; model = os.environ["AGI_MODEL"]; key = os.environ.get("AGI_API_KEY","EMPTY")
    items = [json.loads(l) for l in pathlib.Path(a.bench).read_text().splitlines() if l.strip()]
    if a.limit: items = items[:a.limit]

    conds = ["string_baseline", "string_oracle", "typed_holes", "typed_holes_oracle"]
    rows = []
    print(f"[H009] {len(items)} items x {len(conds)} conds = {len(items)*len(conds)} calls on {model}")
    for it in items:
        sf = it.get("seed_files") or {}
        seed_name = next(iter(sf.keys()), "seed.txt")
        seed_val = next(iter(sf.values()), None) if sf else None
        for cond in conds:
            try:
                reply = call(build(it["goal"], cond, seed_name, seed_val), base, model, key)
            except Exception as e:
                rows.append({"item": it["id"], "cond": cond, "error": str(e)}); continue
            plan = parse(reply)
            cls = classify(plan, seed_val)
            fail = cls in ("placeholder_str", "literal_wrong", "no_write")
            rows.append({"item": it["id"], "cond": cond, "class": cls, "fail": fail, "plan": plan,
                         "content": next((s["args"]["content"] for s in plan.get("steps",[])
                                          if s.get("tool")=="fs_write"
                                          and "args" in s and "content" in s.get("args",{})), None)})
            print(f"  {it['id']:15s} {cond:22s} class={cls:16s} content={repr(rows[-1]['content'])[:40]}")

    from collections import defaultdict
    agg = defaultdict(lambda: {"n":0, "deferred":0, "placeholder_str":0,
                                "literal_wrong":0, "literal_correct":0, "no_write":0, "fail":0})
    for r in rows:
        if "fail" not in r: continue
        x = agg[r["cond"]]
        x["n"] += 1; x[r["class"]] = x.get(r["class"],0)+1; x["fail"] += int(r["fail"])

    print("\n=== H009 result ===")
    print(f"{'cond':22s} {'fail':>8s} {'deferred':>10s} {'ph_str':>8s} {'wrong':>7s} {'correct':>9s} {'no_write':>10s}")
    for c in conds:
        x = agg[c]
        print(f"{c:22s} {x['fail']:>3d}/{x['n']:<3d} {x.get('deferred',0):>10d} "
              f"{x.get('placeholder_str',0):>8d} {x.get('literal_wrong',0):>7d} "
              f"{x.get('literal_correct',0):>9d} {x.get('no_write',0):>10d}")

    out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": model, "n_items": len(items),
                                "aggregate": dict(agg), "rows": rows}, indent=2))
    print(f"\n-> {out}")
    print("\n=== reading ===")
    sh = agg["string_baseline"]; th = agg["typed_holes"]
    if sh["n"] < 10:
        print(f"INSUFFICIENT DATA (n={sh['n']} < 10) — this is a pilot, not a result.")
        print(f"Run full: python3 scripts/typed_holes_probe.py  (no --limit)")
        return
    if th["fail"] < sh["fail"]:
        print(f"SCHEMA IS THE CAUSE: typed_holes fail {th['fail']}/{th['n']} "
              f"vs string_baseline {sh['fail']}/{sh['n']}  → typed-hole schema closes the class")
    else:
        print(f"SCHEMA DOES NOT CLOSE IT: typed_holes fail {th['fail']}/{th['n']} "
              f"vs string_baseline {sh['fail']}/{sh['n']}  → model can't use typed holes even when offered")
    if th.get("deferred",0) > 0:
        print(f"Model DID use __deferred__ {th['deferred']}/{th['n']} times → schema-expressible deferral is learnable")

if __name__ == "__main__":
    main()
