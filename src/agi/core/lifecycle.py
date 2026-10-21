"""Minimal process lifecycle coordinator."""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable


class Lifecycle:
    def __init__(self) -> None:
        self._shutdown = threading.Event()
        self._hooks: list[Callable[[], None]] = []

    @property
    def shutting_down(self) -> bool:
        return self._shutdown.is_set()

    def request_shutdown(self) -> None:
        if self._shutdown.is_set():
            return
        self._shutdown.set()
        for hook in reversed(self._hooks):
            with contextlib.suppress(Exception):
                hook()

    def on_shutdown(self, hook: Callable[[], None]) -> None:
        self._hooks.append(hook)

    def reset(self) -> None:
        self._shutdown.clear()
        self._hooks.clear()
