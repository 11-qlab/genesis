import json, os, pathlib, re, urllib.request
SCHEMA = (
    '{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
    '"args": object, "depends_on": [str]}]}\n\n'
    'For fs_write, `content` accepts EITHER a plain string OR a deferred '
    'value object: {"__deferred__": {"from": "<step_id>", "field": "output"}}. '
    'Use the deferred form when the value comes from a prior step\'s output.')
HEAD = ("You are the planner for an automated agent platform.\n"
        "Return ONLY a JSON object with this exact schema (no prose, no fences):\n")
RULES = ("\nRules:\n1. Step ids unique.\n2. depends_on only prior ids.\n"
         "3. Every tool in catalog.\n4. fs_* paths relative.\n")
TOOLS = ("- fs_read: read file. args: {path: str}\n"
         "- fs_write: write file. args: {path: str, content: str-or-deferred}\n")

GOAL = ("write seed.txt='X42'. read seed.txt and write its contents to mid.txt. "
        "read mid.txt and write its contents to answer.txt.")

def call(p, base, m, k):
    req = urllib.request.Request(f"{base}/chat/completions",
        data=json.dumps({"model":m,"messages":[{"role":"user","content":p}],"temperature":0.0}).encode(),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {k}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["choices"][0]["message"]["content"]

base=os.environ["AGI_BASE_URL"]; m=os.environ["AGI_MODEL"]; k=os.environ.get("AGI_API_KEY","EMPTY")
n_deferrals_total=0; n_correct_chain=0; n_plans=3
for run in range(n_plans):
    reply = call(HEAD+SCHEMA+RULES+f"\nGOAL: {GOAL}\n\nTOOLS:\n"+TOOLS, base, m, k)
    try: plan=json.loads(reply)
    except Exception:
        mm=re.search(r"\{.*\}",reply,re.DOTALL); plan=json.loads(mm.group(0)) if mm else {}
    steps = plan.get("steps",[])
    ids = [s.get("id") for s in steps]
    deferrals = []
    for s in steps:
        c=(s.get("args") or {}).get("content")
        if isinstance(c,dict) and "__deferred__" in c:
            deferrals.append({"step":s.get("id"),"from":c["__deferred__"].get("from")})
    # all deferral refs must point at a real prior step
    valid = all(d["from"] in ids for d in deferrals)
    n_deferrals_total += len(deferrals)
    if valid and len(deferrals)>=2: n_correct_chain += 1
    print(f"  run{run}: steps={ids} deferrals={deferrals} valid={valid}")
print(f"\navg deferrals/plan: {n_deferrals_total/n_plans:.1f}")
print(f"plans with >=2 correct deferrals: {n_correct_chain}/{n_plans}")
