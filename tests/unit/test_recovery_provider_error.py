"""Regression: recovery-plan ProviderError must not be swallowed.

Before this test existed, a 429 on the recovery-plan call was caught by
`_recovery_plan`'s broad `except Exception` and returned None. The run
continued, the retry failed on the same tool error, and the run was
recorded as a *tool failure* with no "429" in its detail. Contamination
detection could not see it. See DECISIONS D019.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agi.agents import Coordinator
from agi.core import load_config
from agi.core.errors import ProviderError
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry


class _RecoveryRateLimited:
    """First call: valid plan. Second call (recovery): raise 429."""
    name = "mixed"
    model = "m"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[Message], **_kw) -> Completion:
        self.calls += 1
        if self.calls == 1:
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
            "request failed after 3 attempt(s): "
            "client error 429: Rate limit reached on tokens per minute"
        )

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def test_recovery_plan_provider_error_propagates(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        coord = Coordinator(_RecoveryRateLimited(), tools, store, cfg.runtime)
        with pytest.raises(ProviderError) as exc_info:
            coord.execute("read the file")
        assert "429" in str(exc_info.value)
        runs = store.list_runs(5)
        assert runs, "run should be recorded"
        assert "429" in (runs[0]["summary"] or "")
    finally:
        store.close()
