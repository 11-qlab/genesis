#!/usr/bin/env python3
"""76_multi_model_differential.py — differential name-contrast oracle across N models.

Models: Groq (8B + 70B), Colab tunnel (local), Gemini Flash.
Rule per (model, contrast):
  NOT_EXECUTED   all 3 inputs failed -> infra, NOT a falsification
  NAME_INVARIANT all executed inputs identical after rename -> model is not name-triggered
  GROUNDED       majority of executed inputs differ after rename -> model IS name-triggered

Cross-model result is the point: appears in 2+ models => general; 1 model => model-specific.
Both are publishable.
"""
import asyncio, json, os, re, sys
from collections import defaultdict
from pathlib import Path
import aiohttp

ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "state" / "multi_model_differential.jsonl"
OUT.parent.mkdir(exist_ok=True)

TUNNEL_BASE = os.environ.get("TUNNEL_BASE", "").rstrip("/")
TUNNEL_MODEL = os.environ.get("TUNNEL_MODEL", "llama3.2:3b")

MODELS = {
    "groq_oss20b": {
        "kind": "openai_compat",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY", "model": "openai/gpt-oss-20b",
        "rpm": 30,
    },
    "groq_qwen27b": {
        "kind": "openai_compat",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY", "model": "qwen/qwen3.8-27b",
        "rpm": 30,
    },
    "tunnel_local": {
        "kind": "openai_compat",
        "url": f"{TUNNEL_BASE}/chat/completions" if TUNNEL_BASE else "",
        "key_env": None, "model": TUNNEL_MODEL, "rpm": 1000,
    },
    "gemini_flash": {
        "kind": "gemini",
        "key_env": "GEMINI_API_KEY", "model": "gemini-2.5-flash", "rpm": 15,
    },
}

CONTRASTS = [
    {"id":"D001","name_a":"binary_search","name_b":"find_index"},
    {"id":"D002","name_a":"binary_search","name_b":"min_heap"},
    {"id":"D003","name_a":"find_index","name_b":"smallest_k"},
]
SPEC   = "Return the index of the first occurrence of x in sorted arr."
INPUTS = [[[1,2,2,3],2], [[],1], [[1],1]]

def prompt(name, inp):
    return (f"Write a single Python function named `{name}`.\n"
            f"Spec: {SPEC}\n"
            f"It will be called with inputs like: {inp}\n"
            f"Return only the function definition, no explanation.")

async def call_openai(session, cfg, p):
    key = os.environ.get(cfg["key_env"]) if cfg["key_env"] else None
    headers = {"Content-Type": "application/json"}
    if key: headers["Authorization"] = f"Bearer {key}"
    async with session.post(cfg["url"], headers=headers,
                            json={"model": cfg["model"],
                                  "messages":[{"role":"user","content":p}],
                                  "max_tokens": 400},
                            timeout=aiohttp.ClientTimeout(total=120)) as r:
        body = await r.text()
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}: {body[:200]}")
        return json.loads(body)["choices"][0]["message"]["content"]

async def call_gemini(session, cfg, p):
    key = os.environ.get(cfg["key_env"])
    if not key: raise RuntimeError(f"{cfg['key_env']} not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent?key={key}"
    async with session.post(url, headers={"Content-Type":"application/json"},
                            json={"contents":[{"parts":[{"text":p}]}]},
                            timeout=aiohttp.ClientTimeout(total=120)) as r:
        body = await r.text()
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}: {body[:200]}")
        return json.loads(body)["candidates"][0]["content"]["parts"][0]["text"]

async def call_model(session, cfg, p):
    if cfg["kind"] == "openai_compat": return await call_openai(session, cfg, p)
    if cfg["kind"] == "gemini":        return await call_gemini(session, cfg, p)
    raise ValueError(cfg["kind"])

def normalize(code, name):
    return re.sub(rf"\b{re.escape(name)}\b", "F", code).strip()

async def run_contrast(session, model_id, cfg, c):
    deltas = []
    # pace to stay under rpm
    pace = 60.0 / max(1, cfg.get("rpm", 30))
    for inp in INPUTS:
        try:
            code_a = await call_model(session, cfg, prompt(c["name_a"], inp))
            await asyncio.sleep(pace)
            code_b = await call_model(session, cfg, prompt(c["name_b"], inp))
            await asyncio.sleep(pace)
            n_a, n_b = normalize(code_a, c["name_a"]), normalize(code_b, c["name_b"])
            deltas.append({"input": inp, "identical_after_rename": n_a == n_b,
                           "len_a": len(code_a), "len_b": len(code_b)})
        except Exception as e:
            deltas.append({"input": inp, "kind":"EXECUTION_FAILURE",
                           "error": str(e)[:200]})
            await asyncio.sleep(pace)
    executed = [d for d in deltas if d.get("kind") != "EXECUTION_FAILURE"]
    failed   = [d for d in deltas if d.get("kind") == "EXECUTION_FAILURE"]
    if not executed:
        return {"model": model_id, "contrast": c["id"], "verdict": "NOT_EXECUTED",
                "n_failed": len(failed), "deltas": deltas}
    differing = sum(1 for d in executed if not d["identical_after_rename"])
    return {"model": model_id, "contrast": c["id"],
            "verdict": "GROUNDED" if differing >= 2 else "NAME_INVARIANT",
            "n_executed": len(executed), "n_failed": len(failed),
            "differing": differing, "deltas": deltas}

async def main():
    rows = []
    async with aiohttp.ClientSession() as s:
        for model_id, cfg in MODELS.items():
            if cfg["kind"] == "openai_compat" and not cfg["url"]:
                print(f"\n[{model_id}] skipped: TUNNEL_BASE unset"); continue
            if cfg["key_env"] and not os.environ.get(cfg["key_env"]):
                print(f"\n[{model_id}] skipped: {cfg['key_env']} unset"); continue
            print(f"\n[{model_id}]  ({cfg['model']})")
            for c in CONTRASTS:
                r = await run_contrast(s, model_id, cfg, c)
                rows.append(r)
                if r["verdict"] == "NOT_EXECUTED":
                    err = (r["deltas"][0].get("error") or "")[:140]
                    print(f"  {c['id']} {c['name_a']:<14} vs {c['name_b']:<14} "
                          f"-> NOT_EXECUTED  {err}")
                else:
                    print(f"  {c['id']} {c['name_a']:<14} vs {c['name_b']:<14} "
                          f"-> {r['verdict']:<13} ({r['differing']}/{r['n_executed']} differ)")
    OUT.write_text("\n".join(json.dumps(r, sort_keys=True, default=str) for r in rows) + "\n")
    by_model = defaultdict(lambda: defaultdict(int))
    for r in rows: by_model[r["model"]][r["verdict"]] += 1
    print(f"\n=== summary -> {OUT} ===")
    for m, s in by_model.items():
        print(f"  {m:<20} grounded={s['GROUNDED']}/3  "
              f"invariant={s['NAME_INVARIANT']}/3  not_executed={s['NOT_EXECUTED']}/3")
    # Cross-model: is the effect general or model-specific?
    models_g = [m for m, s in by_model.items() if s["GROUNDED"] >= 2]
    print(f"\n  models where effect generalizes (>=2/3 contrasts): {models_g or 'none'}")
    print(f"  => {'CROSS-MODEL' if len(models_g) >= 2 else 'MODEL-SPECIFIC' if models_g else 'NOT EXECUTED'}")

if __name__ == "__main__":
    asyncio.run(main())
