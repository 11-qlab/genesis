"""Training infrastructure contracts.

Nothing in this module starts a training job. It defines the shapes that any
adapter and the future CLI must satisfy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetSummary:
    path: Path
    n_examples: int
    n_tokens: int
    checksum: str
    notes: str = ""


@dataclass
class TrainJob:
    name: str
    base_model: str
    dataset: DatasetSummary
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = True


class Trainer(ABC):
    """Abstract training adapter.

    Implementations may *prepare* everything (datasets, checkpoints dir,
    config validation) without starting a job. Starting requires
    ``TrainJob.dry_run is False`` **and** a caller that has already been
    gated by the CLI's ``--yes-train`` flag.
    """

    name: str

    @abstractmethod
    def estimate(self, job: TrainJob) -> dict[str, Any]:
        ...

    @abstractmethod
    def prepare(self, job: TrainJob) -> dict[str, Any]:
        ...

    @abstractmethod
    def run(self, job: TrainJob) -> dict[str, Any]:
        ...
