from __future__ import annotations

from pathlib import Path

import pytest

from agi.core import ConfigError, load_config


def test_defaults_without_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.source == "defaults"
    assert cfg.provider.kind == "echo"
    assert cfg.tools.enabled == ["fs_list", "fs_read", "fs_write"]
    assert cfg.tools.shell_enabled is False


def test_loads_toml(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text(
        '[provider]\nkind = "openai_compat"\nname = "local"\nmodel = "x"\n'
        '[tools]\nfs_root = "/tmp/ws"\n',
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.provider.kind == "openai_compat"
    assert cfg.provider.name == "local"
    assert cfg.tools.fs_root == "/tmp/ws"


def test_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGI_PROVIDER_KIND", "openai_compat")
    monkeypatch.setenv("AGI_PROVIDER", "remote")
    monkeypatch.setenv("AGI_MODEL", "m1")
    monkeypatch.setenv("AGI_PROVIDER_TIMEOUT_S", "12.5")
    cfg = load_config()
    assert cfg.provider.kind == "openai_compat"
    assert cfg.provider.name == "remote"
    assert cfg.provider.model == "m1"
    assert cfg.provider.timeout_s == 12.5


def test_bad_kind_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGI_PROVIDER_KIND", "nonsense")
    with pytest.raises(ConfigError):
        load_config()


def test_bad_int_env_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGI_PROVIDER_MAX_RETRIES", "not-an-int")
    with pytest.raises(ConfigError):
        load_config()


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.toml")
