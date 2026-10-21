"""Integration: a run whose recovery-plan call hits 429 must be marked
contaminated, not recorded as a clean tool failure.
"""
from __future__ import annotations

import json
from pathlib import Path

from agi.core import load_config
from agi.core.errors import ProviderError
from agi.evaluation import Benchmark
from agi.evaluation.dataset import Dataset, DatasetItem
from agi.evaluation.runner import EvalRunner
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry


class _RecoveryRateLimited:
    """Plan for each item succeeds; recovery-plan call for each item 429s."""
    name = "mixed"
    model = "m"

    def __init__(self) -> None:
        self.call_count = 0

    def complete(self, messages: list[Message], **_kw) -> Completion:
        self.call_count += 1
        if self.call_count % 2 == 1:
            return Completion(
                text=json.dumps({
                    "goal": "g", "steps": [{
                        "id": "s1", "title": "read missing",
                        "tool": "fs_read",
                        "args": {"path": "nope.txt"},
                        "depends_on": [],
                    }],
                }),
                model=self.model,
            )
        raise ProviderError(
            "request failed after 3 attempt(s): client error 429: rate limited"
        )

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def _bench(n: int) -> Benchmark:
    items = tuple(
        DatasetItem(id=f"i{k}", goal="read the file", expect_tool="fs_read")
        for k in range(n)
    )
    return Benchmark(
        name="t",
        dataset=Dataset(name="t", path=Path("/tmp/x"), items=items),
    )


def test_recovery_429_marks_contaminated(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        runner = EvalRunner(
            provider=_RecoveryRateLimited(),
            tools=tools,
            store=store,
            runtime=cfg,
        )
        result = runner.run(_bench(3))
        assert result.passed == 0
        assert result.total == 3
        for o in result.items:
            assert "429" in o.detail, f"item {o.item.id} detail: {o.detail!r}"
        assert result.rate_limited_items == 3
        assert result.contaminated is True
    finally:
        store.close()
