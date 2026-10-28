#!/usr/bin/env python3
"""80_minimal_differential.py — 3 name contrasts x 2 Groq families = 36 calls.
Cross-family bar matches the paper (gpt-oss + qwen, N=49 each already established).
No tunnel, no Gemini, no retired-model churn."""
import asyncio, json, os, re, sys
from collections import defaultdict
from pathlib import Path
import aiohttp

OUT = Path(__file__).resolve().parent / "state" / "minimal_differential.jsonl"
OUT.parent.mkdir(exist_ok=True)

KEY = os.environ.get("GROQ_API_KEY")
if not KEY:
    print("ERROR: GROQ_API_KEY not set", file=sys.stderr); sys.exit(3)

BASE = "https://api.groq.com/openai/v1"
MODELS = {
    "groq_gpt_oss_20b": "openai/gpt-oss-20b",
    "groq_qwen_38_27b": "qwen/qwen3.8-27b",
}
CONTRASTS = [
    {"id": "D001", "name_a": "binary_search", "name_b": "find_index"},
    {"id": "D002", "name_a": "binary_search", "name_b": "min_heap"},
    {"id": "D003", "name_a": "find_index",    "name_b": "smallest_k"},
]
SPEC   = "Return the index of the first occurrence of x in sorted arr."
INPUTS = [[[1, 2, 2, 3], 2], [[], 1], [[1], 1]]
PACE   = 2.2

def prompt(name, inp):
    return (f"Write a single Python function named `{name}`.\n"
            f"Spec: {SPEC}\n"
            f"It will be called with inputs like: {inp}\n"
            f"Return only the function definition, no explanation.")

def normalize(code, name):
    return re.sub(rf"\b{re.escape(name)}\b", "F", code).strip()

async def call(session, model, p, retries=3):
    for attempt in range(retries):
        try:
            async with session.post(
                f"{BASE}/chat/completions",
                headers={"Authorization": f"Bearer {KEY}",
                         "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "user", "content": p}],
                      "max_tokens": 400, "temperature": 0},
                timeout=aiohttp.ClientTimeout(total=90),
            ) as r:
                body = await r.text()
                if r.status == 200:
                    return json.loads(body)["choices"][0]["message"]["content"]
                if r.status == 429:
                    await asyncio.sleep(5 * (attempt + 1)); continue
                raise RuntimeError(f"HTTP {r.status}: {body[:180]}")
        except asyncio.TimeoutError:
            if attempt == retries - 1: raise
            await asyncio.sleep(3)
    raise RuntimeError("retries exhausted")

async def preflight(session):
    async with session.get(f"{BASE}/models",
                           headers={"Authorization": f"Bearer {KEY}"},
                           timeout=aiohttp.ClientTimeout(total=15)) as r:
        if r.status != 200:
            print(f"PREFLIGHT FAILED: /models -> {r.status} {(await r.text())[:120]}",
                  file=sys.stderr)
            return False
        ids = {m["id"] for m in (await r.json()).get("data", [])}
    missing = [m for m in MODELS.values() if m not in ids]
    if missing:
        print(f"PREFLIGHT FAILED: models not in account: {missing}", file=sys.stderr)
        print(f"available (sample): {sorted(ids)[:20]}", file=sys.stderr)
        return False
    print("preflight OK: both models accessible")
    return True

async def contrast(session, mid, model, c):
    deltas = []
    for inp in INPUTS:
        try:
            ca = await call(session, model, prompt(c["name_a"], inp))
            await asyncio.sleep(PACE)
            cb = await call(session, model, prompt(c["name_b"], inp))
            await asyncio.sleep(PACE)
            deltas.append({
                "input": inp,
                "identical_after_rename": normalize(ca, c["name_a"]) == normalize(cb, c["name_b"]),
            })
        except Exception as e:
            deltas.append({"input": inp, "kind": "EXECUTION_FAILURE", "error": str(e)[:180]})
    exe = [d for d in deltas if d.get("kind") != "EXECUTION_FAILURE"]
    if not exe:
        return {"model": mid, "contrast": c["id"], "verdict": "NOT_EXECUTED", "deltas": deltas}
    diff = sum(1 for d in exe if not d["identical_after_rename"])
    return {"model": mid, "contrast": c["id"],
            "verdict": "GROUNDED" if diff >= 2 else "NAME_INVARIANT",
            "differing": diff, "n_executed": len(exe), "deltas": deltas}

async def main():
    async with aiohttp.ClientSession() as s:
        if not await preflight(s):
            sys.exit(4)
        rows = []
        for mid, model in MODELS.items():
            print(f"\n[{mid}]  {model}")
            for c in CONTRASTS:
                r = await contrast(s, mid, model, c)
                rows.append(r)
                if r["verdict"] == "NOT_EXECUTED":
                    err = (r["deltas"][0].get("error") or "")[:100]
                    print(f"  {c['id']}  NOT_EXECUTED   {err}")
                else:
                    print(f"  {c['id']}  {r['verdict']:<13}  "
                          f"{r['differing']}/{r['n_executed']} differ")
                OUT.write_text("\n".join(json.dumps(x, sort_keys=True, default=str)
                                         for x in rows) + "\n")
    by = defaultdict(lambda: defaultdict(int))
    for r in rows: by[r["model"]][r["verdict"]] += 1
    print(f"\n=== summary -> {OUT} ===")
    for m, s in by.items():
        print(f"  {m:<22}  grounded={s['GROUNDED']}/3  "
              f"invariant={s['NAME_INVARIANT']}/3  not_exec={s['NOT_EXECUTED']}/3")
    g = [m for m, s in by.items() if s["GROUNDED"] >= 2]
    if len(g) == 2:
        print("\n  VERDICT: CROSS-FAMILY — differential oracle grounds in both families")
    elif len(g) == 1:
        print(f"\n  VERDICT: FAMILY-SPECIFIC — only {g[0]} grounds")
    elif all(s["NOT_EXECUTED"] == 3 for s in by.values()):
        print("\n  VERDICT: NOT EXECUTED — infra failure, do not cite")
    else:
        print("\n  VERDICT: NEGATIVE — name-invariant, differential oracle falsified")

if __name__ == "__main__":
    asyncio.run(main())
