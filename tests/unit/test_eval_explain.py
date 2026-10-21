from __future__ import annotations

from pathlib import Path

import pytest

from agi.evaluation.explain import explain_run, format_explain
from agi.storage import Store


def _seed(store: Store, provider: str) -> int:
    rid = store.create_eval_run("bench", provider, "m", 2)
    store.add_eval_item(rid, item_id="a", goal="g", status="succeeded",
                        passed=True, tool_used="fs_list", expect_tool="fs_list",
                        duration_ms=1.0, run_id=None)
    store.add_eval_item(rid, item_id="b", goal="g", status="succeeded",
                        passed=True, tool_used="fs_list", expect_tool="fs_list",
                        duration_ms=1.0, run_id=None)
    store.finish_eval_run(rid, status="completed", total=2, passed=2, duration_ms=2.0)
    return rid


def test_explain_echo(tmp_path: Path) -> None:
    s = Store(tmp_path / "e.sqlite3")
    try:
        rid = _seed(s, "echo")
        r = explain_run(s, rid)
        assert r["provider"] == "echo"
        assert any("fixture" in n.lower() for n in r["notes"])
        md = format_explain(r)
        assert "What this run proves" in md
        assert "What this run does NOT prove" in md
        assert "harness" in md.lower()
    finally:
        s.close()


def test_explain_real_provider(tmp_path: Path) -> None:
    s = Store(tmp_path / "e.sqlite3")
    try:
        rid = _seed(s, "openai_compat")
        r = explain_run(s, rid)
        assert not any("fixture" in n.lower() for n in r["notes"])
    finally:
        s.close()


def test_explain_missing(tmp_path: Path) -> None:
    s = Store(tmp_path / "e.sqlite3")
    try:
        with pytest.raises(ValueError):
            explain_run(s, 9999)
    finally:
        s.close()
