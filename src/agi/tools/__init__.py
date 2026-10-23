from .base import Tool, ToolResult
from .fs import FSListTool, FSReadTool, FSWriteTool
from .registry import ToolRegistry
from .shell import ShellTool


def build_registry(
    enabled: list[str],
    fs_root: str,
    shell_enabled: bool = False,
    shell_allowlist: list[str] | None = None,
    shell_timeout_s: int = 10,
) -> ToolRegistry:
    registry = ToolRegistry()
    factories = {
        "fs_list": lambda: FSListTool(fs_root),
        "fs_read": lambda: FSReadTool(fs_root),
        "fs_write": lambda: FSWriteTool(fs_root),
        "shell": lambda: ShellTool(shell_allowlist or [], shell_timeout_s),
    }
    for name in enabled:
        if name not in factories:
            raise ValueError(f"unknown tool: {name}")
        if name == "shell" and not shell_enabled:
            continue
        registry.register(factories[name]())
    import os as _os
    if _os.environ.get("AGI_TOOLS_EXTENDED", "").strip().lower() in ("1", "true", "yes"):
        from .extra import build_extra_tools
        for extra in build_extra_tools(fs_root):
            registry.register(extra)

    # --- family tools (12-family distribution test) ---
    import os as _os
    if _os.environ.get('AGI_TOOLS_FAMILIES') == '1':
        from . import family_tools as _family_tools
        _family_tools.register_all(registry, fs_root)
    return registry


__all__ = [
    "FSListTool",
    "FSReadTool",
    "FSWriteTool",
    "ShellTool",
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "build_registry",
]
