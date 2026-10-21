from __future__ import annotations

from agi.reasoning.trace import Trace


def test_trace_add_and_summary() -> None:
    t = Trace(run_id=1)
    t.add("plan.created", step_count=2)
    t.add("step.executed", step_id="s1", ok=True)
    t.add("step.executed", step_id="s2", ok=False)
    summary = t.summary()
    assert summary["run_id"] == 1
    assert summary["total_events"] == 3
    assert summary["by_kind"]["step.executed"] == 2
    assert len(t.filter("step.executed")) == 2
    assert len(t.as_dicts()) == 3
