"""Probe a provider to learn what it can and cannot do.

Never prints credentials. Reads the key from `api_key_env` if set. Every
capability probe is timeout-bounded and independently reported so a partial
failure on one probe does not block the others.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any

from ..core.config import ProviderConfig
from .base import Message
from .echo import EchoProvider
from .openai_compat import _USER_AGENT, OpenAICompatProvider


@dataclass
class ProbeReport:
    provider: str
    kind: str
    base_url: str
    model: str
    credential_present: bool
    credential_env_name: str
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    overall_ok: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _first_key(env_name: str) -> str | None:
    """Return the first key from AGI_API_KEYS pool, else env_name."""
    import os as _os
    multi = _os.environ.get("AGI_API_KEYS", "").strip()
    if multi:
        for raw in multi.split(","):
            k = raw.strip().strip("'\"").strip()
            if k:
                return k
    return _os.environ.get(env_name)


def _summarize_exception(exc: Exception) -> str:
    msg = str(exc)
    if len(msg) > 300:
        msg = msg[:300] + "..."
    return f"{type(exc).__name__}: {msg}"


_HTTP_HINTS: dict[int, str] = {
    401: "invalid or missing api key; check the value of the env var named "
         "in credential_env_name and ensure no trailing whitespace",
    402: "account has insufficient balance on this provider; top up or use a "
         "different endpoint",
    403: "key lacks access to this model on this account",
    404: "wrong base url; usually missing /v1 or pointing at the wrong host",
    429: "rate limited; wait and retry, or use a different endpoint",
}


def _hint_for(status: int | None) -> str | None:
    if status is None:
        return None
    return _HTTP_HINTS.get(status)


def _probe_models(cfg: ProviderConfig, timeout_s: float = 5.0) -> dict[str, Any]:
    url = f"{cfg.base_url.rstrip('/')}/models"
    headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    key = _first_key(cfg.api_key_env)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
            try:
                payload = json.loads(body)
                seen = [m.get("id") for m in payload.get("data", []) if isinstance(m, dict)]
            except json.JSONDecodeError:
                seen = []
            return {
                "ok": True,
                "status": resp.status,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
                "models_seen": seen[:20],
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": exc.code < 400,
            "status": exc.code,
            "reason": str(exc.reason),
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": _summarize_exception(exc),
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }


def _probe_complete(cfg: ProviderConfig) -> dict[str, Any]:
    provider = OpenAICompatProvider(
        name=cfg.name, base_url=cfg.base_url, model=cfg.model,
        api_key_env=cfg.api_key_env, timeout_s=min(cfg.timeout_s, 30.0),
        max_retries=0,
    )
    started = time.monotonic()
    try:
        completion = provider.complete(
            [Message(role="user", content="Reply with the single word: ok")],
            max_tokens=64, temperature=0.0,
        )
        return {
            "ok": True,
            "text_preview": completion.text[:80],
            "model_reported": completion.model,
            "usage": {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
            },
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as exc:
        msg = str(exc)
        status: int | None = None
        for token in msg.split():
            if token.isdigit() and 100 <= int(token) <= 599:
                status = int(token)
                break
        hint = _hint_for(status)
        payload: dict[str, Any] = {
            "ok": False,
            "error": _summarize_exception(exc),
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }
        if hint:
            payload["hint"] = hint
        return payload


def _probe_stream(cfg: ProviderConfig) -> dict[str, Any]:
    provider = OpenAICompatProvider(
        name=cfg.name, base_url=cfg.base_url, model=cfg.model,
        api_key_env=cfg.api_key_env, timeout_s=min(cfg.timeout_s, 30.0),
        max_retries=0,
    )
    started = time.monotonic()
    chunks: list[str] = []
    try:
        for i, chunk in enumerate(provider.stream(
            [Message(role="user", content="Count: one, two, three")],
            max_tokens=32, temperature=0.0,
        )):
            chunks.append(chunk)
            if i >= 20:  # cap; we only need to see that streaming works
                break
        return {
            "ok": bool(chunks),
            "chunks": len(chunks),
            "preview": "".join(chunks)[:120],
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as exc:
        msg = str(exc)
        status: int | None = None
        for token in msg.split():
            if token.isdigit() and 100 <= int(token) <= 599:
                status = int(token)
                break
        hint = _hint_for(status)
        payload: dict[str, Any] = {
            "ok": False,
            "error": _summarize_exception(exc),
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }
        if hint:
            payload["hint"] = hint
        return payload


def _probe_embeddings(cfg: ProviderConfig) -> dict[str, Any]:
    if cfg.kind == "echo":
        return {"ok": False, "error": "echo has no embeddings endpoint"}
    url = f"{cfg.base_url.rstrip('/')}/embeddings"
    key = _first_key(cfg.api_key_env)
    headers = {"Content-Type": "application/json", "User-Agent": _USER_AGENT}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = json.dumps({"model": cfg.model, "input": ["hello"]}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=min(cfg.timeout_s, 20.0)) as resp:
            payload = json.loads(resp.read())
            data = payload.get("data") or []
            dim = len(data[0]["embedding"]) if data and "embedding" in data[0] else 0
            return {
                "ok": bool(dim),
                "dim": dim,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "reason": str(exc.reason),
            "note": "some chat models do not expose /embeddings; the memory "
                    "feature falls back to HashEmbedding in that case",
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": _summarize_exception(exc),
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }


def probe(cfg: ProviderConfig) -> ProbeReport:
    import os

    _pool = os.environ.get("AGI_API_KEYS", "").strip()
    credential_present = bool(_pool) or bool(os.environ.get(cfg.api_key_env))
    report = ProbeReport(
        provider=cfg.name, kind=cfg.kind,
        base_url=cfg.base_url, model=cfg.model,
        credential_present=credential_present,
        credential_env_name=cfg.api_key_env,
    )
    if cfg.kind == "echo":
        ep = EchoProvider()
        report.checks["health"] = ep.health()
        report.checks["complete"] = {
            "ok": True,
            "text_preview": ep.complete([Message("user", "ok")]).text[:80],
        }
        report.overall_ok = True
        return report

    report.checks["models"] = _probe_models(cfg)
    report.checks["complete"] = _probe_complete(cfg)
    report.checks["stream"] = _probe_stream(cfg)
    report.checks["embeddings"] = _probe_embeddings(cfg)
    report.overall_ok = report.checks["complete"].get("ok", False)
    return report
