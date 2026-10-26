"""Single-agent pipeline with bounded reflection.

On the first failure of a plan step, the coordinator asks the planner for a
recovery sub-plan once, runs it, then retries the original step exactly once.
If the retry fails (or the recovery sub-plan itself cannot be produced), the
run is recorded as failed. There is no unbounded loop.
"""

from __future__ import annotations

import time
from typing import Any

from ..core.config import RuntimeConfig
from ..core.errors import (
    BudgetExceeded,
    PlanValidationError,
    ProviderError,
    ToolError,
)
from ..core.logging import get_logger
from ..providers.base import Provider
from ..reasoning.critique import PlanCritique
from ..reasoning.planner import Planner
from ..reasoning.repair import type_directed_repair
from ..reasoning.schemas import Plan, PlanStep
from ..reasoning.trace import Trace
from ..reasoning.typecheck import typecheck_plan
from ..storage.sqlite import Store
from ..tools.registry import ToolRegistry

log = get_logger("agi.coordinator")


class _Budget:
    __slots__ = ("calls",)

    def __init__(self) -> None:
        self.calls = 0

    def spend(self, limit: int) -> None:
        self.calls += 1
        if self.calls > limit:
            raise BudgetExceeded(
                f"tool-call budget exceeded ({self.calls} > {limit})"
            )


