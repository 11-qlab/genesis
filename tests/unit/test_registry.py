from __future__ import annotations

import pytest

from agi.core.registry import Registry, RegistryError


def test_register_get_names() -> None:
    reg: Registry[int] = Registry("item")
    reg.register("b", 2)
    reg.register("a", 1)
    assert reg.get("a") == 1
    assert reg.names() == ["a", "b"]
    assert "a" in reg
    assert len(reg) == 2


def test_duplicate_raises() -> None:
    reg: Registry[int] = Registry("item")
    reg.register("x", 1)
    with pytest.raises(RegistryError):
        reg.register("x", 2)
    reg.register("x", 3, overwrite=True)
    assert reg.get("x") == 3


def test_unknown_raises() -> None:
    reg: Registry[int] = Registry("item")
    with pytest.raises(RegistryError):
        reg.get("nope")
    assert reg.find("nope") is None
