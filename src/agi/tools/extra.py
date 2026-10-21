"""Extended tool catalog for broad-transfer (T11, §1).

15 extra tools, sandboxed/pure. Opt-in via AGI_TOOLS_EXTENDED=1 so the
default catalog stays at 5.
"""
from __future__ import annotations

import base64
import glob as _glob
import hashlib
import json
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from .base import Tool, ToolResult


def _resolve(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes sandbox: {relative!r}")
    return candidate


class _PathArgs(BaseModel):
    path: str


class FsExistsTool(Tool):
    name = "fs_exists"
    description = "Return whether a path exists inside the sandbox."
    args_model = _PathArgs

    def __init__(self, root):
        self.root = Path(root)

    def run(self, path: str) -> ToolResult:
        try:
            p = _resolve(self.root, path)
        except ValueError as e:
            return ToolResult(ok=False, output=str(e))
        return ToolResult(ok=True, output="yes" if p.exists() else "no")


class FsSizeTool(Tool):
    name = "fs_size"
    description = "Return size in bytes of a file inside the sandbox."
    args_model = _PathArgs

    def __init__(self, root):
        self.root = Path(root)

    def run(self, path: str) -> ToolResult:
        try:
            p = _resolve(self.root, path)
        except ValueError as e:
            return ToolResult(ok=False, output=str(e))
        if not p.is_file():
            return ToolResult(ok=False, output=f"not a file: {path}")
        return ToolResult(ok=True, output=str(p.stat().st_size))


class FsMkdirTool(Tool):
    name = "fs_mkdir"
    description = "Create a directory inside the sandbox."
    args_model = _PathArgs

    def __init__(self, root):
        self.root = Path(root)

    def run(self, path: str) -> ToolResult:
        try:
            p = _resolve(self.root, path)
        except ValueError as e:
            return ToolResult(ok=False, output=str(e))
        p.mkdir(parents=True, exist_ok=True)
        return ToolResult(ok=True, output=f"created {path}")


class _MoveArgs(BaseModel):
    src: str
    dst: str


class FsMoveTool(Tool):
    name = "fs_move"
    description = "Move or rename a file inside the sandbox."
    args_model = _MoveArgs

    def __init__(self, root):
        self.root = Path(root)

    def run(self, src: str, dst: str) -> ToolResult:
        try:
            a = _resolve(self.root, src)
            b = _resolve(self.root, dst)
        except ValueError as e:
            return ToolResult(ok=False, output=str(e))
        if not a.exists():
            return ToolResult(ok=False, output=f"not found: {src}")
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(a), str(b))
        return ToolResult(ok=True, output=f"moved {src} -> {dst}")


class FsDeleteTool(Tool):
    name = "fs_delete"
    description = "Delete a file inside the sandbox."
    args_model = _PathArgs

    def __init__(self, root):
        self.root = Path(root)

    def run(self, path: str) -> ToolResult:
        try:
            p = _resolve(self.root, path)
        except ValueError as e:
            return ToolResult(ok=False, output=str(e))
        if not p.is_file():
            return ToolResult(ok=False, output=f"not a file: {path}")
        p.unlink()
        return ToolResult(ok=True, output=f"deleted {path}")


class _GlobArgs(BaseModel):
    pattern: str


class FsGlobTool(Tool):
    name = "fs_glob"
    description = "List files matching a glob pattern inside the sandbox."
    args_model = _GlobArgs

    def __init__(self, root):
        self.root = Path(root)

    def run(self, pattern: str) -> ToolResult:
        root = self.root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        matches = sorted(
            str(Path(p).relative_to(root))
            for p in _glob.glob(str(root / pattern), recursive=True)
        )
        return ToolResult(
            ok=True, output="\n".join(matches) if matches else "(none)",
            meta={"count": len(matches)},
        )


class _TextArgs(BaseModel):
    text: str


class TextUpperTool(Tool):
    name = "text_upper"
    description = "Uppercase a text string."
    args_model = _TextArgs

    def run(self, text: str) -> ToolResult:
        return ToolResult(ok=True, output=text.upper())


