"""Loopback HTTP API for the AGI platform (stdlib only)."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from ..agents.coordinator import Coordinator
from ..core.config import AppConfig
from ..core.errors import AGIError
from ..providers.router import ProviderRouter
from ..reasoning.planner import Planner
from ..storage.sqlite import Store
from ..tools.registry import ToolRegistry


@dataclass
class ServerHandle:
    server: ThreadingHTTPServer
    thread: threading.Thread
    host: str
    port: int

    def url(self, path: str = "/") -> str:
        return f"http://{self.host}:{self.port}{path}"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        raise ValueError("empty request body")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("body must be a JSON object")
    return payload


def _require_goal(payload: dict[str, Any]) -> str:
    goal = payload.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("'goal' must be a non-empty string")
    return goal.strip()


def _make_handler(
    cfg: AppConfig,
    router: ProviderRouter,
    tools: ToolRegistry,
    store: Store,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "agi/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:  # silence stderr noise
            return

        def _send(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _err(self, code: int, message: str) -> None:
            self._send(code, {"ok": False, "error": message})

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/health":
                providers = router.health()
                self._send(200, {
                    "ok": True,
                    "providers": providers,
                    "tools": tools.names(),
                })
                return
            if path == "/v1/runs":
                self._send(200, {"ok": True, "runs": store.list_runs(50)})
                return
            if path.startswith("/v1/runs/"):
                suffix = path[len("/v1/runs/"):]
                try:
                    run_id = int(suffix)
                except ValueError:
                    self._err(400, "run id must be an integer")
                    return
                run = store.get_run(run_id)
                if run is None:
                    self._err(404, f"no such run: {run_id}")
                    return
                self._send(200, {
                    "ok": True,
                    "run": run,
                    "events": store.list_events(run_id),
                })
                return
            self._err(404, f"unknown path: {path}")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                payload = _read_json(self)
            except ValueError as exc:
                self._err(400, str(exc))
                return

            if path == "/v1/plan":
                try:
                    goal = _require_goal(payload)
                except ValueError as exc:
                    self._err(400, str(exc))
                    return
                try:
                    planner = Planner(router.get(), tools.names())
                    plan = planner.plan(goal)
                except AGIError as exc:
                    self._err(422, f"plan failed: {exc}")
                    return
                self._send(200, {"ok": True, "plan": plan.model_dump()})
                return

            if path == "/v1/run":
                try:
                    goal = _require_goal(payload)
                except ValueError as exc:
                    self._err(400, str(exc))
                    return
                try:
                    coordinator = Coordinator(router.get(), tools, store, cfg.runtime)
                    result = coordinator.execute(goal)
                except AGIError as exc:
                    self._err(422, f"run failed: {exc}")
                    return
                self._send(200, {"ok": True, **result})
                return

            self._err(404, f"unknown path: {path}")

    return Handler


def build_server(
    cfg: AppConfig,
    router: ProviderRouter,
    tools: ToolRegistry,
    store: Store,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ServerHandle:
    handler_cls = _make_handler(cfg, router, tools, store)
    httpd = ThreadingHTTPServer((host, port), handler_cls)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return ServerHandle(
        server=httpd, thread=thread,
        host=httpd.server_address[0], port=httpd.server_address[1],
    )


def serve(
    cfg: AppConfig,
    router: ProviderRouter,
    tools: ToolRegistry,
    store: Store,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    handle = build_server(cfg, router, tools, store, host=host, port=port)
    try:
        handle.thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        handle.stop()
