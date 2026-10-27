#!/usr/bin/env python3
"""H013: does PTE generalize to transform tasks?"""
import json, os, pathlib, re, shutil, sys, tempfile, time, urllib.request, urllib.error

TASKS = [
    {"id":"t1","goal":"read a.txt, write its UPPERCASE content to answer.txt","seed":"hello world","expected":"HELLO WORLD"},
    {"id":"t2","goal":"read a.txt, write its lowercase content to answer.txt","seed":"Hello World","expected":"hello world"},
    {"id":"t3","goal":"read a.txt, write it reversed to answer.txt","seed":"abcdef","expected":"fedcba"},
    {"id":"t4","goal":"read a.txt, strip leading/trailing whitespace and write to answer.txt","seed":"  hello  ","expected":"hello"},
    {"id":"t5","goal":"read a.txt, write its length as a number to answer.txt","seed":"hello","expected":"5"},
    {"id":"t6","goal":"read a.txt, write its words in sorted order space-separated to answer.txt","seed":"world hello","expected":"hello world"},
    {"id":"t7","goal":"read a.txt, write its uppercase AND reversed content to answer.txt","seed":"abc","expected":"CBA"},
    {"id":"t8","goal":"read a.txt, replace spaces with underscores and write to answer.txt","seed":"hello world","expected":"hello_world"},
]
SUPPORTED = {
    "uppercase": lambda s: s.upper(),
    "lowercase": lambda s: s.lower(),
    "reverse": lambda s: s[::-1],
    "strip": lambda s: s.strip(),
    "len": lambda s: str(len(s)),
    "words_sorted": lambda s: " ".join(sorted(s.split())),
    "replace_spaces": lambda s: s.replace(" ", "_"),
}
HEAD = ("You are the planner for an automated agent platform.\n"
        "Return ONLY a JSON object with this exact schema (no prose, no fences):\n")
RULES = "\nRules:\n1. Step ids unique.\n2. depends_on only prior ids.\n3. Every tool in catalog.\n4. fs_* paths relative.\n"
TOOLS = "- fs_read: read file. args: {path: str}\n- fs_write: write file. args: {path: str, content: str-or-deferred}\n"
SA = '{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, "args": object, "depends_on": [str]}]}'
SB = SA + ('\n\nFor fs_write, `content` accepts EITHER a plain string OR a deferred '
           'value object: {"__deferred__": {"from": "<step_id>", "field": "output"}}.')
SC = SA + ('\n\nFor fs_write, `content` accepts EITHER a plain string OR a deferred '
           'value object: {"__deferred__": {"from": "<step_id>", "field": "output", '
           '"transform": "<op>"}}.\n'
           'Supported transforms: ' + ", ".join(SUPPORTED) + '.\n'
           'Omit `transform` to copy the value verbatim.')
SD = SA + ('\n\nFor fs_write, `content` accepts EITHER a plain string OR a deferred '
           'value object: {"__deferred__": {"from": "<step_id>", "field": "output", '
           '"transform": "<op>"}}.\nThe transform is applied to the referenced step\'s output.')
CONDS = {"A_string":SA, "B_verbatim":SB, "C_transform_list":SC, "D_transform_free":SD}

def build(goal, schema):
    return HEAD + schema + RULES + f"\nGOAL: {goal}\n\nTOOLS:\n" + TOOLS

