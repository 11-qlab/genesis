"""Benchmark protocol and pass/fail rules.

A benchmark wraps a dataset with a per-item checker. The default checker
compares the executed run's status and (optionally) the first tool the
coordinator invoked against the dataset item's expectations.
"""

from __future__ import annotations
import os

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .dataset import Dataset, DatasetItem, load_dataset


@dataclass(frozen=True)
class ItemOutcome:
    item: DatasetItem
    run_status: str
    tool_used: str | None
    duration_ms: float
    run_id: int | None
    passed: bool
    detail: str = ""
    tool_sequence: tuple[str, ...] = ()
    steps: list[dict] | None = None
    agreement: float | None = None
    calibration_estimate: int | None = None


@dataclass(frozen=True)
class EvalResult:
    benchmark: str
    provider: str
    model: str
    total: int
    passed: int
    duration_ms: float
    items: tuple[ItemOutcome, ...]
    eval_run_id: int | None = None
    contaminated: bool = False
    rate_limited_items: int = 0
    strategy: str = "greedy"
    mean_agreement: float | None = None
    brier: float | None = None
    ece: float | None = None

    @property
    def accuracy(self) -> float:
        return (self.passed / self.total) if self.total else 0.0


@runtime_checkable
class Checker(Protocol):
    def __call__(
        self,
        item: DatasetItem,
        run_status: str,
        tool_used: str | None,
        tool_sequence: tuple[str, ...] = (),
    ) -> tuple[bool, str]: ...


def default_checker(
    item: DatasetItem,
    run_status: str,
    tool_used: str | None,
    tool_sequence: tuple[str, ...] = (),
) -> tuple[bool, str]:
    if run_status != item.expect_status:
        return False, f"status {run_status!r} != expected {item.expect_status!r}"
    if item.expect_tool is not None and tool_used != item.expect_tool:
        return False, f"tool {tool_used!r} != expected {item.expect_tool!r}"
    expected_seq = item.raw.get("expect_sequence")
    if expected_seq is not None and list(tool_sequence) != list(expected_seq):
        return False, (
            f"sequence {list(tool_sequence)} != expected {list(expected_seq)}"
        )
    expected_sub = item.raw.get("expect_subsequence")
    if expected_sub is not None:
        seq = list(tool_sequence)
        sub = list(expected_sub)
        if not _contains_subsequence(seq, sub):
            return False, (
                f"sequence {seq} does not contain subsequence {sub}"
            )
    return True, ""


def _contains_subsequence(seq: list, sub: list) -> bool:
    if not sub:
        return True
    it = iter(seq)
    return all(any(x == wanted for x in it) for wanted in sub)


def _extract_seed_files(path: Path) -> dict[str, list[dict]]:
    """Read raw JSONL, extract seed_files entries per item id."""
    import json as _json
    seed_map: dict[str, list[dict]] = {}
    if not path.exists():
        return seed_map
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            raw = _json.loads(line)
        except Exception:
            continue
        item_id = raw.get("id")
        seed_files = raw.get("seed_files")
        if not (item_id and seed_files):
            continue
        # Bench files use {"path": "content"} dicts. The hook expects
        # [{"path": ..., "content": ...}]. Normalize here so callers
        # (including --seed none) get a consistent shape.
        if isinstance(seed_files, dict):
            seed_map[item_id] = [
                {"path": k, "content": v} for k, v in seed_files.items()
            ]
        elif isinstance(seed_files, list):
            seed_map[item_id] = seed_files
        # unknown shape -> skip silently
    return seed_map


def _make_seed_hook(seed_map: dict[str, list[dict]]):
    """Return a before_each hook that writes seed_files under AGI_FS_ROOT."""
    from pathlib import Path as _P

    def _seed(item) -> None:
        item_id = getattr(item, "id", None)
        if not item_id:
            return
        seed_files = seed_map.get(item_id)
        if not seed_files:
            return
        # Defensive: accept dict form ({path: content}) as well
        if isinstance(seed_files, dict):
            seed_files = [
                {"path": k, "content": v} for k, v in seed_files.items()
            ]
        root = _P(os.environ.get("AGI_FS_ROOT", "state/workspace")).resolve()
        root.mkdir(parents=True, exist_ok=True)
        for sf in seed_files:
            rel = sf.get("path")
            if not rel or rel.startswith("/") or ".." in rel.split("/"):
                continue
            target = (root / rel).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(sf.get("content", ""))

    return _seed


@dataclass(frozen=True)
class Benchmark:
    """A dataset + a pass/fail rule.

    ``before_each`` is an optional hook invoked with each ``DatasetItem``
    before the coordinator runs. Stateful benchmarks (memory retrieval, for
    example) use it to seed per-item state into the store. The default runner
    calls it once per item; failures are recorded as item errors, not run
    crashes.
    """

    name: str
    dataset: Dataset
    checker: Checker = default_checker
    before_each: Callable[[DatasetItem], None] | None = None

    @classmethod
    def from_file(cls, path: str | Path, *, name: str | None = None) -> Benchmark:
        path = Path(path)
        seed_map = _extract_seed_files(path)
        try:
            ds = load_dataset(path)
        except Exception:
            import json as _json
            import tempfile
            stripped = []
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                raw = _json.loads(line)
                raw.pop("seed_files", None)
                stripped.append(_json.dumps(raw))
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsonl", delete=False, dir=str(path.parent)
            )
            tmp.write("\n".join(stripped) + "\n")
            tmp.close()
            try:
                ds = load_dataset(tmp.name)
            finally:
                try:
                    os.remove(tmp.name)
                except OSError:
                    pass
        before_each = _make_seed_hook(seed_map) if seed_map else None
        return cls(name=name or ds.name, dataset=ds, before_each=before_each)


def first_tool_from_result(result: dict[str, Any]) -> str | None:
    """Extract the first tool the coordinator ran from a run result dict."""
    steps = result.get("results") or []
    for step in steps:
        tool = step.get("tool")
        if tool:
            return tool
    return None


def tool_sequence_from_result(result: dict[str, Any]) -> tuple[str, ...]:
    """Ordered list of every tool executed in the run.

    Uses each step's `tools_invoked` when present (which includes recovery +
    retry calls), otherwise falls back to the primary `tool` field per step.
    """
    steps = result.get("results") or []
    flat: list[str] = []
    for s in steps:
        invoked = s.get("tools_invoked")
        if invoked:
            flat.extend(t for t in invoked if t)
        else:
            t = s.get("tool")
            if t:
                flat.append(t)
    return tuple(flat)
