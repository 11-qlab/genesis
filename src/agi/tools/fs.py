"""Sandboxed filesystem tools."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from .base import Tool, ToolResult

_MAX_READ = 1_048_576


def _resolve(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes sandbox root: {relative!r}")
    return candidate


class _FSListArgs(BaseModel):
    path: str = Field(default=".", description="Path relative to the sandbox root.")


class FSListTool(Tool):
    name = "fs_list"
    description = "List directory entries inside the sandbox root."
    args_model = _FSListArgs

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def run(self, path: str = ".") -> ToolResult:
        try:
            target = _resolve(self.root, path)
        except ValueError as exc:
            return ToolResult(ok=False, output=str(exc))
        if not target.exists():
            return ToolResult(ok=False, output=f"not found: {path}")
        if not target.is_dir():
            return ToolResult(ok=False, output=f"not a directory: {path}")
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
        return ToolResult(
            ok=True,
            output="\n".join(entries) if entries else "(empty)",
            meta={"count": len(entries)},
        )


class _FSReadArgs(BaseModel):
    path: str
    max_bytes: int = Field(default=65536, ge=1, le=_MAX_READ)


class FSReadTool(Tool):
    name = "fs_read"
    description = "Read a UTF-8 text file from inside the sandbox root."
    args_model = _FSReadArgs

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def run(self, path: str, max_bytes: int = 65536) -> ToolResult:
        try:
            target = _resolve(self.root, path)
        except ValueError as exc:
            return ToolResult(ok=False, output=str(exc))
        if not target.is_file():
            return ToolResult(ok=False, output=f"not a file: {path}")
        data = target.read_bytes()[:max_bytes]
        return ToolResult(
            ok=True,
            output=data.decode("utf-8", "replace"),
            meta={"bytes": len(data)},
        )


_MODE_ALIASES = {
    "w": "overwrite", "w+": "overwrite", "write": "overwrite",
    "overwrite": "overwrite", "create": "overwrite", "truncate": "overwrite",
    "a": "append", "a+": "append", "append": "append", "add": "append",
}


class _FSWriteArgs(BaseModel):
    path: str
    content: str
    mode: str = Field(default="overwrite")

    @field_validator("mode", mode="before")
    @classmethod
    def _normalize_mode(cls, value):
        if not isinstance(value, str):
            return value
        normalized = _MODE_ALIASES.get(value.strip().lower())
        if normalized is None:
            raise ValueError(
                f"unknown mode {value!r}; expected one of "
                f"overwrite|append|w|a|write|create|truncate|add"
            )
        return normalized


class FSWriteTool(Tool):
    name = "fs_write"
    description = "Write UTF-8 text inside the sandbox root."
    args_model = _FSWriteArgs

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def run(self, path: str, content: str, mode: str = "overwrite") -> ToolResult:
        try:
            target = _resolve(self.root, path)
        except ValueError as exc:
            return ToolResult(ok=False, output=str(exc))
        target.parent.mkdir(parents=True, exist_ok=True)
        flags = "w" if mode == "overwrite" else "a"
        with target.open(flags, encoding="utf-8") as handle:
            handle.write(content)
        return ToolResult(
            ok=True,
            output=f"wrote {len(content)} chars to {path}",
            meta={"chars": len(content), "mode": mode},
        )
