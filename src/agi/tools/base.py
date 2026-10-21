"""Tool contract: name, description, validated arguments, execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    ok: bool = True
    output: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str] = ""
    args_model: ClassVar[type[BaseModel]]

    def validate_args(self, args: dict[str, Any]) -> BaseModel:
        return self.args_model(**args)

    @abstractmethod
    def run(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with already-validated keyword arguments."""
