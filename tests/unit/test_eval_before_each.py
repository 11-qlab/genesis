from __future__ import annotations

import json
from pathlib import Path

from agi.core import load_config
from agi.evaluation import Benchmark, EvalRunner
from agi.evaluation.dataset import Dataset, DatasetItem
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry


class _FixedProvider:
    name = "fixed"
    model = "fixed-1"

    def __init__(self, plan: dict) -> None:
        self._plan = json.dumps(plan)

    def complete(self, messages: list[Message], **_kw) -> Completion:
        return Completion(text=self._plan, model=self.model)

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def test_before_each_called_once_per_item(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")

    calls: list[str] = []
    def before(item: DatasetItem) -> None:
        calls.append(item.id)

    items = (
        DatasetItem(id="a", goal="list", expect_tool="fs_list"),
        DatasetItem(id="b", goal="list", expect_tool="fs_list"),
    )
    bench = Benchmark(
        name="demo", dataset=Dataset(name="demo", path=tmp_path / "x", items=items),
        before_each=before,
    )
    provider = _FixedProvider({
        "goal": "g",
        "steps": [{"id": "s1", "title": "t", "tool": "fs_list",
                   "args": {"path": "."}, "depends_on": []}],
    })
    try:
        result = EvalRunner(provider=provider, tools=tools, store=store, runtime=cfg).run(bench)
        assert calls == ["a", "b"]
        assert result.passed == result.total == 2
    finally:
        store.close()


def test_before_each_failure_recorded_as_seed_error(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")

    def before(_item: DatasetItem) -> None:
        raise RuntimeError("seed broke")

    items = (DatasetItem(id="a", goal="list", expect_tool="fs_list"),)
    bench = Benchmark(
        name="demo", dataset=Dataset(name="demo", path=tmp_path / "x", items=items),
        before_each=before,
    )
    provider = _FixedProvider({
        "goal": "g",
        "steps": [{"id": "s1", "title": "t", "tool": "fs_list",
                   "args": {"path": "."}, "depends_on": []}],
    })
    try:
        result = EvalRunner(provider=provider, tools=tools, store=store, runtime=cfg).run(bench)
        assert result.passed == 0
        assert result.items[0].run_status == "seed_error"
    finally:
        store.close()
