import json, os, pathlib, re, sys, time, urllib.request, urllib.error

BASE = "https://api.groq.com/openai/v1"; KEY = os.environ["GROQ_API_KEY"]

HEAD = ("You are the planner for an automated agent platform.\n"
        "Return ONLY a JSON object with this exact schema (no prose, no fences):\n")
SCHEMA = ('{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
          '"args": object, "depends_on": [str]}]}\n\n'
          'For fs_write, `content` accepts EITHER a plain string OR a deferred '
          'value object: {"__deferred__": {"from": "<step_id>", "field": "output"}}. '
          'Use the deferred form when the value comes from a prior step\'s output.')
RULES = "\nRules:\n1. Step ids unique.\n2. depends_on only prior ids.\n3. Every tool in catalog.\n4. fs_* paths relative.\n"
TOOLS = "- fs_read: read file. args: {path: str}\n- fs_write: write file. args: {path: str, content: str-or-deferred}\n"
EXAMPLE = ('\nEXAMPLE (study the structure of `content` carefully):\n'
           'GOAL: read a.txt and write its contents to b.txt\n'
           '{"goal":"copy","steps":['
           '{"id":"s1","tool":"fs_read","args":{"path":"a.txt"},"depends_on":[]},'
           '{"id":"s2","tool":"fs_write","args":{"path":"b.txt","content":'
           '{"__deferred__":{"from":"s1","field":"output"}}},"depends_on":["s1"]}]}\n')

def build(goal):
    return HEAD + SCHEMA + RULES + EXAMPLE + f"\nGOAL: {goal}\n\nTOOLS:\n" + TOOLS

def call_with_backoff(prompt, model="allam-2-7b", retries=8):
    for i in range(retries):
        try:
            req = urllib.request.Request(f"{BASE}/chat/completions",
                data=json.dumps({"model": model,
                                 "messages": [{"role": "user", "content": prompt}],
                                 "temperature": 0.0, "max_tokens": 1024}).encode(),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {KEY}",
                         "User-Agent": "groq-python/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(2 ** i, 60)
                print(f"    429, waiting {wait}s (attempt {i+1}/{retries})")
                time.sleep(wait); continue
            raise
    raise RuntimeError("gave up after retries")

def classify(content):
    if isinstance(content, dict) and "__deferred__" in content: return "deferred"
    if isinstance(content, str) and "__deferred__" in content: return "string"
    if isinstance(content, str) and "${" in content: return "placeholder"
    if isinstance(content, str): return "literal"
    return "no_write"

def plan_class(reply):
    try: plan = json.loads(reply)
    except Exception:
        m = re.search(r"\{.*\}", reply, re.DOTALL)
        plan = json.loads(m.group(0)) if m else {}
    content = next((s["args"].get("content") for s in plan.get("steps", [])
                    if s.get("tool") == "fs_write" and s.get("args", {}).get("content")), None)
    return classify(content), content

items = [json.loads(l) for l in pathlib.Path("bench/families/test/fam14in.jsonl").read_text().splitlines() if l.strip()]

print(f"=== allam-2-7b WITH example (12 items, backoff on 429) ===\n")
tally = {"deferred": 0, "string": 0, "placeholder": 0, "literal": 0, "no_write": 0}
results = []
for i, it in enumerate(items):
    try:
        reply = call_with_backoff(build(it["goal"]))
    except Exception as e:
        print(f"  {it['id']:12s} ERROR {e}")
        continue
    cls, content = plan_class(reply)
    tally[cls] += 1
    results.append({"item": it["id"], "class": cls, "content": str(content)[:80]})
    print(f"  {it['id']:12s} {cls:12s} {str(content)[:60]}")
    time.sleep(1.2)  # gentle pacing to reduce 429

print(f"\ntally: {tally}")
print(f"adoption rate: {tally['deferred']}/{sum(tally.values())} = {tally['deferred']/max(1,sum(tally.values())):.0%}")

pathlib.Path("artifacts/esf/allam_example_test.json").write_text(
    json.dumps({"tally": tally, "results": results}, indent=2))
