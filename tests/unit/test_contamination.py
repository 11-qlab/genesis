"""Tests for the contamination detection protocol.

A run is contaminated if >10% of items failed with rate-limit or billing
errors. Contaminated runs exit non-zero and must not be averaged.
"""
from __future__ import annotations

import json
from pathlib import Path

from agi.core import load_config
from agi.evaluation import Benchmark
from agi.evaluation.contamination import is_rate_limited as _is_rate_limited
from agi.evaluation.dataset import Dataset, DatasetItem
from agi.evaluation.runner import EvalRunner
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry


class _RateLimited:
    """Returns 429 on every call — simulates tier exhaustion."""
    name = "429"
    model = "m"

    def __init__(self) -> None:
        self._n = 0

    def complete(self, messages: list[Message], **_kw) -> Completion:
        self._n += 1
        raise __import__("agi").core.errors.ProviderError(
            'request failed after 3 attempt(s): client error 429: '
            '{"error":{"message":"Rate limit reached on tokens per minute ..."}}'
        )

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": False}


class _Healthy:
    name = "ok"
    model = "m"

    def complete(self, messages: list[Message], **_kw) -> Completion:
        return Completion(
            text=json.dumps({
                "goal": "g", "steps": [{
                    "id": "s1", "title": "t", "tool": "fs_list",
                    "args": {"path": "."}, "depends_on": [],
                }],
            }),
            model=self.model,
        )

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def _bench(items: int) -> Benchmark:
    return Benchmark(
        name="t",
        dataset=Dataset(
            name="t", path=Path("/tmp/x"),
            items=tuple(
                DatasetItem(id=f"i{n}", goal="g", expect_tool="fs_list")
                for n in range(items)
            ),
        ),
    )


def test_is_rate_limited_markers():
    assert _is_rate_limited("client error 429: rate limit reached")
    assert _is_rate_limited("429: Rate Limit")
    assert _is_rate_limited('client error 402: Insufficient Balance')
    assert _is_rate_limited("QUOTA EXCEEDED on tokens")
    assert not _is_rate_limited("")
    assert not _is_rate_limited("not a file: x.txt")
    assert not _is_rate_limited("step s1 (fs_read) failed: path escapes sandbox")


def test_all_rate_limited_marks_contaminated(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        runner = EvalRunner(_RateLimited(), tools, store, cfg)
        result = runner.run(_bench(5))
        assert result.contaminated is True
        assert result.rate_limited_items == 5
        saved = store.get_eval_run(result.eval_run_id)
        assert saved["status"] == "contaminated"
        assert saved["contaminated"] == 1
    finally:
        store.close()


def test_healthy_not_contaminated(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        runner = EvalRunner(_Healthy(), tools, store, cfg)
        result = runner.run(_bench(3))
        assert result.contaminated is False
        assert result.rate_limited_items == 0
        saved = store.get_eval_run(result.eval_run_id)
        assert saved["status"] == "completed"
        assert saved["contaminated"] == 0
    finally:
        store.close()


def test_under_10_percent_not_contaminated(tmp_path: Path) -> None:
    """1 in 20 = 5%, below the 10% threshold. Not contaminated."""
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        bench = _bench(20)
        # Force one item to be rate-limited by having the provider fail
        # every fifth call.
        class _Sometimes:
            name = "sometimes"
            model = "m"

            def __init__(self) -> None:
                self._n = 0

            def complete(self, messages: list[Message], **_kw) -> Completion:
                self._n += 1
                if self._n == 1:
                    raise __import__("agi").core.errors.ProviderError(
                        "429: rate limit"
                    )
                return Completion(
                    text=json.dumps({
                        "goal": "g", "steps": [{
                            "id": "s1", "title": "t", "tool": "fs_list",
                            "args": {"path": "."}, "depends_on": [],
                        }],
                    }),
                    model=self.model,
                )

            def stream(self, messages: list[Message], **_kw):
                yield self.complete(messages).text

            def health(self) -> dict:
                return {"ok": True}

        runner = EvalRunner(_Sometimes(), tools, store, cfg)
        result = runner.run(bench)
        assert result.rate_limited_items == 1
        # 1/20 = 5% < 10%
        assert result.contaminated is False
    finally:
        store.close()
