"""Minimal LLM client: llama.cpp / OpenAI-compatible. Stdlib only."""
from __future__ import annotations
import json, os, urllib.request, urllib.error
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TokenScore:
    tokens: list[str]
    logprobs: list[float]

    def for_token(self, tok: str) -> Optional[float]:
        best: Optional[float] = None
        for t, lp in zip(self.tokens, self.logprobs):
            if t.strip() == tok.strip():
                if best is None or lp > best:
                    best = lp
        return best


class LLMClient:
    def complete(self, messages, **kw):
        raise NotImplementedError

    def complete_with_logprobs(self, messages, **kw):
        return self.complete(messages, **kw), None

    def score_continuation(self, prompt, continuation, **kw):
        return None

    def infer_tool_result(self, goal, prefix_steps, tc):
        raise NotImplementedError


class OpenAICompatClient(LLMClient):
    def __init__(self, base_url, model, api_key="sk-noop", timeout=120.0, temperature=0.0):
        _bu = base_url.rstrip("/")
        if _bu.endswith("/v1"):
            _bu = _bu[:-3]
        self.base_url = _bu
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature

    def _post(self, path, payload):
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e

    def complete(self, messages, **kw):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kw.get("temperature", self.temperature),
            "max_tokens": kw.get("max_tokens", 4096),
        }
        data = self._post("/v1/chat/completions", payload)
        msg = data["choices"][0].get("message", {}) or {}
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        if not content.strip() and reasoning.strip():
            return reasoning
        return content

    def complete_with_logprobs(self, messages, top_k=20, **kw):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kw.get("temperature", 0.0),
            "max_tokens": kw.get("max_tokens", 512),
            "logprobs": True,
            "top_logprobs": top_k,
        }
        try:
            data = self._post("/v1/chat/completions", payload)
        except RuntimeError:
            return self.complete(messages, **kw), None
        choice = data["choices"][0]
        msg = choice.get("message", {}) or {}
        text = msg.get("content") or ""
        if not text.strip():
            text = msg.get("reasoning_content") or msg.get("reasoning") or ""
        lp = choice.get("logprobs")
        if not lp or not lp.get("content"):
            return text, None
        toks = [t["token"] for t in lp["content"]]
        lps = [t["logprob"] for t in lp["content"]]
        return text, TokenScore(tokens=toks, logprobs=lps)

    def infer_tool_result(self, goal, prefix_steps, tc):
        sys = (
            "You are simulating a tool. Given the goal, prior context, and a "
            "pending tool call, produce the result you *believe* the tool would "
            "return. Be concise: one or two sentences."
        )
        prefix_txt = "\n".join(
            f"- {s.kind.value}: {s.content[:200]}" for s in prefix_steps[-6:]
        )
        user = f"GOAL: {goal}\n\nPRIOR:\n{prefix_txt}\n\nTOOL CALL: {tc.short()}\n\nRESULT:"
        return self.complete(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=0.7, max_tokens=80,
        )


def default_client() -> LLMClient:
    base = (
        os.environ.get("CFH_LLM_BASE")
        or os.environ.get("AGI_BASE_URL")
        or "http://127.0.0.1:8080"
    )
    model = os.environ.get("CFH_LLM_MODEL") or os.environ.get("AGI_MODEL") or "gpt-oss-20b"
    key = os.environ.get("CFH_LLM_KEY", "sk-noop")
    return OpenAICompatClient(base_url=base, model=model, api_key=key)


def extract_verdict(text: str) -> str | None:
    """Extract CORRECT or INCORRECT from a reply.

    Checks for the leading verdict word first (models usually lead with
    their answer). Falls back to searching anywhere in the reply.
    INCORRECT takes precedence: if "INCORRECT" appears anywhere, the
    verdict is INCORRECT unless the reply clearly opens with CORRECT.
    """
    if not text:
        return None
    t = text.strip().upper()
    # Leading token wins if it's the verdict
    first_word = t.split()[0] if t.split() else ""
    if first_word.startswith("INCORRECT"):
        return "INCORRECT"
    if first_word.startswith("CORRECT"):
        return "CORRECT"
    # Fallback: check INCORRECT before CORRECT (substring shadowing)
    import re
    if re.search(r"\bINCORRECT\b", t):
        return "INCORRECT"
    if re.search(r"\bCORRECT\b", t):
        return "CORRECT"
    return None
