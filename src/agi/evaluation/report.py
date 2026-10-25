"""Markdown and JSON report renderers for an EvalResult."""

from __future__ import annotations

import json

from .benchmark import EvalResult
from .metrics import compute_metrics, summarize_by_status


def to_json(result: EvalResult) -> str:
    payload = {
        "eval_run_id": result.eval_run_id,
        "benchmark": result.benchmark,
        "provider": result.provider,
        "model": result.model,
        "total": result.total,
        "passed": result.passed,
        "accuracy": result.accuracy,
        "contaminated": result.contaminated,
        "rate_limited_items": result.rate_limited_items,
        "strategy": result.strategy,
        "mean_agreement": result.mean_agreement,
        "brier": result.brier,
        "ece": result.ece,
        "duration_ms": result.duration_ms,
        "items": [
            {
                "id": o.item.id,
                "goal": o.item.goal,
                "status": o.run_status,
                "tool_used": o.tool_used,
                "expect_tool": o.item.expect_tool,
                "expect_status": o.item.expect_status,
                "passed": o.passed,
                "duration_ms": round(o.duration_ms, 3),
                "run_id": o.run_id,
                "detail": o.detail,
                "tool_sequence": list(o.tool_sequence),
                "steps": getattr(o, "steps", None),
                "agreement": o.agreement,
                "calibration_estimate": o.calibration_estimate,
            }
            for o in result.items
        ],
    }
    return json.dumps(payload, indent=2, default=str)


def to_markdown(result: EvalResult) -> str:
    m = compute_metrics(result)
    by_status = summarize_by_status(result.items)
    status_line = ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))

    lines: list[str] = []
    lines.append(f"# Evaluation report: {result.benchmark}")
    lines.append("")
    if result.contaminated:
        lines.append(
            f"> **CONTAMINATED**: {result.rate_limited_items}/{result.total} "
            "items failed with rate-limit or billing errors. Discard this run."
        )
        lines.append("")
    lines.append(f"- Provider: `{result.provider}`")
    lines.append(f"- Model: `{result.model}`")
    if result.eval_run_id is not None:
        lines.append(f"- eval_run_id: `{result.eval_run_id}`")
    lines.append("")
    if result.strategy != "greedy":
        lines.append(f"- strategy: `{result.strategy}`")
        if result.mean_agreement is not None:
            lines.append(
                f"- mean_agreement: {result.mean_agreement:.4f} "
                "(fraction of k samples in the majority cluster)"
            )
        if result.brier is not None:
            lines.append(
                f"- brier: {result.brier:.4f} (0=perfect, 0.25=random)"
            )
        if result.ece is not None:
            lines.append(
                f"- ece: {result.ece:.4f} (0=perfect, ~0.25=random, "
                ">0.15=poorly calibrated)"
            )
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("| --- | --- |")
    lines.append(f"| total | {m.total} |")
    lines.append(f"| passed | {m.passed} |")
    lines.append(f"| failed | {m.failed} |")
    lines.append(f"| accuracy | {m.accuracy:.4f} |")
    lines.append(f"| mean_duration_ms | {m.mean_duration_ms:.2f} |")
    lines.append(f"| p50_duration_ms | {m.p50_duration_ms:.2f} |")
    lines.append(f"| p95_duration_ms | {m.p95_duration_ms:.2f} |")
    lines.append(f"| unique_tools | {', '.join(m.unique_tools) or '(none)'} |")
    lines.append(f"| status_counts | {status_line or '(none)'} |")
    lines.append("")
    lines.append("## Items")
    lines.append("")
    lines.append("| id | status | pass | tool | expect_tool | duration_ms |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for o in result.items:
        lines.append(
            f"| {o.item.id} | {o.run_status} | "
            f"{'yes' if o.passed else 'no'} | "
            f"{o.tool_used or '-'} | "
            f"{o.item.expect_tool or '-'} | "
            f"{o.duration_ms:.2f} |"
        )
    failures = [o for o in result.items if not o.passed]
    if failures:
        lines.append("")
        lines.append("## Failures")
        lines.append("")
        for o in failures:
            lines.append(f"- `{o.item.id}`: {o.detail or '(no detail)'}")
    return "\n".join(lines) + "\n"
