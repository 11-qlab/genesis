from __future__ import annotations

from agi.evaluation.benchmark import EvalResult, ItemOutcome
from agi.evaluation.dataset import DatasetItem
from agi.evaluation.metrics import compute_metrics, summarize_by_status


def _outcome(i: str, passed: bool, tool: str | None, ms: float, status: str = "succeeded") -> ItemOutcome:
    return ItemOutcome(
        item=DatasetItem(id=i, goal="g", expect_tool=tool),
        run_status=status, tool_used=tool,
        duration_ms=ms, run_id=None, passed=passed,
    )


def test_perfect() -> None:
    items = (_outcome("a", True, "fs_list", 10.0),
             _outcome("b", True, "fs_list", 20.0))
    r = EvalResult(benchmark="x", provider="echo", model="m",
                   total=2, passed=2, duration_ms=30.0, items=items)
    m = compute_metrics(r)
    assert m.accuracy == 1.0
    assert m.mean_duration_ms == 15.0
    assert m.unique_tools == ("fs_list",)


def test_half() -> None:
    items = (_outcome("a", True, "fs_list", 10.0),
             _outcome("b", False, None, 20.0, status="error"))
    r = EvalResult(benchmark="x", provider="p", model="m",
                   total=2, passed=1, duration_ms=30.0, items=items)
    m = compute_metrics(r)
    assert m.accuracy == 0.5
    assert m.failed == 1
    assert m.unique_tools == ("fs_list",)
    statuses = summarize_by_status(r.items)
    assert statuses == {"succeeded": 1, "error": 1}


def test_p95_single() -> None:
    items = (_outcome("a", True, "fs_list", 42.0),)
    r = EvalResult(benchmark="x", provider="p", model="m",
                   total=1, passed=1, duration_ms=42.0, items=items)
    m = compute_metrics(r)
    assert m.p50_duration_ms == 42.0
    assert m.p95_duration_ms == 42.0
