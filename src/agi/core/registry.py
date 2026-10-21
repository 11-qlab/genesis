"""A tiny named-component registry."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Generic, TypeVar

from .errors import AGIError

T = TypeVar("T")


class RegistryError(AGIError):
    """A registry lookup or insertion failed."""


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, T] = {}

    def register(self, name: str, item: T, *, overwrite: bool = False) -> None:
        if name in self._items and not overwrite:
            raise RegistryError(f"{self.kind} already registered: {name}")
        self._items[name] = item

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError as exc:
            raise RegistryError(f"unknown {self.kind}: {name}") from exc

    def find(self, name: str) -> T | None:
        return self._items.get(name)

    def names(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def __iter__(self) -> Iterator[str]:
        return iter(self.names())

    def __len__(self) -> int:
        return len(self._items)