class TextLowerTool(Tool):
    name = "text_lower"
    description = "Lowercase a text string."
    args_model = _TextArgs

    def run(self, text: str) -> ToolResult:
        return ToolResult(ok=True, output=text.lower())


class TextReverseTool(Tool):
    name = "text_reverse"
    description = "Reverse a text string."
    args_model = _TextArgs

    def run(self, text: str) -> ToolResult:
        return ToolResult(ok=True, output=text[::-1])


class TextLengthTool(Tool):
    name = "text_length"
    description = "Return number of characters in a text string."
    args_model = _TextArgs

    def run(self, text: str) -> ToolResult:
        return ToolResult(ok=True, output=str(len(text)))


class _HashFileArgs(BaseModel):
    path: str
    algorithm: str = Field(default="sha256", pattern="^(sha256|md5)$")


class HashFileTool(Tool):
    name = "hash_file"
    description = "Compute sha256/md5 of a file inside the sandbox."
    args_model = _HashFileArgs

    def __init__(self, root):
        self.root = Path(root)

    def run(self, path: str, algorithm: str = "sha256") -> ToolResult:
        try:
            p = _resolve(self.root, path)
        except ValueError as e:
            return ToolResult(ok=False, output=str(e))
        if not p.is_file():
            return ToolResult(ok=False, output=f"not a file: {path}")
        h = hashlib.new(algorithm)
        h.update(p.read_bytes())
        return ToolResult(ok=True, output=h.hexdigest())


class _HashTextArgs(BaseModel):
    text: str
    algorithm: str = Field(default="sha256", pattern="^(sha256|md5)$")


class HashTextTool(Tool):
    name = "hash_text"
    description = "Compute sha256/md5 of a text string."
    args_model = _HashTextArgs

    def run(self, text: str, algorithm: str = "sha256") -> ToolResult:
        h = hashlib.new(algorithm)
        h.update(text.encode("utf-8"))
        return ToolResult(ok=True, output=h.hexdigest())


class Base64EncodeTool(Tool):
    name = "base64_encode"
    description = "Base64-encode a text string."
    args_model = _TextArgs

    def run(self, text: str) -> ToolResult:
        return ToolResult(ok=True, output=base64.b64encode(text.encode()).decode())


class Base64DecodeTool(Tool):
    name = "base64_decode"
    description = "Base64-decode a text string."
    args_model = _TextArgs

    def run(self, text: str) -> ToolResult:
        try:
            return ToolResult(
                ok=True, output=base64.b64decode(text).decode("utf-8", "replace"),
            )
        except Exception as e:
            return ToolResult(ok=False, output=f"decode failed: {e}")


class _JsonArgs(BaseModel):
    text: str
    path: str = ""


class JsonGetTool(Tool):
    name = "json_get"
    description = "Navigate a JSON string by dot-path and return the value."
    args_model = _JsonArgs

    def run(self, text: str, path: str = "") -> ToolResult:
        try:
            node = json.loads(text)
        except json.JSONDecodeError as e:
            return ToolResult(ok=False, output=f"invalid json: {e}")
        if path:
            for part in path.split("."):
                if isinstance(node, dict):
                    if part not in node:
                        return ToolResult(ok=False, output=f"key not found: {part}")
                    node = node[part]
                elif isinstance(node, list):
                    try:
                        node = node[int(part)]
                    except (ValueError, IndexError):
                        return ToolResult(ok=False, output=f"bad index: {part}")
                else:
                    return ToolResult(ok=False, output="cannot descend")
        return ToolResult(
            ok=True, output=json.dumps(node) if not isinstance(node, str) else node,
        )


def build_extra_tools(fs_root):
    return [
        FsExistsTool(fs_root), FsSizeTool(fs_root), FsMkdirTool(fs_root),
        FsMoveTool(fs_root), FsDeleteTool(fs_root), FsGlobTool(fs_root),
        TextUpperTool(), TextLowerTool(), TextReverseTool(), TextLengthTool(),
        HashFileTool(fs_root), HashTextTool(),
        Base64EncodeTool(), Base64DecodeTool(), JsonGetTool(),
    ]
