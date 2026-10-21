"""Structured reasoning trace.

Every planner call, tool call, and recovery attempt is a TraceEvent. The
trace is the ground truth for post-hoc analysis: what the model actually
saw, what it produced, what tool was actually called, what came back.

Nothing in this module changes behavior. It observes.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TraceEvent:
    kind: str
    ts: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Trace:
    """A single run's trace. One Trace per Coordinator.execute call."""

    run_id: int
    events: list[TraceEvent] = field(default_factory=list)

    def add(self, kind: str, **payload: Any) -> TraceEvent:
        ev = TraceEvent(kind=kind, payload=payload)
        self.events.append(ev)
        return ev

    def filter(self, kind: str) -> list[TraceEvent]:
        return [e for e in self.events if e.kind == kind]

    def summary(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        for ev in self.events:
            by_kind[ev.kind] = by_kind.get(ev.kind, 0) + 1
        return {
            "run_id": self.run_id,
            "total_events": len(self.events),
            "by_kind": by_kind,
        }

    def as_dicts(self) -> list[dict[str, Any]]:
        return [ev.as_dict() for ev in self.events]
