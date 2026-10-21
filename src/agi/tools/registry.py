"""Typed tool registry with schema validation."""

from __future__ import annotations

from typing import Any

from ..core.errors import ToolError
from ..core.registry import Registry
from .base import Tool, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._registry: Registry[Tool] = Registry("tool")

    def register(self, tool: Tool) -> None:
        self._registry.register(tool.name, tool)

    def get(self, name: str) -> Tool:
        try:
            return self._registry.get(name)
        except Exception as exc:
            raise ToolError(f"unknown tool: {name}") from exc

    def names(self) -> list[str]:
        return self._registry.names()

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "args_schema": tool.args_model.model_json_schema(),
            }
            for tool in (self._registry.get(name) for name in self._registry.names())
        ]

    def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        tool = self.get(name)
        try:
            validated = tool.validate_args(args)
        except Exception as exc:
            raise ToolError(f"invalid arguments for {name}: {exc}") from exc
        return tool.run(**validated.model_dump())
