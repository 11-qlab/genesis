"""Health and environment diagnostics."""

from __future__ import annotations

import platform
import sys
from typing import Any

from ..core.config import AppConfig
from ..providers.router import ProviderRouter
from ..storage.sqlite import Store
from ..tools.registry import ToolRegistry


def environment_info() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def collect_health(
    cfg: AppConfig,
    router: ProviderRouter,
    tools: ToolRegistry,
    store: Store,
) -> dict[str, Any]:
    providers = router.health()
    return {
        "config_source": cfg.source,
        "environment": environment_info(),
        "providers": providers,
        "provider_ok": bool(providers) and all(p.get("ok", False) for p in providers),
        "tools": tools.names(),
        "storage": {"path": str(store.path), "ok": store.path.exists()},
    }
