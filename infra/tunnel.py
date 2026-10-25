"""Cloudflare quick-tunnel supervisor. Detects URL, keeps pid/logs."""
from __future__ import annotations
import os, re, signal, subprocess, time
from pathlib import Path

from .env import save_env
from .health import check_health

LOG = Path.home() / ".agi" / "tunnel.log"
PID = Path.home() / ".agi" / "tunnel.pid"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


class TunnelSupervisor:
    def __init__(self, upstream: str = "http://127.0.0.1:8080"):
        self.upstream = upstream
        LOG.parent.mkdir(parents=True, exist_ok=True)

    def is_running(self) -> bool:
        if not PID.exists():
            return False
        try:
            pid = int(PID.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            return False

    def stop(self) -> None:
        if not self.is_running():
            PID.unlink(missing_ok=True)
            return
        pid = int(PID.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        PID.unlink(missing_ok=True)
        time.sleep(1)

    def start(self, wait_url: float = 30.0) -> str:
        # Pre-flight: upstream must respond
        if not self._upstream_ok():
            raise SystemExit(
                f"FATAL: upstream {self.upstream} not responding. "
                "Start llama.cpp / Colab cell first."
            )
        self.stop()
        LOG.write_text("")
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", self.upstream, "--no-autoupdate"],
            stdout=LOG.open("a"), stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        PID.write_text(str(proc.pid))
        url = self._wait_url(wait_url)
        if not url:
            raise SystemExit(f"FATAL: no URL in {LOG} after {wait_url}s. tail:{LOG}")
        base = f"{url}/v1"
        os.environ["AGI_BASE_URL"] = base
        save_env({"AGI_BASE_URL": base})
        return base

    def _wait_url(self, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                m = URL_RE.search(LOG.read_text())
                if m:
                    url = m.group(0)
                    # Edge propagation
                    for _ in range(10):
                        os.environ["AGI_BASE_URL"] = f"{url}/v1"
                        if check_health(timeout=5).get("ok"):
                            return url
                        time.sleep(2)
                    return url  # URL exists even if slow — caller verifies
            except FileNotFoundError:
                pass
            time.sleep(1)
        return None

    def _upstream_ok(self) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen(f"{self.upstream}/v1/models", timeout=3) as r:
                return r.status < 400
        except Exception:
            return False


def set_remote_url(url: str) -> str:
    """Store a URL provided externally (e.g. from a Colab cloudflared cell).

    Normalizes to .../v1 and persists to ~/.agi/env. Verifies health and
    raises SystemExit with a clear message if the URL doesn't respond.
    """
    if not url:
        raise SystemExit("FATAL: empty URL")
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url = url + "/v1"
    os.environ["AGI_BASE_URL"] = url
    save_env({"AGI_BASE_URL": url})

    from .health import check_health
    h = check_health(timeout=15)
    if not h.get("ok"):
        raise SystemExit(
            f"FATAL: URL saved but health check failed.\n"
            f"  URL: {url}\n"
            f"  err: {h.get('error')}\n"
            "  → the Colab cell may still be starting cloudflared; retry in 10s.\n"
            "  → or the tunnel is dead; regenerate it in Colab and pass the new URL."
        )
    return url