class Coordinator:
    def __init__(
        self,
        provider: Provider,
        tools: ToolRegistry,
        store: Store,
        runtime: RuntimeConfig,
        *,
        max_step_retries: int = 1,
        enable_critique: bool = False,
        enable_typed_plans: bool = False,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.store = store
        self.runtime = runtime
        self.max_step_retries = max(0, max_step_retries)
        self.enable_critique = enable_critique
        self.enable_typed_plans = enable_typed_plans
        self.trace: Trace | None = None

    # -- internal -------------------------------------------------------

    def _call_tool(self, budget: _Budget, tool: str, args: dict) -> tuple[bool, str, dict]:
        budget.spend(self.runtime.max_tool_calls)
        try:
            result = self.tools.execute(tool, args)
        except ToolError as exc:
            return False, str(exc), {}
        return result.ok, result.output, result.meta


    def _resolve_placeholders(self, content: str, prior_observations: list[str]) -> str:
        """Resolve {{read_inN_output}} references to prior observations."""
        import re
        def repl(m):
            try:
                n = int(m.group(1))
                if 0 <= n < len(prior_observations):
                    return prior_observations[n]
            except (ValueError, IndexError):
                pass
            return m.group(0)
        return re.sub(r"\{\{read_in(\d+)_output\}\}", repl, content)

    def _recovery_plan(self, planner: Planner, step: PlanStep, error: str) -> Plan | None:
        prompt = (
            f"Recovery for failed step '{step.title}' (tool={step.tool}). "
            f"Error: {error}. Produce a small plan whose steps, if run, would "
            "unblock a retry of that step."
        )
        try:
            return planner.plan(prompt)
        except PlanValidationError as exc:
            # The model produced an invalid recovery plan. Real
            # recovery failure, not a harness problem. Return None
            # so the caller falls through to the plain retry.
            log.info("recovery plan invalid: %s", exc)
            return None
        except ProviderError:
            # Rate limit, timeout, auth. Do NOT swallow: propagate so
            # the run is recorded with the 429 in its detail, which
            # contamination detection needs. See DECISIONS D019.
            raise
        except Exception as exc:  # pragma: no cover - defensive
            log.info("recovery plan unavailable: %s", exc)
            return None

    def _execute_step(
        self, run_id: int, planner: Planner, step: PlanStep, budget: _Budget
    ) -> dict[str, Any]:
        record: dict[str, Any] = {"id": step.id, "title": step.title}
        tools_invoked: list[str] = []
        if step.tool is None:
            record.update(ok=True, output="(no-op)", attempts=1,
                          tools_invoked=[])
            return record

        # Resolve {{read_inN_output}} / {{stepN.content}} before tool execution
        if step.tool and isinstance(step.args, dict) and "content" in step.args:
            # TEMP-DISABLED-FOR-PROMPT-FIX-TEST
            # step.args["content"] = self._resolve_placeholders(step.args["content"], results)
            pass
        ok, output, meta = self._call_tool(budget, step.tool, step.args)
        tools_invoked.append(step.tool)
        record.update(tool=step.tool, args=step.args, ok=ok, output=output, meta=meta,
                      attempts=1, tools_invoked=list(tools_invoked))
        if ok:
            return record

        if self.max_step_retries == 0:
            return record

        # Bounded reflection: one recovery attempt, one retry of the original.
        self.store.add_event(
            run_id, "step.retry",
            {"id": step.id, "tool": step.tool, "error": output},
        )
        recovery = self._recovery_plan(planner, step, output)
        if recovery is not None:
            for rs in recovery.topo_order():
                if not rs.tool:
                    continue
                r_ok, r_out, _ = self._call_tool(budget, rs.tool, rs.args)
                tools_invoked.append(rs.tool)
                self.store.add_event(
                    run_id, "step.recovery",
                    {"id": rs.id, "tool": rs.tool, "ok": r_ok, "output": r_out},
                )

        ok2, out2, meta2 = self._call_tool(budget, step.tool, step.args)
        tools_invoked.append(step.tool)
        record.update(
            ok=ok2, output=out2, meta=meta2,
            attempts=record["attempts"] + 1,
            tools_invoked=list(tools_invoked),
        )
        return record

    # -- public ---------------------------------------------------------

    def execute_with_plan(self, goal: str, plan: Plan) -> dict[str, Any]:
        """Execute a pre-computed plan. Skips the Planner.plan() step.

        Used by strategy=self-consistent so the majority-vote plan is
        actually executed, and by strategy=calibration so the plan the
        estimate was made on is what runs.
        """
        model = getattr(self.provider, "model", "unknown")
        run_id = self.store.create_run(goal, self.provider.name, model)
        started = time.monotonic()
        self.store.add_event(run_id, "run.started", {"goal": goal})
        log.info("run started", extra={"run_id": run_id})

        try:
            self.store.add_event(run_id, "plan.created", plan.model_dump())
            self.trace = Trace(run_id=run_id)
            self.trace.add("plan.created", goal=goal,
                           step_count=len(plan.steps),
                           tool_used=[s.tool for s in plan.steps])

            if self.enable_typed_plans:
                errs = typecheck_plan(plan)
                if errs:
                    raise PlanValidationError(
                        "plan failed type checking: "
                        + "; ".join(e.message for e in errs)
                    )

            catalog = self.tools.describe()
            planner = Planner(self.provider, catalog)
            budget = _Budget()
            results: list[dict[str, Any]] = []
            failed_step: str | None = None

            for step in plan.topo_order():
                if time.monotonic() - started > self.runtime.max_wall_clock_s:
                    raise BudgetExceeded("wall-clock budget exceeded")
                record = self._execute_step(run_id, planner, step, budget)
                if self.trace is not None:
                    self.trace.add("step.executed",
                                   step_id=record["id"],
                                   tool=record.get("tool"),
                                   ok=record.get("ok"),
                                   attempts=record.get("attempts", 1))
                results.append(record)
                if not record["ok"]:
                    failed_step = record["id"]
                    self.store.add_event(run_id, "step.failed", record)
                    break
                self.store.add_event(run_id, "step.completed", record)

            status = "failed" if failed_step else "succeeded"
            summary = f"{len(results)} step(s) executed"
            self.store.finish_run(run_id, status, summary)
            self.store.add_event(
                run_id,
                "run.completed" if status == "succeeded" else "run.failed",
                {"summary": summary, "failed_step": failed_step},
            )
            return {"run_id": run_id, "status": status,
                    "plan": plan.model_dump(), "results": results}
        except Exception as exc:
            self.store.add_event(run_id, "run.failed", {"error": str(exc)})
            self.store.finish_run(run_id, "failed", str(exc))
            log.warning("run %s failed: %s", run_id, exc)
            raise

    def execute(self, goal: str) -> dict[str, Any]:
        model = getattr(self.provider, "model", "unknown")
        run_id = self.store.create_run(goal, self.provider.name, model)
        started = time.monotonic()
        self.store.add_event(run_id, "run.started", {"goal": goal})
        log.info("run started", extra={"run_id": run_id})

        try:
            catalog = self.tools.describe()
            planner = Planner(self.provider, catalog)
            plan = planner.plan(goal)
            self.store.add_event(run_id, "plan.created", plan.model_dump())

            self.trace = Trace(run_id=run_id)

            if self.enable_typed_plans:
                errs = typecheck_plan(plan)
                self.trace.add(
                    "plan.typecheck",
                    ok=(not errs),
                    error_count=len(errs),
                    errors=[e.as_dict() for e in errs],
                )
                if errs:
                    repaired = type_directed_repair(
                        self.provider, goal, plan, catalog=catalog,
                    )
                    if repaired is None:
                        self.store.add_event(
                            run_id, "plan.typecheck.failed",
                            {"errors": [e.as_dict() for e in errs]},
                        )
                        raise PlanValidationError(
                            "plan failed type checking after repair attempts: "
                            + "; ".join(e.message for e in errs)
                        )
                    plan = repaired
                    self.store.add_event(
                        run_id, "plan.repaired", plan.model_dump(),
                    )
                    self.trace.add(
                        "plan.repaired",
                        step_count=len(plan.steps),
                        tool_used=[s.tool for s in plan.steps],
                    )

            self.trace.add(
                "plan.created",
                goal=goal,
                step_count=len(plan.steps),
                tool_used=[s.tool for s in plan.steps],
            )

            if self.enable_critique:
                try:
                    critique = PlanCritique(self.provider).review(goal, plan, catalog)
                except Exception as exc:
                    critique = {"verdict": "unavailable", "reason": str(exc)}
                self.store.add_event(run_id, "plan.critique", critique)
                self.trace.add("plan.critique", **critique)

            budget = _Budget()
            results: list[dict[str, Any]] = []
            failed_step: str | None = None

            for step in plan.topo_order():
                if time.monotonic() - started > self.runtime.max_wall_clock_s:
                    raise BudgetExceeded("wall-clock budget exceeded")
                record = self._execute_step(run_id, planner, step, budget)
                if self.trace is not None:
                    self.trace.add(
                        "step.executed",
                        step_id=record["id"],
                        tool=record.get("tool"),
                        ok=record.get("ok"),
                        attempts=record.get("attempts", 1),
                    )
                results.append(record)
                if not record["ok"]:
                    failed_step = record["id"]
                    self.store.add_event(run_id, "step.failed", record)
                    break
                self.store.add_event(run_id, "step.completed", record)

            status = "failed" if failed_step else "succeeded"
            summary = f"{len(results)} step(s) executed"
            self.store.finish_run(run_id, status, summary)
            self.store.add_event(
                run_id,
                "run.completed" if status == "succeeded" else "run.failed",
                {"summary": summary, "failed_step": failed_step},
            )
            return {
                "run_id": run_id,
                "status": status,
                "plan": plan.model_dump(),
                "results": results,
            }
        except Exception as exc:
            self.store.add_event(run_id, "run.failed", {"error": str(exc)})
            self.store.finish_run(run_id, "failed", str(exc))
            # One line, not a stack trace: the caller (CLI, eval runner) records
            # the failure and the eval report names the item.
            log.warning("run %s failed: %s", run_id, exc)
            raise
