"""Aggregate metrics for an EvalResult."""

from __future__ import annotations

from dataclasses import dataclass

from .benchmark import EvalResult, ItemOutcome


@dataclass(frozen=True)
class EvalMetrics:
    total: int
    passed: int
    failed: int
    accuracy: float
    mean_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    unique_tools: tuple[str, ...]


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def compute_metrics(result: EvalResult) -> EvalMetrics:
    durations = sorted(outcome.duration_ms for outcome in result.items)
    total = result.total
    passed = result.passed
    failed = total - passed
    unique_tools = tuple(sorted({
        outcome.tool_used for outcome in result.items if outcome.tool_used
    }))
    return EvalMetrics(
        total=total,
        passed=passed,
        failed=failed,
        accuracy=result.accuracy,
        mean_duration_ms=(sum(durations) / total) if total else 0.0,
        p50_duration_ms=_percentile(durations, 0.50),
        p95_duration_ms=_percentile(durations, 0.95),
        unique_tools=unique_tools,
    )


def summarize_by_status(items: tuple[ItemOutcome, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for outcome in items:
        counts[outcome.run_status] = counts.get(outcome.run_status, 0) + 1
    return counts
