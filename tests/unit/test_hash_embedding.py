from __future__ import annotations

import numpy as np

from agi.memory import HashEmbedding


def test_deterministic() -> None:
    e = HashEmbedding(dim=64)
    a = e.embed(["hello world"])
    b = e.embed(["hello world"])
    assert np.allclose(a, b)


def test_unit_norm() -> None:
    e = HashEmbedding(dim=64)
    v = e.embed(["the quick brown fox"])[0]
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-5


def test_similarity() -> None:
    e = HashEmbedding(dim=256)
    v1 = e.embed(["list the workspace files"])[0]
    v2 = e.embed(["show the files in the workspace"])[0]
    v3 = e.embed(["completely unrelated topic about music"])[0]
    s12 = float(v1 @ v2)
    s13 = float(v1 @ v3)
    assert s12 > s13


def test_empty_input() -> None:
    e = HashEmbedding(dim=32)
    arr = e.embed([])
    assert arr.shape == (0, 32)
