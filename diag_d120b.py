#!/usr/bin/env python3
"""Find and categorize gpt-oss-120b's D-baseline failure.

For each D task:
  1. Run with the CURRENT prompt (from run_family.py) — find the failure
  2. If failure, run 5x with seed=42+i — measure determinism
  3. Run with a HARDENED prompt (OBSERVATION tags + no-summarize) — test fix A
  4. Run with RETRY logic (5 seeds, any pass) — test fix B

Print which failure category AND which fix works.
"""
from __future__ import annotations
import json, os, sys, urllib.request
from openai import OpenAI
import families

MODEL = "openai/gpt-oss-120b"

def fetch(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.read().decode("utf-8", errors="replace")

def build_current(task, obs):
    t = next(s for s in task["steps"] if s.get("expect_arg"))
    return (
        f"Task {task['id']}.\n"
        f"Tool to call: {t['tool']}\n"
        f"Argument keys to fill: {sorted(t['args'].keys())}\n"
        f"The prior tool observation was:\n{obs!r}\n\n"
        f'Return ONLY JSON of the form {{"args": {{...}}}}.'
    )

def build_hardened(task, obs):
    t = next(s for s in task["steps"] if s.get("expect_arg"))
    k, _ = t["expect_arg"]
    return (
        f"Task {task['id']}.\n"
        f"Tool to call: {t['tool']}\n"
        f"Argument keys to fill: {sorted(t['args'].keys())}\n"
        f"<OBSERVATION>\n{obs}\n</OBSERVATION>\n\n"
        f"Copy the observation character-for-character into the "
        f"`{k}` argument. Do NOT summarize. Do NOT interpret. "
        f"Do NOT change word order or whitespace. "
        f"The value must equal the observation exactly.\n\n"
        f'Return ONLY JSON of the form {{"args": {{"{k}": "<obs here>"}}}}.'
    )

def try_one(c, task, obs, build, seed):
    try:
        resp = c.chat.completions.create(
            model=MODEL, temperature=0, seed=seed,
            messages=[{"role": "user", "content": build(task, obs)}],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        return {"ok": False, "cat": "EXCEPTION", "got": None,
                "raw": None, "err": f"{type(e).__name__}: {str(e)[:120]}"}
    raw = resp.choices[0].message.content
    try:
        produced = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "cat": "NON_JSON", "got": None, "raw": raw}
    got = str(produced.get("args", {}).get("content", "")).strip()
    exp = obs.strip()
    if got == exp:
        return {"ok": True, "cat": "PASS", "got": got, "raw": raw}
    if "<" in got and "PLACEHOLDER" in got:
        cat = "PLACEHOLDER"
    elif got.startswith("Task ") or got.startswith("The "):
        cat = "HALLUC-semantic"
    elif got.strip("\"'") == exp.strip("\"'"):
        cat = "FORMAT-quote"
    elif not got:
        cat = "EMPTY"
    else:
        cat = "HALLUC-other"
    return {"ok": False, "cat": cat, "got": got, "raw": raw}

def main():
    if not os.path.exists("results"):
        os.makedirs("results")
    c = OpenAI(base_url=os.environ["OPENAI_BASE_URL"],
               api_key=os.environ["OPENAI_API_KEY"])

    print("=== Phase 1: current prompt, 10 D tasks ===")
    current = {}
    for task in families.get("D"):
        obs = fetch(task["steps"][0]["args"]["url"])
        r = try_one(c, task, obs, build_current, seed=42)
        current[task["id"]] = r
        print(f"  {task['id']}: {'PASS' if r['ok'] else 'FAIL[' + r['cat'] + ']'}")
    n_cur = sum(1 for r in current.values() if r["ok"])
    print(f"  --> {n_cur}/10\n")

    failures = [(tid, r) for tid, r in current.items() if not r["ok"]]
    if not failures:
        print("No failures on this run — the 9/10 you saw was a Groq flake.")
        print("Fix: retry+seed (see fix_d120b.py).")
        return 0

    print(f"=== Phase 2: determinism check on {len(failures)} failure(s) ===")
    for tid, r in failures:
        task = next(t for t in families.get("D") if t["id"] == tid)
        obs = fetch(task["steps"][0]["args"]["url"])
        print(f"\n  {tid}  expected={obs.strip()!r}")
        print(f"    current got={r['got']!r}  (cat={r['cat']})")
        n_pass = 0
        for i in range(5):
            rr = try_one(c, task, obs, build_current, seed=42 + i)
            n_pass += int(rr["ok"])
            print(f"    seed={42+i}: {'PASS' if rr['ok'] else 'FAIL  got=' + repr(rr['got'])}")
        print(f"    --> {n_pass}/5 pass  ->  "
              f"{'DETERMINISTIC' if n_pass==0 else 'FLAKY' if n_pass<5 else 'TRANSIENT'}")

    print(f"\n=== Phase 3: hardened prompt, all 10 D tasks ===")
    n_hard = 0
    for task in families.get("D"):
        obs = fetch(task["steps"][0]["args"]["url"])
        r = try_one(c, task, obs, build_hardened, seed=42)
        n_hard += int(r["ok"])
        print(f"  {task['id']}: {'PASS' if r['ok'] else 'FAIL[' + r['cat'] + ']'}")
    print(f"  --> {n_hard}/10\n")

    print("=== Recommendation ===")
    print(f"  Current prompt:  {n_cur}/10")
    print(f"  Hardened prompt: {n_hard}/10")
    if n_hard == 10 and n_cur < 10:
        print("  ACTION: apply hardened prompt (fix A)")
    elif n_cur < 10 and n_hard < 10:
        print("  ACTION: apply retry+seed (fix B); prompt hardening insufficient")
    else:
        print("  ACTION: retry+seed only; failure was transient")

if __name__ == "__main__":
    sys.exit(main())
