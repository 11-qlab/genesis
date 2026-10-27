#!/usr/bin/env python3
"""Typed_holes only, 4 models, 12 items each = 48 calls. Cross-model test."""
import json, os, pathlib, re, shutil, sys, tempfile, time, urllib.request, urllib.error

HEAD = ("You are the planner for an automated agent platform.\n"
        "Return ONLY a JSON object with this exact schema (no prose, no fences):\n")
SCHEMA = ('{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
          '"args": object, "depends_on": [str]}]}\n\n'
          'For fs_write, `content` accepts EITHER a plain string OR a deferred '
          'value object: {"__deferred__": {"from": "<step_id>", "field": "output"}}. '
          'Use the deferred form when the value comes from a prior step\'s output.')
RULES = "\nRules:\n1. Step ids unique.\n2. depends_on only prior ids.\n3. Every tool in catalog.\n4. fs_* paths relative.\n"
TOOLS = "- fs_read: read file. args: {path: str}\n- fs_write: write file. args: {path: str, content: str-or-deferred}\n"

def build(goal):
    return HEAD + SCHEMA + RULES + f"\nGOAL: {goal}\n\nTOOLS:\n" + TOOLS

def call(prompt, base, model, key, retries=6):
    for i in range(retries):
        try:
            req = urllib.request.Request(f"{base}/chat/completions",
                data=json.dumps({"model": model,
                                 "messages": [{"role": "user", "content": prompt}],
                                 "temperature": 0.0,
                                 "max_tokens": 2048}).encode(),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}",
                         "User-Agent": "groq-python/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.load(r)
            m = d["choices"][0]["message"]
            return m.get("content") or ""
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            if e.code == 429 and i < retries - 1:
                time.sleep(2 ** i); continue
            raise RuntimeError(f"HTTP {e.code}: {body[:100]}")
        except Exception:
            if i < retries - 1: time.sleep(2); continue
            raise

def parse_plan(text):
    if not text: return {}
    try: return json.loads(text)
    except Exception: pass
    for m in re.finditer(r"\{.*\}", text, re.DOTALL):
        try: return json.loads(m.group(0))
        except Exception: continue
    return {}

def execute(plan, seed_files):
    wd = tempfile.mkdtemp(prefix="x_")
    try:
        for n, v in seed_files.items():
            pathlib.Path(wd, n).write_text(v)
        obs = {}
        for s in plan.get("steps", []):
            sid, tool = s.get("id"), s.get("tool")
            args = s.get("args") or {}
            if tool == "fs_read":
                try: obs[sid] = pathlib.Path(wd, args["path"]).read_text()
                except Exception as e: obs[sid] = f"<err {e}>"
            elif tool == "fs_write":
                c = args.get("content")
                if isinstance(c, dict) and "__deferred__" in c:
                    c = obs.get(c["__deferred__"].get("from"), "<UNRESOLVED>")
                try: pathlib.Path(wd, args["path"]).write_text(str(c))
                except Exception: pass
                obs[sid] = str(c)
        p = pathlib.Path(wd, "answer.txt")
        return p.read_text() if p.exists() else None
    finally:
        shutil.rmtree(wd, ignore_errors=True)

base = "https://api.groq.com/openai/v1"
key = os.environ["GROQ_API_KEY"]
models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "allam-2-7b"]
items = [json.loads(l) for l in pathlib.Path("bench/families/test/fam14in.jsonl").read_text().splitlines() if l.strip()]

print(f"[fast] 4 models x {len(items)} items = 48 calls\n")
results = {}
for model in models:
    print(f"===== {model} =====")
    ok = 0; n = 0
    for it in items:
        sf = it.get("seed_files") or {}
        exp = next(iter(sf.values()), None) if sf else None
        try:
            reply = call(build(it["goal"]), base, model, key)
        except Exception as e:
            print(f"  {it['id']:12s} ERR {str(e)[:60]}"); continue
        plan = parse_plan(reply)
        final = execute(plan, sf)
        correct = (final == exp)
        n += 1; ok += int(correct)
        print(f"  {it['id']:12s} exec={'OK' if correct else 'FAIL'}")
        time.sleep(0.5)
    results[model] = {"n": n, "ok": ok}
    print(f"  → {ok}/{n}\n")

print("=" * 60)
print(f"{'model':35s} {'exec_ok':>12s}")
print("-" * 60)
for m, r in results.items():
    print(f"{m[:35]:35s} {r['ok']:>3d}/{r['n']:<3d}")
pathlib.Path("artifacts/esf/cross_groq_typed.json").write_text(json.dumps(results, indent=2))
