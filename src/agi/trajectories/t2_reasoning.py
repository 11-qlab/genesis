"""T2 — Self-consistency plan generation.

Wang et al. 2022 showed that sampling k reasoning chains at temperature > 0
and taking the majority vote over final answers improves accuracy over
greedy decoding, on arithmetic and common-sense benchmarks.

This module ports the idea to plan generation. Given a goal and a tool
catalog:

1. Sample k plans at temperature T > 0.
2. Validate each with `Plan.validate_graph`.
3. Cluster the valid plans by their structural signature
   (tuple of (tool, arg-names) per step).
4. Return the plan from the largest cluster, plus diagnostics.

The structural signature is not the same as "the answer" in a math
problem — two plans can be structurally identical but differ in argument
values. This means self-consistency here measures *structural agreement*
between independent samples, not answer agreement. That is the honest
scope of the port.

Measured against a benchmark, the relevant question is: does accuracy
with majority-vote over k=5 samples beat accuracy with k=1 greedy? The
answer is empirical and will vary by model and benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.errors import PlanValidationError
from ..providers.base import Provider
from ..reasoning.planner import Planner
from ..reasoning.schemas import Plan


@dataclass
class SelfConsistencyResult:
    plan: Plan
    samples: int
    valid_samples: int
    clusters: int
    majority_size: int
    agreement: float  # majority_size / valid_samples
    all_valid: list[Plan] = field(default_factory=list)


def _signature(plan: Plan) -> tuple[tuple[str | None, tuple[str, ...]], ...]:
    """Structural signature: per step, (tool, sorted arg names)."""
    return tuple(
        (step.tool, tuple(sorted(step.args.keys())))
        for step in plan.steps
    )


def self_consistent_plan(
    provider: Provider,
    goal: str,
    catalog: list[dict[str, Any]],
    *,
    k: int = 5,
    temperature: float = 0.7,
) -> SelfConsistencyResult:
    """Sample k plans, cluster by structural signature, return majority."""
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if k == 1:
        # Degenerate case: single sample, no consistency measurement
        plan = Planner(provider, catalog).plan(goal, temperature=0.0)
        return SelfConsistencyResult(
            plan=plan, samples=1, valid_samples=1, clusters=1,
            majority_size=1, agreement=1.0, all_valid=[plan],
        )

    valid: list[Plan] = []
    for _ in range(k):
        try:
            planner = Planner(provider, catalog)
            p = planner.plan(goal, temperature=temperature)
            valid.append(p)
        except PlanValidationError:
            continue

    if not valid:
        raise PlanValidationError(
            f"self-consistency: 0 of {k} samples produced a valid plan"
        )

    clusters: dict[tuple, list[Plan]] = {}
    for p in valid:
        clusters.setdefault(_signature(p), []).append(p)

    winner_sig = max(clusters, key=lambda sig: len(clusters[sig]))
    winner = clusters[winner_sig][0]

    return SelfConsistencyResult(
        plan=winner,
        samples=k,
        valid_samples=len(valid),
        clusters=len(clusters),
        majority_size=len(clusters[winner_sig]),
        agreement=len(clusters[winner_sig]) / len(valid),
        all_valid=valid,
    )
