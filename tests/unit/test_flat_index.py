from __future__ import annotations

import numpy as np

from agi.memory import FlatIndex


def test_search_orders_by_similarity() -> None:
    idx = FlatIndex()
    v = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], dtype=np.float32)
    idx.add(
        row_ids=[1, 2, 3],
        document_ids=["a", "a", "b"],
        chunk_indexes=[0, 1, 0],
        texts=["one", "two", "three"],
        vectors=v,
    )
    hits = idx.search(np.array([1.0, 0.0], dtype=np.float32), k=2)
    assert [h.chunk_row_id for h in hits] == [1, 2]
    assert hits[0].score > hits[1].score


def test_empty_index() -> None:
    idx = FlatIndex()
    assert idx.search(np.zeros(4, dtype=np.float32)) == []
    assert len(idx) == 0
