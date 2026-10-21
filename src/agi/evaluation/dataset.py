"""JSONL dataset loader for evaluation benchmarks.

Each line is one item. Required fields: ``goal`` (str), ``expect_tool`` (str|None).
Optional: ``expect_status`` (str, default "succeeded"), ``id`` (str), ``tags``
(list of str). Unknown fields are kept verbatim in ``raw`` for downstream use.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class DatasetError(ValueError):
    """A dataset is malformed or missing required fields."""


@dataclass(frozen=True)
class DatasetItem:
    id: str
    goal: str
    expect_tool: str | None
    expect_status: str = "succeeded"
    tags: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Dataset:
    name: str
    path: Path
    items: tuple[DatasetItem, ...]

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[DatasetItem]:
        return iter(self.items)


def _parse_item(idx: int, line: str, source: Path) -> DatasetItem:
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise DatasetError(f"{source}:{idx}: invalid JSON ({exc})") from exc
    if not isinstance(obj, dict):
        raise DatasetError(f"{source}:{idx}: item must be a JSON object")

    goal = obj.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise DatasetError(f"{source}:{idx}: 'goal' must be a non-empty string")

    if "expect_tool" not in obj:
        raise DatasetError(f"{source}:{idx}: 'expect_tool' is required (may be null)")
    expect_tool = obj["expect_tool"]
    if expect_tool is not None and not isinstance(expect_tool, str):
        raise DatasetError(f"{source}:{idx}: 'expect_tool' must be string or null")

    expect_status = obj.get("expect_status", "succeeded")
    if expect_status not in {"succeeded", "failed"}:
        raise DatasetError(
            f"{source}:{idx}: 'expect_status' must be 'succeeded' or 'failed'"
        )

    tags = obj.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise DatasetError(f"{source}:{idx}: 'tags' must be a list of strings")

    item_id = obj.get("id")
    if not isinstance(item_id, str) or not item_id:
        item_id = f"item-{idx}"

    return DatasetItem(
        id=item_id,
        goal=goal.strip(),
        expect_tool=expect_tool,
        expect_status=expect_status,
        tags=tuple(tags),
        raw=obj,
    )


def load_dataset(path: str | Path) -> Dataset:
    path = Path(path)
    if not path.is_file():
        raise DatasetError(f"dataset not found: {path}")
    items: list[DatasetItem] = []
    with path.open("r", encoding="utf-8") as fh:
        for idx, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            items.append(_parse_item(idx, line, path))
    if not items:
        raise DatasetError(f"dataset is empty: {path}")
    return Dataset(name=path.stem, path=path, items=tuple(items))
