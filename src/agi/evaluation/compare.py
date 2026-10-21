"""Compare two stored evaluation runs.

Pure read: this module never writes to the store and never executes a
benchmark. It is intended for regression triage after `agi eval run` twice.
"""

from __future__ import annotations

import json
from typing import Any

from ..storage.sqlite import Store


class CompareError(ValueError):
    """One or both eval runs are missing, or the ids are equal."""


def compare_runs(store: Store, a_id: int, b_id: int) -> dict[str, Any]:
    if a_id == b_id:
        raise CompareError("A and B must be different eval_run ids")

    run_a = store.get_eval_run(a_id)
    run_b = store.get_eval_run(b_id)
    if run_a is None:
        raise CompareError(f"no such eval run: {a_id}")
    if run_b is None:
        raise CompareError(f"no such eval run: {b_id}")

    items_a = {row["item_id"]: row for row in store.list_eval_items(a_id)}
    items_b = {row["item_id"]: row for row in store.list_eval_items(b_id)}

    only_a = sorted(set(items_a) - set(items_b))
    only_b = sorted(set(items_b) - set(items_a))
    both = sorted(set(items_a) & set(items_b))

    regressions: list[str] = []
    improvements: list[str] = []
    stable_pass = 0
    stable_fail = 0
    tool_changes: list[dict[str, Any]] = []

    for item_id in both:
        ra, rb = items_a[item_id], items_b[item_id]
        pa = bool(ra["passed"])
        pb = bool(rb["passed"])
        if pa and not pb:
            regressions.append(item_id)
        elif pb and not pa:
            improvements.append(item_id)
        elif pa and pb:
            stable_pass += 1
        else:
            stable_fail += 1
        if ra["tool_used"] != rb["tool_used"]:
            tool_changes.append({
                "item_id": item_id,
                "tool_a": ra["tool_used"],
                "tool_b": rb["tool_used"],
            })

    acc_a = float(run_a["accuracy"])
    acc_b = float(run_b["accuracy"])
    return {
        "a": {
            "eval_run_id": a_id,
            "benchmark": run_a["benchmark"],
            "provider": run_a["provider"],
            "model": run_a["model"],
            "accuracy": acc_a,
            "total": run_a["total"],
            "passed": run_a["passed"],
        },
        "b": {
            "eval_run_id": b_id,
            "benchmark": run_b["benchmark"],
            "provider": run_b["provider"],
            "model": run_b["model"],
            "accuracy": acc_b,
            "total": run_b["total"],
            "passed": run_b["passed"],
        },
        "delta_accuracy": acc_b - acc_a,
        "delta_passed": int(run_b["passed"]) - int(run_a["passed"]),
        "shared_items": len(both),
        "stable_pass": stable_pass,
        "stable_fail": stable_fail,
        "regressions": regressions,
        "improvements": improvements,
        "only_in_a": only_a,
        "only_in_b": only_b,
        "tool_changes": tool_changes,
    }


def format_compare_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2)


def format_compare_markdown(result: dict[str, Any]) -> str:
    a, b = result["a"], result["b"]
    lines: list[str] = []
    lines.append(f"# Eval compare: `{a['eval_run_id']}` → `{b['eval_run_id']}`")
    lines.append("")
    lines.append("| | A | B | delta |")
    lines.append("| --- | --- | --- | --- |")
    lines.append(
        f"| accuracy | {a['accuracy']:.4f} | {b['accuracy']:.4f} "
        f"| {result['delta_accuracy']:+.4f} |"
    )
    lines.append(
        f"| passed | {a['passed']} | {b['passed']} "
        f"| {result['delta_passed']:+d} |"
    )
    lines.append(
        f"| total | {a['total']} | {b['total']} | - |"
    )
    lines.append("")
    lines.append(f"- shared items: {result['shared_items']}")
    lines.append(f"- stable pass: {result['stable_pass']}")
    lines.append(f"- stable fail: {result['stable_fail']}")
    lines.append(f"- regressions: {len(result['regressions'])}"
                 + (f" ({', '.join(result['regressions'])})" if result['regressions'] else ""))
    lines.append(f"- improvements: {len(result['improvements'])}"
                 + (f" ({', '.join(result['improvements'])})" if result['improvements'] else ""))
    if result["only_in_a"]:
        lines.append(f"- only in A: {', '.join(result['only_in_a'])}")
    if result["only_in_b"]:
        lines.append(f"- only in B: {', '.join(result['only_in_b'])}")
    if result["tool_changes"]:
        lines.append("")
        lines.append("## Tool changes")
        lines.append("")
        lines.append("| item | tool A | tool B |")
        lines.append("| --- | --- | --- |")
        for change in result["tool_changes"]:
            lines.append(
                f"| {change['item_id']} | {change['tool_a'] or '-'} | {change['tool_b'] or '-'} |"
            )
    return "\n".join(lines) + "\n"
