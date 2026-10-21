"""Interactive multi-turn conversation with tool execution.

Each user turn produces a fresh plan-execute cycle using the same
`Coordinator` the batch CLI uses. Between turns, prior turns are summarized
into a short context string that is prepended to the next goal — the plan
prompt sees "Recent context: ... Task: ..." and can reference things done in
earlier turns. This is not a memory system; it is a bounded conversation
buffer. Deliberately.

The conversation never changes the planner prompt. Any change to what the
model sees per turn is visible in the effective goal string that gets stored
in the run's `run.started` event.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..core.config import RuntimeConfig
from ..core.errors import AGIError
from ..core.logging import get_logger
from ..providers.base import Message, Provider
from ..storage.sqlite import Store
from ..tools.registry import ToolRegistry
from .coordinator import Coordinator

log = get_logger("agi.conversation")


@dataclass
class Turn:
    user: str
    effective_goal: str
    run_id: int | None
    status: str
    summary: str
    tool_sequence: tuple[str, ...] = ()
    results: list[dict] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class Conversation:
    provider: Provider
    tools: ToolRegistry
    store: Store
    runtime: RuntimeConfig
    max_turns: int = 20
    summarize: bool = True
    history: list[Turn] = field(default_factory=list)

    # -- helpers --------------------------------------------------------

    def _context_prefix(self) -> str:
        """Build a short summary of recent turns for the next plan prompt."""
        if not self.history:
            return ""
        recent = self.history[-4:]
        lines = ["Recent conversation context:"]
        for i, turn in enumerate(recent, 1):
            short_user = turn.user.strip().replace("\n", " ")[:120]
            short_summary = turn.summary.strip().replace("\n", " ")[:160]
            tools = ", ".join(turn.tool_sequence) or "(no tool)"
            lines.append(
                f"  {i}. user asked: {short_user!r}; "
                f"result: {turn.status}; used: {tools}; outcome: {short_summary}"
            )
        return "\n".join(lines) + "\n\n"

    def _effective_goal(self, user_message: str) -> str:
        prefix = self._context_prefix()
        if prefix:
            return f"{prefix}Task: {user_message}"
        return user_message

    def _summarize_run(self, user_message: str, result: dict) -> str:
        if not self.summarize:
            steps = result.get("results") or []
            return f"Ran {len(steps)} step(s); status: {result.get('status', '?')}."
        steps = result.get("results") or []
        brief = [
            {
                "tool": s.get("tool"),
                "ok": s.get("ok"),
                "output": (s.get("output") or "")[:400],
            }
            for s in steps
        ]
        messages = [
            Message(
                role="system",
                content=(
                    "You are summarizing the outcome of a multi-step tool run for "
                    "a user. Be concise: 1 to 3 sentences. Do not invent results. "
                    "If a step failed, say so and name the error."
                ),
            ),
            Message(
                role="user",
                content=(
                    f"User asked: {user_message}\n\n"
                    f"Execution status: {result.get('status', 'unknown')}\n"
                    f"Steps:\n{brief}"
                ),
            ),
        ]
        try:
            completion = self.provider.complete(messages, temperature=0.0)
        except AGIError as exc:
            return f"(summary unavailable: {exc})"
        return completion.text.strip() or "(empty summary)"

    # -- public --------------------------------------------------------

    def run_turn(self, user_message: str) -> Turn:
        if len(self.history) >= self.max_turns:
            raise RuntimeError(
                f"max_turns={self.max_turns} reached; start a new Conversation"
            )
        started = time.monotonic()
        effective = self._effective_goal(user_message)
        coordinator = Coordinator(
            self.provider, self.tools, self.store, self.runtime,
        )
        run_id: int | None = None
        status = "error"
        summary = ""
        tool_sequence: tuple[str, ...] = ()
        results: list[dict] = []
        try:
            result = coordinator.execute(effective)
            run_id = result.get("run_id")
            status = result.get("status", "unknown")
            results = result.get("results") or []
            tool_sequence = tuple(
                s.get("tool") for s in results if s.get("tool")
            )
            summary = self._summarize_run(user_message, result)
        except AGIError as exc:
            status = "error"
            summary = f"run failed: {exc}"
            log.warning("conversation turn failed: %s", exc)

        turn = Turn(
            user=user_message,
            effective_goal=effective,
            run_id=run_id,
            status=status,
            summary=summary,
            tool_sequence=tool_sequence,
            results=results,
            duration_ms=(time.monotonic() - started) * 1000.0,
        )
        self.history.append(turn)
        return turn

    def clear(self) -> None:
        self.history.clear()
