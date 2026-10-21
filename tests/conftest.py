"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from agi.providers import EchoProvider
from agi.storage import Store
from agi.tools import build_registry
from agi.tools.registry import ToolRegistry

_AGI_ENV_VARS = (
    "AGI_API_KEYS", "AGI_API_KEY", "AGI_API_KEY_ENV",
    "AGI_PROVIDER", "AGI_PROVIDER_KIND",
    "AGI_BASE_URL", "AGI_MODEL",
    "AGI_PROVIDER_TIMEOUT_S", "AGI_PROVIDER_MAX_RETRIES",
    "AGI_PROVIDER_STREAMING",
    "AGI_STORAGE_PATH", "AGI_FS_ROOT",
    "AGI_SHELL_ENABLED", "AGI_EMBEDDING_KIND",
    "AGI_LOG_LEVEL", "AGI_LOG_JSON",
    "AGI_CONFIG",
)


@pytest.fixture(autouse=True)
def _clean_agi_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear AGI_* env vars so a shell with real keys/exports does not
    leak into the test suite. Every test starts from defaults; tests that
    need an override use monkeypatch.setenv explicitly."""
    for name in _AGI_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


@pytest.fixture()
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "test.sqlite3")
    yield s
    s.close()


@pytest.fixture()
def echo() -> EchoProvider:
    return EchoProvider()


@pytest.fixture()
def fs_tools(workspace: Path) -> ToolRegistry:
    return build_registry(["fs_list", "fs_read", "fs_write"], str(workspace))
