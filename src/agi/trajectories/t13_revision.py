"""T13 - Plan revision with bounded retries.

Two signal modes:

- "basic" (default): the revision prompt gives the model the failing step,
  its error, and a summary of the plan. Tested in the previous batch:
  delta=0 on task_chain. The model produced the same wrong plan twice.
- "rich": the revision prompt walks through every step with its outcome,
  classifies the error (tool-not-found, template-syntax, invalid-args,
  type-error), and adds targeted suggestions. Tested here on error_recovery,
  where the initial plan commonly fails on missing-file errors and the
  "create the file first" suggestion is directly actionable.

Not a claim about AGI. Model, tools, and harness unchanged. It is: when
the current plan fails, try a different plan, with two different signals
for what "different" means.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..agents.coordinator import Coordinator
from ..core.config import RuntimeConfig
from ..core.errors import ProviderError
from ..core.logging import get_logger
from ..providers.base import Provider
from ..reasoning.planner import Planner
from ..reasoning.schemas import Plan
from ..storage.sqlite import Store
from ..tools.registry import ToolRegistry

log = get_logger("agi.trajectories.t13")

_VALID_SIGNALS = ("basic", "rich")


@dataclass
class RevisionResult:
    goal: str
    status: str
    revisions_attempted: int
    run_ids: list[int] = field(default_factory=list)
    final_result: dict[str, Any] | None = None
    all_results: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_runs(self) -> int:
        return len(self.run_ids)


class RevisionAgent:
    def __init__(
        self,
        provider: Provider,
        tools: ToolRegistry,
        store: Store,
        runtime: RuntimeConfig,
        *,
        max_revisions: int = 1,
        signal: str = "basic",
    ) -> None:
        if signal not in _VALID_SIGNALS:
            raise ValueError(
                f"signal must be one of {_VALID_SIGNALS}, got {signal!r}"
            )
        self.provider = provider
        self.tools = tools
        self.store = store
        self.runtime = runtime
        self.max_revisions = max(0, max_revisions)
        self.signal = signal

    def _extract_failure(
        self, result: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        for step in result.get("results") or []:
            if step.get("ok") is False:
                return step, (step.get("output") or "(no detail)")
        return None, "(no failed step found)"

    def _classify_error(self, error: str) -> str:
        low = error.lower()
        if "{{" in error or "<%" in error:
            return "template-syntax"
        if "not a file" in low or "not found" in low:
            return "tool-not-found"
        if "invalid arguments" in low or "validation" in low:
            return "tool-invalid-args"
        if "type" in low and ("mismatch" in low or "expected" in low):
            return "type-error"
        if "429" in error or "rate limit" in low:
            return "rate-limit"
        return "other"

    def _suggestions_for(self, err_class: str) -> list[str]:
        if err_class == "tool-not-found":
            return [
                "The referenced file/directory/resource does not exist. "
                "Consider creating it first with fs_write, or listing its "
                "parent directory with fs_list before reading it.",
            ]
        if err_class == "template-syntax":
            return [
                "Data flow MUST use $step_id.field references "
                "($s1.out, $s2.ok). Do NOT use {{...}} or <%...%>.",
            ]
        if err_class == "tool-invalid-args":
            return [
                "Argument validation failed. Check required vs optional args "
                "and types against the tool catalog.",
            ]
        if err_class == "type-error":
            return [
                "$sN.out is a string; do not pass it to a parameter that "
                "expects an integer or bool.",
            ]
        return []

    def _revise_plan_basic(
        self,
        goal: str,
        failed_plan: Plan,
        failed_step: dict[str, Any] | None,
        error: str,
    ) -> Plan | None:
        catalog = self.tools.describe()
        planner = Planner(self.provider, catalog)
        failed_id = failed_step.get("id", "?") if failed_step else "?"
        failed_tool = failed_step.get("tool", "?") if failed_step else "?"
        steps_summary = [
            {
                "id": s.id,
                "tool": s.tool,
                "args_keys": list(s.args.keys()),
                "depends_on": s.depends_on,
            }
            for s in failed_plan.steps
        ]
        prompt = (
            f"The following plan for goal {goal!r} failed.\n"
            f"Failed step: {failed_id} (tool={failed_tool})\n"
            f"Error: {error}\n"
            f"Original plan steps: {steps_summary}\n\n"
            f"Produce a COMPLETELY REVISED plan for the same goal. "
            f"The failed approach may be fundamentally wrong; if so, try a "
            f"different sequence of tools. Return only the revised plan "
            f"JSON in the standard schema. Each step MUST include: id (string), title (short human-readable description), tool (string tool name), args (object with tool arguments), depends_on (list of step ids this step depends on)."
        )
        try:
            return planner.plan(prompt, temperature=0.7)
        except ProviderError:
            raise
        except Exception as exc:
            log.info("revision plan invalid: %s", exc)
            return None

    def _revise_plan_rich(
        self,
        goal: str,
        failed_plan: Plan,
        full_result: dict[str, Any],
        failed_step: dict[str, Any] | None,
        error: str,
    ) -> Plan | None:
        catalog = self.tools.describe()
        planner = Planner(self.provider, catalog)
        results_by_id = {
            r.get("id"): r for r in (full_result.get("results") or [])
        }
        walk: list[dict[str, Any]] = []
        for s in failed_plan.steps:
            r = results_by_id.get(s.id, {})
            walk.append({
                "id": s.id,
                "tool": s.tool,
                "args": s.args,
                "ok": r.get("ok"),
                "output": (r.get("output") or "")[:200],
            })
        err_class = self._classify_error(error)
        suggestions = self._suggestions_for(err_class)

        lines: list[str] = []
        lines.append(f"REVISED ATTEMPT for goal: {goal!r}")
        lines.append("")
        lines.append("Full plan and outcomes:")
        for w in walk:
            status = "OK" if w["ok"] else "FAILED"
            lines.append(
                f"  - {w['id']}: {w['tool']}({w['args']}) -> {status}"
            )
            if not w["ok"]:
                lines.append(f"      error: {w['output']}")
        lines.append("")
        if failed_step:
            lines.append(
                f"Specific failure: step {failed_step.get('id')} "
                f"(tool={failed_step.get('tool')})"
            )
            lines.append(f"  error: {error}")
            lines.append(f"  classification: {err_class}")
            lines.append("")
        if suggestions:
            lines.append("Suggestions for the revised plan:")
            for s in suggestions:
                lines.append(f"  - {s}")
            lines.append("")
        lines.append(
            "Produce a COMPLETELY REVISED plan for the SAME goal. "
            "Do not repeat the failed approach. If the failing step was a "
            "tool-not-found error, the revised plan must first ensure the "
            "resource exists. If it was a template-syntax error, use only "
            "$id.field data-flow references. Return only the revised plan "
            "JSON in the standard schema. Each step MUST include: id (string), title (short human-readable description), tool (string tool name), args (object with tool arguments), depends_on (list of step ids this step depends on)."
        )
        prompt = "\n".join(lines)
        try:
            return planner.plan(prompt, temperature=0.7)
        except ProviderError:
            raise
        except Exception as exc:
            log.info("rich revision plan invalid: %s", exc)
            return None

    def execute(self, goal: str) -> RevisionResult:
        current_plan: Plan | None = None
        all_results: list[dict[str, Any]] = []
        run_ids: list[int] = []

        for revision in range(self.max_revisions + 1):
            coord = Coordinator(
                self.provider, self.tools, self.store, self.runtime,
            )
            try:
                if current_plan is None:
                    result = coord.execute(goal)
                else:
                    result = coord.execute_with_plan(goal, current_plan)
            except ProviderError:
                raise

            run_ids.append(result.get("run_id", -1))
            all_results.append(result)

            if result.get("status") == "succeeded":
                return RevisionResult(
                    goal=goal,
                    status="succeeded",
                    revisions_attempted=revision,
                    run_ids=run_ids,
                    final_result=result,
                    all_results=all_results,
                )

            if revision >= self.max_revisions:
                break

            failed_plan = Plan.model_validate(result["plan"])
            failed_step, error = self._extract_failure(result)
            if self.signal == "rich":
                revised = self._revise_plan_rich(
                    goal, failed_plan, result, failed_step, error,
                )
            else:
                revised = self._revise_plan_basic(
                    goal, failed_plan, failed_step, error,
                )
            if revised is None:
                break
            current_plan = revised

        return RevisionResult(
            goal=goal,
            status="failed",
            revisions_attempted=len(all_results) - 1 if all_results else 0,
            run_ids=run_ids,
            final_result=all_results[-1] if all_results else None,
            all_results=all_results,
        )
