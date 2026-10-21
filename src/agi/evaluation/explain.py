"""Produce an honest interpretation of an eval_run.

The output separates:
- WHAT THIS PROVES  — properties of the harness (scheduling, storage, reporting).
- WHAT THIS DOES NOT PROVE — properties of the model (reasoning, planning quality).

The two must never be conflated. A 1.0 against a fixture provider is a
statement about the runner, not about intelligence.
"""

from __future__ import annotations

from typing import Any

from ..storage.sqlite import Store


def explain_run(store: Store, eval_run_id: int) -> dict[str, Any]:
    run = store.get_eval_run(eval_run_id)
    if run is None:
        raise ValueError(f"no such eval run: {eval_run_id}")
    items = store.list_eval_items(eval_run_id)

    tools = sorted({i["tool_used"] for i in items if i["tool_used"]})
    tools_by_item = {
        i["item_id"]: (i["tool_used"], i["expect_tool"], bool(i["passed"]))
        for i in items
    }

    provider_is_fixture = run["provider"] == "echo"

    proves = [
        "The eval runner iterated every item in the dataset.",
        "The Coordinator scheduled and executed each step's tool.",
        "Per-item rows were persisted in eval_items.",
        "Aggregate metrics (accuracy, passed, total) were computed.",
        f"Tool surface actually used: {tools or '(none)'}",
    ]
    does_not_prove = [
        "That the model planned well. Echo is a regex fixture; it returns the "
        "plan the benchmark needs." if provider_is_fixture else
        "That the model planned well. That requires reasoning that is the "
        "model's, not the harness's.",
        "That the system retrieved the right document. HashEmbedding is a "
        "bag-of-words sketch; semantic matching needs an embedding model.",
        "That the accuracy number is comparable across benchmarks. Two "
        "benchmarks with different item ids measure different things; "
        "compare only same-benchmark runs.",
        "That the agent improved at anything. Two runs of the same benchmark "
        "measured against the same provider is the only honest regression signal.",
    ]

    # Flag fixture-planted state
    seeds = [i for i in items if i["status"] == "seed_error"]
    notes: list[str] = []
    if seeds:
        notes.append(
            f"{len(seeds)} item(s) failed during seeding; those are harness "
            "failures, not model failures."
        )
    if provider_is_fixture:
        notes.append(
            "Provider was `echo` (deterministic fixture). Any number above "
            "measures the harness, not a model. To measure reasoning, point "
            "AGI_PROVIDER_KIND=openai_compat at a real endpoint and rerun."
        )

    return {
        "eval_run_id": eval_run_id,
        "benchmark": run["benchmark"],
        "provider": run["provider"],
        "model": run["model"],
        "accuracy": run["accuracy"],
        "passed": run["passed"],
        "total": run["total"],
        "tools_by_item": tools_by_item,
        "proves": proves,
        "does_not_prove": does_not_prove,
        "notes": notes,
    }


def format_explain(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Eval explain: run {result['eval_run_id']}")
    lines.append("")
    lines.append(f"- benchmark: `{result['benchmark']}`")
    lines.append(f"- provider: `{result['provider']}`  model: `{result['model']}`")
    lines.append(f"- accuracy: {result['accuracy']:.4f} "
                 f"({result['passed']}/{result['total']})")
    lines.append("")
    lines.append("## What this run proves")
    lines.append("")
    for line in result["proves"]:
        lines.append(f"- {line}")
    lines.append("")
    lines.append("## What this run does NOT prove")
    lines.append("")
    for line in result["does_not_prove"]:
        lines.append(f"- {line}")
    if result["notes"]:
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        for note in result["notes"]:
            lines.append(f"- {note}")
    lines.append("")
    lines.append("## Per-item tool calls")
    lines.append("")
    lines.append("| item | tool_used | expect_tool | passed |")
    lines.append("| --- | --- | --- | --- |")
    for item_id, (used, expect, passed) in result["tools_by_item"].items():
        lines.append(
            f"| {item_id} | {used or '-'} | {expect or '-'} | "
            f"{'yes' if passed else 'no'} |"
        )
    return "\n".join(lines) + "\n"
