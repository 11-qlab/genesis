from __future__ import annotations

import os

import pytest

from agi.core.config import load_config
from agi.memory import build_embedding


def _build(cfg):
    kind = os.environ.get("AGI_EMBEDDING_KIND", "hash").lower()
    if kind == "openai_compat":
        return build_embedding(
            "openai_compat",
            base_url=cfg.provider.base_url,
            model=cfg.provider.model,
            api_key_env=cfg.provider.api_key_env,
        )
    return build_embedding("hash", dim=256)


def test_default_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGI_EMBEDDING_KIND", raising=False)
    cfg = load_config()
    embedder = _build(cfg)
    assert embedder.name == "hash"
    assert embedder.dim == 256


def test_override_openai_compat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGI_EMBEDDING_KIND", "openai_compat")
    cfg = load_config()
    embedder = _build(cfg)
    assert embedder.name == "openai_compat"
