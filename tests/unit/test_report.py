from __future__ import annotations

import json

from agi.evaluation.benchmark import EvalResult, ItemOutcome
from agi.evaluation.dataset import DatasetItem
from agi.evaluation.report import to_json, to_markdown


def _result() -> EvalResult:
    items = (
        ItemOutcome(DatasetItem(id="a", goal="g", expect_tool="fs_list"),
                    run_status="succeeded", tool_used="fs_list",
                    duration_ms=12.5, run_id=1, passed=True),
        ItemOutcome(DatasetItem(id="b", goal="g", expect_tool="fs_list"),
                    run_status="failed", tool_used="fs_list",
                    duration_ms=20.0, run_id=2, passed=False,
                    detail="status mismatch"),
    )
    return EvalResult(benchmark="demo", provider="echo", model="echo-1",
                      total=2, passed=1, duration_ms=32.5,
                      items=items, eval_run_id=7)


def test_json_shape() -> None:
    payload = json.loads(to_json(_result()))
    assert payload["eval_run_id"] == 7
    assert payload["total"] == 2 and payload["passed"] == 1
    assert payload["items"][1]["passed"] is False


def test_markdown_contains_sections() -> None:
    md = to_markdown(_result())
    for needle in ("# Evaluation report: demo",
                   "## Summary", "## Items", "## Failures",
                   "status mismatch"):
        assert needle in md