def call(prompt, base, model, key, retries=6):
    for i in range(retries):
        try:
            req = urllib.request.Request(f"{base}/chat/completions",
                data=json.dumps({"model":model,"messages":[{"role":"user","content":prompt}],
                                 "temperature":0.0,"max_tokens":2048}).encode(),
                headers={"Content-Type":"application/json",
                         "Authorization":f"Bearer {key}",
                         "User-Agent":"pte-xform/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(2**i); continue
            raise
    raise RuntimeError("gave up")

def parse(text):
    try: return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return json.loads(m.group(0)) if m else {}

def resolve(content, obs):
    if isinstance(content, dict) and "__deferred__" in content:
        d = content["__deferred__"]
        src = d.get("from")
        if src not in obs: return "<UNRESOLVED>", {"unresolved_from": src}
        val = obs[src]
        meta = {"deferred": True, "from": src}
        if "transform" in d:
            t = d["transform"]
            meta["transform"] = t
            if t in SUPPORTED:
                val = SUPPORTED[t](val); meta["transform_valid"] = True
            else:
                meta["transform_valid"] = False
        return val, meta
    return content, {"deferred": False}

def execute(plan, seed_files):
    wd = tempfile.mkdtemp(prefix="xform_")
    try:
        for n, v in seed_files.items(): pathlib.Path(wd, n).write_text(v)
        obs = {}
        for s in plan.get("steps", []):
            sid, tool = s.get("id"), s.get("tool")
            args = s.get("args") or {}
            if tool == "fs_read":
                try: obs[sid] = pathlib.Path(wd, args["path"]).read_text()
                except Exception as e: obs[sid] = f"<err {e}>"
            elif tool == "fs_write":
                val, meta = resolve(args.get("content"), obs)
                try: pathlib.Path(wd, args["path"]).write_text(str(val))
                except Exception: pass
                obs[sid] = str(val)
        p = pathlib.Path(wd, "answer.txt")
        return p.read_text() if p.exists() else None
    finally:
        shutil.rmtree(wd, ignore_errors=True)

def classify(plan):
    for s in plan.get("steps", []):
        if s.get("tool") == "fs_write":
            c = (s.get("args") or {}).get("content")
            if isinstance(c, dict) and "__deferred__" in c:
                if "transform" in c["__deferred__"]:
                    t = c["__deferred__"]["transform"]
                    return "deferred+transform" if t in SUPPORTED else "deferred+invalid"
                return "deferred_verbatim"
            if isinstance(c, str) and "${" in c: return "placeholder"
            if isinstance(c, str): return "literal"
    return "no_write"

base = "https://api.groq.com/openai/v1"
key = os.environ["GROQ_API_KEY"]
model = os.environ.get("PTE_MODEL", "openai/gpt-oss-20b")
print(f"[H013] {len(TASKS)} tasks x {len(CONDS)} conds = {len(TASKS)*len(CONDS)} calls on {model}\n")

results = {}
for cond, schema in CONDS.items():
    print(f"===== {cond} =====")
    rows = []
    for t in TASKS:
        try:
            reply = call(build(t["goal"], schema), base, model, key)
        except Exception as e:
            print(f"  {t['id']} ERR {type(e).__name__}"); continue
        plan = parse(reply)
        cls = classify(plan)
        final = execute(plan, {"a.txt": t["seed"]})
        ok = (final == t["expected"])
        rows.append({"task":t["id"],"class":cls,"final":final,"expected":t["expected"],"ok":ok})
        print(f"  {t['id']:3s} {cls:24s} {'OK' if ok else 'FAIL':4s} final={repr(final)[:30]}")
        time.sleep(0.5)
    results[cond] = rows
    print()

print("=" * 78)
print(f"{'condition':22s} {'deferred':>10s} {'with_xform':>11s} {'exec_ok':>9s}")
print("-" * 78)
for cond in CONDS:
    rs = results[cond]; n = len(rs)
    deferred = sum(1 for r in rs if "deferred" in r["class"])
    with_xform = sum(1 for r in rs if "transform" in r["class"])
    exec_ok = sum(1 for r in rs if r["ok"])
    print(f"{cond:22s} {deferred:>3d}/{n:<3d}   {with_xform:>3d}/{n:<3d}   {exec_ok:>3d}/{n:<3d}")

pathlib.Path("artifacts/esf/transform_test.json").write_text(json.dumps({"model":model,"results":results}, indent=2))
print(f"\n-> artifacts/esf/transform_test.json")
