"""Structured plan schema with DAG validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    goal: str = Field(min_length=1)
    steps: list[PlanStep] = Field(default_factory=list)

    def validate_graph(self, known_tools: set[str]) -> list[str]:
        problems: list[str] = []
        ids = [step.id for step in self.steps]
        if len(set(ids)) != len(ids):
            problems.append("duplicate step ids")

        seen: set[str] = set()
        for step in self.steps:
            for dependency in step.depends_on:
                if dependency not in ids:
                    problems.append(
                        f"step {step.id!r} depends on unknown step {dependency!r}"
                    )
                elif dependency not in seen:
                    problems.append(
                        f"step {step.id!r} depends on later step {dependency!r}"
                    )
            seen.add(step.id)
            if step.tool and step.tool not in known_tools:
                problems.append(
                    f"step {step.id!r} uses unknown tool {step.tool!r}"
                )

        if not problems:
            graph = {step.id: set(step.depends_on) for step in self.steps}
            temporary: set[str] = set()
            permanent: set[str] = set()

            def visit(node: str) -> bool:
                if node in permanent:
                    return True
                if node in temporary:
                    return False
                temporary.add(node)
                for dependency in graph[node]:
                    if not visit(dependency):
                        return False
                temporary.discard(node)
                permanent.add(node)
                return True

            for node in graph:
                if not visit(node):
                    problems.append("dependency cycle detected")
                    break

        return problems

    def topo_order(self) -> list[PlanStep]:
        remaining = list(self.steps)
        done: set[str] = set()
        ordered: list[PlanStep] = []
        while remaining:
            progressed = False
            for step in list(remaining):
                if all(dep in done for dep in step.depends_on):
                    ordered.append(step)
                    done.add(step.id)
                    remaining.remove(step)
                    progressed = True
            if not progressed:
                raise ValueError("plan contains a dependency cycle")
        return ordered
