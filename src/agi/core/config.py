"""Configuration loading: TOML file + environment overrides."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

from .errors import ConfigError


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class ProviderConfig(BaseModel):
    name: str = "echo"
    kind: str = "echo"
    base_url: str = "http://127.0.0.1:8000/v1"
    model: str = "deepseek-chat"
    api_key_env: str = "AGI_API_KEY"
    timeout_s: float = 600.0
    max_retries: int = 2
    supports_streaming: bool = True


class RuntimeConfig(BaseModel):
    log_level: str = "INFO"
    log_json: bool = False
    max_tool_calls: int = 32
    max_tokens_budget: int = 200_000
    max_wall_clock_s: int = 900


class StorageConfig(BaseModel):
    path: str = "state/agi.sqlite3"


class ToolsConfig(BaseModel):
    enabled: list[str] = Field(default_factory=lambda: ["fs_list", "fs_read", "fs_write"])
    fs_root: str = "state/workspace"
    shell_enabled: bool = False
    shell_allowlist: list[str] = Field(default_factory=list)
    shell_timeout_s: int = 10


class AppConfig(BaseModel):
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    source: str = "defaults"


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load configuration from TOML, then apply AGI_* environment overrides.

    - If an explicit path is passed, or AGI_CONFIG is set, that file must exist.
    - If nothing is requested, try ``config/default.toml`` and fall back to
      built-in defaults when it is absent.
    """
    explicit_path = path is not None
    env_path = os.environ.get("AGI_CONFIG")
    if explicit_path:
        cfg_path: str = str(path)
    elif env_path:
        cfg_path = env_path
        explicit_path = True
    else:
        cfg_path = "config/default.toml"

    data: dict = {}
    resolved: str | None = None

    candidate = Path(cfg_path)
    if candidate.is_file():
        data = _read_toml(candidate)
        resolved = str(candidate.resolve())
    elif explicit_path:
        raise ConfigError(f"config file not found: {candidate}")

    cfg = AppConfig(**data)
    cfg.provider.name = _env_str("AGI_PROVIDER", cfg.provider.name)
    cfg.provider.kind = _env_str("AGI_PROVIDER_KIND", cfg.provider.kind)
    cfg.provider.base_url = _env_str("AGI_BASE_URL", cfg.provider.base_url)
    cfg.provider.model = _env_str("AGI_MODEL", cfg.provider.model)
    cfg.provider.api_key_env = _env_str("AGI_API_KEY_ENV", cfg.provider.api_key_env)
    cfg.provider.timeout_s = _env_float("AGI_PROVIDER_TIMEOUT_S", cfg.provider.timeout_s)
    cfg.provider.max_retries = _env_int("AGI_PROVIDER_MAX_RETRIES", cfg.provider.max_retries)
    cfg.provider.supports_streaming = _env_bool("AGI_PROVIDER_STREAMING", cfg.provider.supports_streaming)
    cfg.runtime.log_level = _env_str("AGI_LOG_LEVEL", cfg.runtime.log_level).upper()
    cfg.runtime.log_json = _env_bool("AGI_LOG_JSON", cfg.runtime.log_json)
    cfg.storage.path = _env_str("AGI_STORAGE_PATH", cfg.storage.path)
    cfg.tools.fs_root = _env_str("AGI_FS_ROOT", cfg.tools.fs_root)
    cfg.tools.shell_enabled = _env_bool("AGI_SHELL_ENABLED", cfg.tools.shell_enabled)
    cfg.source = resolved or "defaults"

    if cfg.provider.kind not in {"echo", "openai_compat"}:
        raise ConfigError(f"unknown provider kind: {cfg.provider.kind!r}")
    return cfg
