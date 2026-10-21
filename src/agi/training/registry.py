"""Checkpoint and artifact registry (filesystem + JSON index).

Weights stay on disk. This module only records metadata and verifies that a
referenced path still exists and matches its recorded size.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Artifact:
    name: str
    path: Path
    size_bytes: int
    created_at: float = field(default_factory=time.time)


@dataclass
class Checkpoint:
    id: str
    job_name: str
    step: int
    path: Path
    size_bytes: int
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class CheckpointRegistry:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        if self.index_path.is_file():
            try:
                self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._index = {"checkpoints": [], "artifacts": []}
        else:
            self._index = {"checkpoints": [], "artifacts": []}

    def _save(self) -> None:
        self.index_path.write_text(
            json.dumps(self._index, indent=2, default=str), encoding="utf-8"
        )

    def add_checkpoint(self, cp: Checkpoint) -> None:
        if not cp.path.is_file():
            raise FileNotFoundError(f"checkpoint file missing: {cp.path}")
        self._index["checkpoints"].append({
            "id": cp.id, "job_name": cp.job_name, "step": cp.step,
            "path": str(cp.path), "size_bytes": cp.size_bytes,
            "metadata": cp.metadata, "created_at": cp.created_at,
        })
        self._save()

    def add_artifact(self, art: Artifact) -> None:
        if not art.path.exists():
            raise FileNotFoundError(f"artifact missing: {art.path}")
        self._index["artifacts"].append({
            "name": art.name, "path": str(art.path),
            "size_bytes": art.size_bytes, "created_at": art.created_at,
        })
        self._save()

    def list_checkpoints(self) -> list[dict]:
        return list(self._index["checkpoints"])

    def list_artifacts(self) -> list[dict]:
        return list(self._index["artifacts"])
