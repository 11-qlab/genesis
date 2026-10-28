#!/usr/bin/env python3
"""70_async_router.py — async multi-provider router with persisted token bucket.

Does not call any LLM by itself. Exposes async def call(provider_pref=None)
that any caller (autonomous_research, generate_candidate, etc.) can await.
On 429, rotates to next provider. On exhaustion of all providers, falls back
to local (vLLM/Ollama at $LOCAL_LLM_URL if set, else raises LocalUnavailable).
"""
import asyncio, json, os, time
from collections import deque
from pathlib import Path
ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state" / "router_state.json"; STATE.parent.mkdir(exist_ok=True)

PROVIDERS = {
    "groq":     {"env":"GROQ_API_KEY",     "rpm": 30,   "url":"https://api.groq.com/openai/v1/chat/completions"},
    "together": {"env":"TOGETHER_API_KEY", "rpm": 60,   "url":"https://api.together.xyz/v1/chat/completions"},
    "cerebras": {"env":"CEREBRAS_API_KEY", "rpm": 30,   "url":"https://api.cerebras.ai/v1/chat/completions"},
    "deepseek": {"env":"DEEPSEEK_API_KEY", "rpm": 60,   "url":"https://api.deepseek.com/v1/chat/completions"},
}
LOCAL_URL = os.environ.get("LOCAL_LLM_URL")  # e.g. http://localhost:8000/v1/chat/completions
WINDOW = 60.0   # seconds

class Bucket:
    def __init__(self, rpm):
        self.rpm = rpm; self.calls = deque()
    def _prune(self):
        now = time.time()
        while self.calls and now - self.calls[0] > WINDOW:
            self.calls.popleft()
    def ready(self, env_var=None):
        import os as _os
        if env_var and not _os.environ.get(env_var): return False
        self._prune(); return len(self.calls) < self.rpm
    def take(self):
        self._prune(); self.calls.append(time.time())
    def dump(self):
        self._prune(); return list(self.calls)
    def load(self, calls):
        self.calls = deque(x for x in calls if time.time() - x <= WINDOW)

buckets = {name: Bucket(spec["rpm"]) for name, spec in PROVIDERS.items()}
if STATE.exists():
    try:
        data = json.loads(STATE.read_text())
        for name, calls in data.items():
            if name in buckets: buckets[name].load(calls)
    except Exception:
        pass

def persist():
    STATE.write_text(json.dumps({n: b.dump() for n, b in buckets.items()}))

async def _post(url, headers, payload, timeout=60):
    import aiohttp
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=headers, json=payload, timeout=timeout) as r:
            text = await r.text()
            return r.status, text

async def call(prompt, model, provider_pref=None, max_tokens=1024):
    order = ([provider_pref] if provider_pref else []) + [p for p in PROVIDERS if p != provider_pref]
    last_err = None
    for name in order:
        spec = PROVIDERS[name]
        key = os.environ.get(spec["env"])
        if not key: continue
        if not buckets[name].ready():
            await asyncio.sleep(1.0); continue
        buckets[name].take(); persist()
        try:
            status, text = await _post(
                spec["url"],
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                {"model": model, "messages": [{"role":"user","content":prompt}],
                 "max_tokens": max_tokens},
            )
        except Exception as e:
            last_err = f"{name}: {e!r}"; continue
        if status == 200:
            return json.loads(text)["choices"][0]["message"]["content"]
        if status == 429:
            last_err = f"{name}: 429 rate limit"; await asyncio.sleep(2.0); continue
        last_err = f"{name}: HTTP {status}: {text[:200]}"
    if LOCAL_URL:
        try:
            status, text = await _post(
                LOCAL_URL, {"Content-Type": "application/json"},
                {"model": model, "messages": [{"role":"user","content":prompt}],
                 "max_tokens": max_tokens},
            )
            if status == 200:
                return json.loads(text)["choices"][0]["message"]["content"]
            last_err = f"local: HTTP {status}: {text[:200]}"
        except Exception as e:
            last_err = f"local: {e!r}"
    raise RuntimeError(f"all providers failed; last error: {last_err}")

if __name__ == "__main__":
    import sys
    if "--status" in sys.argv:
        import os as _os
        for n, b in buckets.items():
            key = _os.environ.get(PROVIDERS[n]["env"])
            print(f"{n:<10} {len(b.calls)}/{b.rpm:<3} key={'set' if key else 'MISSING':<8} ready={b.ready(PROVIDERS[n]['env'])}")
        raise SystemExit(0)
    async def demo():
        out = await call("Say PONG and nothing else.", "llama-3.1-8b-instant")
        print("got:", out[:120])
    asyncio.run(demo())
