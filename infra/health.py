"""Endpoint health checks. Every run starts with require_healthy()."""
from __future__ import annotations
import json, os, time, urllib.error, urllib.request
from pathlib import Path

HEALTH_FILE = Path.home() / ".agi" / "health.json"


def check_health(timeout: float = 10.0) -> dict:
    base = os.environ.get("AGI_BASE_URL", "").rstrip("/")
    if not base:
        return {"ok": False, "error": "AGI_BASE_URL unset"}
    url = f"{base}/models"
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agi-infra/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(2000).decode("utf-8", "replace")
        data = json.loads(body)
        models = data.get("models") or data.get("data") or []
        model_ids = [m.get("id") or m.get("name") for m in models if isinstance(m, dict)]
        result = {
            "ok": True,
            "base_url": base,
            "latency_ms": (time.monotonic() - t0) * 1000,
            "model_count": len(model_ids),
            "models": model_ids[:10],
            "checked_at": time.time(),
        }
    except urllib.error.HTTPError as e:
        result = {"ok": False, "error": f"HTTP {e.code}", "body": e.read(500).decode("utf-8", "replace")}
    except Exception as e:
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(json.dumps(result, indent=2))
    return result


def require_healthy(timeout: float = 10.0, max_tries: int = 3, wait_s: float = 5.0) -> dict:
    """Raise SystemExit if endpoint is not healthy after retries."""
    last = None
    for i in range(max_tries):
        last = check_health(timeout=timeout)
        if last.get("ok"):
            return last
        if i < max_tries - 1:
            time.sleep(wait_s * (i + 1))
    raise SystemExit(
        f"FATAL: endpoint unhealthy after {max_tries} tries.\n"
        f"  {json.dumps(last, indent=2)}\n"
        "  → restart tunnel:  scripts/infra_up\n"
        "  → or check status: scripts/infra_health"
    )
