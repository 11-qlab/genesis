"""Allowlisted subprocess tool. Disabled unless explicitly configured."""

from __future__ import annotations

import shlex
import subprocess

from pydantic import BaseModel, Field

from .base import Tool, ToolResult


class _ShellArgs(BaseModel):
    command: str = Field(min_length=1)
    timeout_s: int = Field(default=10, ge=1, le=120)


class ShellTool(Tool):
    name = "shell"
    description = "Run an allowlisted command without a shell."
    args_model = _ShellArgs

    def __init__(self, allowlist: list[str], timeout_s: int = 10) -> None:
        self.allowlist = set(allowlist)
        self.default_timeout = timeout_s

    def run(self, command: str, timeout_s: int = 10) -> ToolResult:
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return ToolResult(ok=False, output=f"cannot parse command: {exc}")
        if not argv:
            return ToolResult(ok=False, output="empty command")
        if argv[0] not in self.allowlist:
            return ToolResult(ok=False, output=f"command not allowed: {argv[0]}")
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=min(timeout_s, self.default_timeout),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output=f"timed out after {timeout_s}s")
        output = (completed.stdout or "") + (completed.stderr or "")
        return ToolResult(
            ok=completed.returncode == 0,
            output=output.strip(),
            meta={"returncode": completed.returncode},
        )
