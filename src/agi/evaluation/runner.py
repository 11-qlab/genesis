"""Evaluation runner: executes a benchmark against a Coordinator."""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..agents.coordinator import Coordinator
from ..core.config import AppConfig
from ..core.errors import AGIError
from ..providers.base import Provider
from ..storage.sqlite import Store
from ..tools.registry import ToolRegistry
from .benchmark import (
    Benchmark,
    EvalResult,
    ItemOutcome,
    first_tool_from_result,
    tool_sequence_from_result,
)
from .contamination import classify


def _first_failed_step(result: dict) -> dict | None:
    """Return the first step in `result['results']` that has ok=False."""
    for step in result.get("results") or []:
        if step.get("ok") is False:
            return step
    return None




@dataclass
class EvalRunner:
    provider: Provider
    tools: ToolRegistry
    store: Store
    runtime: AppConfig  # we only use runtime for coordinator's budget
    delay_ms: int = 0  # pace inter-item calls to stay under provider rate limits
    enable_typed_plans: bool = False
    strategy: str = "greedy"
    revision_signal: str = "basic"
    self_consistency_k: int = 5
    calibration_bins: int = 5

    def run(self, bench: Benchmark) -> EvalResult:
        model = getattr(self.provider, "model", "unknown")
        eval_run_id = self.store.create_eval_run(
            bench.name, self.provider.name, model, len(bench.dataset)
        )
        started = time.monotonic()
        outcomes: list[ItemOutcome] = []

        for idx, item in enumerate(bench.dataset):
            if idx > 0 and self.delay_ms > 0:
                time.sleep(self.delay_ms / 1000.0)
            t0 = time.monotonic()
            run_status = "error"
            tool_used: str | None = None
            tool_sequence: tuple[str, ...] = ()
            run_id: int | None = None
            detail = ""

            if bench.before_each is not None:
                try:
                    bench.before_each(item)
                except Exception as exc:
                    duration_ms = (time.monotonic() - t0) * 1000.0
                    self.store.add_eval_item(
                        eval_run_id,
                        item_id=item.id, goal=item.goal,
                        status="seed_error", passed=False,
                        tool_used=None, expect_tool=item.expect_tool,
                        duration_ms=duration_ms, run_id=None,
                        detail=f"before_each failed: {type(exc).__name__}: {exc}",
                    )
                    outcomes.append(ItemOutcome(
                        item=item, run_status="seed_error", tool_used=None,
                        duration_ms=duration_ms, run_id=None, passed=False,
                        detail=f"before_each failed: {exc}",
                    ))
                    continue

            agreement_this_item = None
            calibration_this_item = None
            coordinator = Coordinator(
                self.provider, self.tools, self.store, self.runtime.runtime,
                enable_typed_plans=self.enable_typed_plans,
            )
            try:
                if self.strategy == "self-consistent":
                    from ..trajectories import self_consistent_plan
                    scr = self_consistent_plan(
                        self.provider, item.goal,
                        self.tools.describe(),
                        k=self.self_consistency_k, temperature=0.7,
                    )
                    agreement_this_item = scr.agreement
                    result = coordinator.execute_with_plan(item.goal, scr.plan)
                elif self.strategy == "calibration":
                    from ..reasoning.planner import Planner
                    from ..trajectories import CalibrationProbe
                    catalog = self.tools.describe()
                    plan = Planner(self.provider, catalog).plan(
                        item.goal, temperature=0.0,
                    )
                    try:
                        calibration_this_item = CalibrationProbe(
                            self.provider
                        ).estimate(item.goal, plan, catalog)
                    except Exception:
                        calibration_this_item = None
                    result = coordinator.execute_with_plan(item.goal, plan)
                elif self.strategy == "revision":
                    from ..trajectories import RevisionAgent
                    agent = RevisionAgent(
                        self.provider, self.tools, self.store,
                        self.runtime.runtime,
                        max_revisions=2,
                        signal=self.revision_signal,
                    )
                    rr = agent.execute(item.goal)
                    # Take the final result of the revision chain
                    result = rr.final_result or {}
                    # Record revisions attempted for the summary
                    if rr.revisions_attempted:
                        self.store.add_event(
                            result.get("run_id", 0),
                            "revision.attempted",
                            {"count": rr.revisions_attempted,
                             "run_ids": rr.run_ids},
                        )
                else:
                    result = coordinator.execute(item.goal)
                run_id = result.get("run_id")
                run_status = result.get("status", "unknown")
                tool_used = first_tool_from_result(result)
                tool_sequence = tool_sequence_from_result(result)
            except AGIError as exc:
                run_status = "error"
                detail = str(exc)
            except Exception as exc:  # pragma: no cover - defensive
                run_status = "error"
                detail = f"{type(exc).__name__}: {exc}"

            passed, reason = bench.checker(item, run_status, tool_used, tool_sequence)
            duration_ms = (time.monotonic() - t0) * 1000.0

            # Capture the failing step's tool + output for the report.
            failed_step = _first_failed_step(result) if 'result' in locals() else None
            if failed_step:
                tool_name = failed_step.get("tool") or "?"
                tool_out = (failed_step.get("output") or "")[:200]
                prefix = f"step {failed_step.get('id')} ({tool_name}) failed: {tool_out}"
                detail = prefix if not detail else f"{detail} | {prefix}"

            if not passed and reason and reason not in detail:
                detail = (detail + " | " if detail else "") + reason

            self.store.add_eval_item(
                eval_run_id,
                item_id=item.id,
                goal=item.goal,
                status=run_status,
                passed=passed,
                tool_used=tool_used,
                expect_tool=item.expect_tool,
                duration_ms=duration_ms,
                run_id=run_id,
                detail=detail,
            )
            outcomes.append(ItemOutcome(
                item=item,
                run_status=run_status,
                tool_used=tool_used,
                duration_ms=duration_ms,
                run_id=run_id,
                passed=passed,
                detail=detail,
                tool_sequence=tool_sequence,
                agreement=agreement_this_item,
                calibration_estimate=calibration_this_item,
            ))

        total_ms = (time.monotonic() - started) * 1000.0
        passed = sum(1 for o in outcomes if o.passed)
        rate_limited, contaminated = classify([o.detail for o in outcomes])
        total = len(outcomes)

        status = "contaminated" if contaminated else "completed"

        self.store.finish_eval_run(
            eval_run_id,
            status=status,
            total=total,
            passed=passed,
            duration_ms=total_ms,
            contaminated=contaminated,
        )
        # --- strategy-specific aggregates ---
        mean_agreement = None
        brier = None
        ece = None

        if self.strategy == "self-consistent":
            ags = [o.agreement for o in outcomes if o.agreement is not None]
            if ags:
                mean_agreement = sum(ags) / len(ags)

        if self.strategy == "calibration":
            try:
                from ..trajectories import (
                    CalibrationSample,
                    brier_score,
                    expected_calibration_error,
                )
                samples = [
                    CalibrationSample(
                        goal=o.item.goal,
                        estimate=o.calibration_estimate,
                        actual_success=o.passed,
                    )
                    for o in outcomes
                    if o.calibration_estimate is not None
                ]
                if samples:
                    brier = brier_score(samples)
                    ece = expected_calibration_error(
                        samples, bins=self.calibration_bins,
                    )
            except Exception:
                pass

        return EvalResult(
            benchmark=bench.name,
            provider=self.provider.name,
            model=model,
            total=total,
            passed=passed,
            duration_ms=total_ms,
            items=tuple(outcomes),
            eval_run_id=eval_run_id,
            contaminated=contaminated,
            rate_limited_items=rate_limited,
            strategy=self.strategy,
            mean_agreement=mean_agreement,
            brier=brier,
            ece=ece,
        )
