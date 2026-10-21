"""Single-agent execution pipeline: plan, validate, execute, record."""

from __future__ import annotations

import time
from typing import Any

from ..core.config import RuntimeConfig
from ..core.errors import BudgetExceeded, ToolError
from ..core.logging import get_logger
from ..providers.base import Provider
from ..reasoning.planner import Planner
from ..storage.sqlite import Store
from ..tools.registry import ToolRegistry

log = get_logger("agi.agent")


class SimpleAgent:
    def __init__(
        self,
        provider: Provider,
        tools: ToolRegistry,
        store: Store,
        runtime: RuntimeConfig,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.store = store
        self.runtime = runtime

    def execute(self, goal: str) -> dict[str, Any]:
        model = getattr(self.provider, "model", "unknown")
        run_id = self.store.create_run(goal, self.provider.name, model)
        started = time.monotonic()
        self.store.add_event(run_id, "run.started", {"goal": goal})
        log.info("run started", extra={"run_id": run_id})

        try:
            planner = Planner(self.provider, self.tools.describe())
            plan = planner.plan(goal)
            self.store.add_event(run_id, "plan.created", plan.model_dump())

            results: list[dict[str, Any]] = []
            tool_calls = 0
            for step in plan.topo_order():
                if time.monotonic() - started > self.runtime.max_wall_clock_s:
                    raise BudgetExceeded("wall-clock budget exceeded")

                record: dict[str, Any] = {"id": step.id, "title": step.title}
                if step.tool:
                    tool_calls += 1
                    if tool_calls > self.runtime.max_tool_calls:
                        raise BudgetExceeded("tool-call budget exceeded")
                    try:
                        result = self.tools.execute(step.tool, step.args)
                    except ToolError as exc:
                        record.update(tool=step.tool, ok=False, output=str(exc))
                        self.store.add_event(run_id, "step.failed", record)
                        raise
                    record.update(
                        tool=step.tool,
                        ok=result.ok,
                        output=result.output,
                        meta=result.meta,
                    )
                else:
                    record.update(ok=True, output="(no-op)")

                results.append(record)
                if not record["ok"]:
                    self.store.add_event(run_id, "step.failed", record)
                    raise ToolError(
                        f"step {record['id']} (tool={record.get('tool')}) "
                        f"failed: {record.get('output', '(no detail)')[:200]}"
                    )
                self.store.add_event(run_id, "step.completed", record)

            summary = f"{len(results)} step(s) executed"
            self.store.finish_run(run_id, "succeeded", summary)
            self.store.add_event(run_id, "run.completed", {"summary": summary})
            return {
                "run_id": run_id,
                "status": "succeeded",
                "plan": plan.model_dump(),
                "results": results,
            }
        except Exception as exc:
            self.store.add_event(run_id, "run.failed", {"error": str(exc)})
            self.store.finish_run(run_id, "failed", str(exc))
            log.exception("run failed", extra={"run_id": run_id})
            raise
