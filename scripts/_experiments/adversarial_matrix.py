import json, os, pathlib, re, sys, time, urllib.request
sys.path.insert(0, "scripts")
from verifier_deterministic import TEMPLATE_RE

HEAD = ("You are the planner for an automated agent platform.\n"
        "Return ONLY a JSON object with this exact schema (no prose, no fences):\n")
SCHEMA = ('{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
          '"args": object, "depends_on": [str]}]}\n\n'
          'For fs_write, `content` accepts EITHER a plain string OR a deferred '
          'value object: {"__deferred__": {"from": "<step_id>", "field": "output"}}. '
          'Use the deferred form when the value comes from a prior step\'s output.')
RULES = ("\nRules:\n1. Step ids unique.\n2. depends_on only prior ids.\n"
         "3. Every tool in catalog.\n4. fs_* paths relative.\n")
TOOLS = ("- fs_read: read file. args: {path: str}\n"
         "- fs_write: write file. args: {path: str, content: str-or-deferred}\n")

EX = ('Example plan for a related task:\n'
      '{"goal":"copy a.txt to b.txt","steps":['
      '{"id":"s1","title":"read","tool":"fs_read","args":{"path":"a.txt"},"depends_on":[]},'
      '{"id":"s2","title":"write","tool":"fs_write","args":{"path":"b.txt",'
      '"content":"${s1.output}"},"depends_on":["s1"]}]}\n'
      'Follow this pattern.\n')

CONDS = {
    "control":              "",                                       # no pressure
    "explicit_forbid":      "9. For fs_write, do NOT use the deferred object. "
                            "Use the string marker ${step_id.output} instead.\n",
    "explicit_forbid_soft": "9. It is strongly preferred that fs_write.content be "
                            "a plain literal string, not a deferred object.\n",
    "soft_prefer":          "Prefer simple string values when possible.\n",
    "vague_warn":           "Avoid complex object structures in the content argument.\n",
    "example_pressure":     EX,
    "explicit_allow":       "You may use either a plain string or the deferred form. "
                            "Both are accepted.\n",
}

def build(goal, cond):
    return HEAD + SCHEMA + RULES + CONDS[cond] + f"\nGOAL: {goal}\n\nTOOLS:\n" + TOOLS

def call(p, base, m, k, retries=3, timeout=240):
    for i in range(retries):
        try:
            req = urllib.request.Request(f"{base}/chat/completions",
                data=json.dumps({"model":m,"messages":[{"role":"user","content":p}],
                                 "temperature":0.0}).encode(),
                headers={"Content-Type":"application/json","Authorization":f"Bearer {k}"})
            return json.load(urllib.request.urlopen(req, timeout=timeout))["choices"][0]["message"]["content"]
        except Exception as e:
            if i < retries-1: time.sleep(3)
            else: raise

def classify(reply, expected):
    try: plan = json.loads(reply)
    except Exception:
        mm = re.search(r"\{.*\}", reply, re.DOTALL)
        plan = json.loads(mm.group(0)) if mm else {}
    for s in plan.get("steps", []):
        if s.get("tool") == "fs_write":
            c = (s.get("args") or {}).get("content")
            if isinstance(c, dict) and "__deferred__" in c: return "deferred"
            if isinstance(c, str):
                if TEMPLATE_RE.search(c): return "placeholder"
                if expected is not None and c != expected: return "wrong_literal"
                return "literal_ok"
    return "no_write"

def main():
    base = os.environ["AGI_BASE_URL"]; m = os.environ["AGI_MODEL"]; k = os.environ.get("AGI_API_KEY","EMPTY")
    items = [json.loads(l) for l in pathlib.Path("bench/families/test/fam14in.jsonl").read_text().splitlines() if l.strip()]
    conds = list(CONDS.keys())
    print(f"[matrix] {len(items)} items × {len(conds)} conds = {len(items)*len(conds)} calls on {m}\n")
    from collections import defaultdict
    agg = defaultdict(lambda: defaultdict(int))
    rows = []
    for it in items:
        sf = it.get("seed_files") or {}
        exp = next(iter(sf.values()), None) if sf else None
        for cond in conds:
            try:
                reply = call(build(it["goal"], cond), base, m, k)
            except Exception as e:
                print(f"  {it['id']:14s} {cond:22s} ERROR: {e}"); continue
            cls = classify(reply, exp)
            agg[cond][cls] += 1
            rows.append({"item": it["id"], "cond": cond, "class": cls})
            print(f"  {it['id']:14s} {cond:22s} {cls}")
        print()

    print("=" * 70)
    print(f"{'condition':24s} {'deferred':>9s} {'ph':>4s} {'wrong':>6s} {'lit_ok':>7s} {'nowrite':>8s}")
    print("-" * 70)
    for c in conds:
        x = agg[c]
        print(f"{c:24s} {x['deferred']:>9d} {x['placeholder']:>4d} {x['wrong_literal']:>6d} "
              f"{x['literal_ok']:>7d} {x['no_write']:>8d}")

    # Pressure curve: deferred count by condition
    print("\n=== pressure curve (deferred / 12) ===")
    order = ["control", "explicit_allow", "vague_warn", "soft_prefer",
             "example_pressure", "explicit_forbid_soft", "explicit_forbid"]
    for c in order:
        if c in agg:
            bar = "#" * agg[c]["deferred"]
            print(f"{c:24s} {agg[c]['deferred']:>2d}/12  {bar}")

    pathlib.Path("artifacts/esf/adversarial_matrix.json").write_text(
        json.dumps({"model": m, "aggregate": {k: dict(v) for k, v in agg.items()},
                    "rows": rows}, indent=2))
    print(f"\n-> artifacts/esf/adversarial_matrix.json")

if __name__ == "__main__":
    main()
