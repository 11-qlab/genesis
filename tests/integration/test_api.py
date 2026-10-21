from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from agi.api import build_server
from agi.core import load_config
from agi.providers import EchoProvider
from agi.providers.router import ProviderRouter
from agi.storage import Store
from agi.tools import build_registry


@pytest.fixture()
def api(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    provider = EchoProvider()
    router = ProviderRouter(default=provider)
    tools = build_registry(["fs_list", "fs_read", "fs_write"], str(ws))
    store = Store(tmp_path / "api.sqlite3")
    handle = build_server(cfg, router, tools, store, host="127.0.0.1", port=0)
    yield handle
    handle.stop()
    store.close()


def _get(url: str) -> tuple[int, dict]:
    try:
        with urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def _post(url: str, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    req = Request(url, data=body, method="POST",
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def test_health(api) -> None:
    code, payload = _get(api.url("/health"))
    assert code == 200
    assert payload["ok"] is True
    assert payload["providers"][0]["provider"] == "echo"


def test_plan(api) -> None:
    code, payload = _post(api.url("/v1/plan"), {"goal": "list workspace"})
    assert code == 200, payload
    assert payload["ok"] is True
    assert payload["plan"]["steps"][0]["tool"] == "fs_list"


def test_run_and_runs(api) -> None:
    code, payload = _post(api.url("/v1/run"), {"goal": "list workspace"})
    assert code == 200, payload
    assert payload["ok"] is True
    assert payload["status"] == "succeeded"
    run_id = payload["run_id"]

    code, listing = _get(api.url("/v1/runs"))
    assert code == 200
    assert any(r["id"] == run_id for r in listing["runs"])

    code, detail = _get(api.url(f"/v1/runs/{run_id}"))
    assert code == 200
    kinds = [e["kind"] for e in detail["events"]]
    assert "run.started" in kinds and "run.completed" in kinds


def test_missing_goal_400(api) -> None:
    code, payload = _post(api.url("/v1/plan"), {})
    assert code == 400
    assert payload["ok"] is False


def test_unknown_path_404(api) -> None:
    code, payload = _get(api.url("/nope"))
    assert code == 404
    assert payload["ok"] is False


def test_runs_bad_id_400(api) -> None:
    code, _ = _get(api.url("/v1/runs/abc"))
    assert code == 400


def test_runs_missing_404(api) -> None:
    code, _ = _get(api.url("/v1/runs/9999"))
    assert code == 404
