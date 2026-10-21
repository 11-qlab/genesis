"""Flat cosine similarity index. Small scale, no external DB."""

from __future__ import annotations

from dataclasses import dataclass

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

from .documents import MemoryError


@dataclass(frozen=True)
class SearchHit:
    chunk_row_id: int
    document_id: str
    chunk_index: int
    text: str
    score: float


class FlatIndex:
    def __init__(self) -> None:
        if np is None:
            raise MemoryError("numpy is required for FlatIndex")
        self._ids: list[int] = []
        self._doc_ids: list[str] = []
        self._chunk_idxs: list[int] = []
        self._texts: list[str] = []
        self._matrix: np.ndarray | None = None

    def add(
        self,
        *,
        row_ids: list[int],
        document_ids: list[str],
        chunk_indexes: list[int],
        texts: list[str],
        vectors: np.ndarray,
    ) -> None:
        if not row_ids:
            return
        if not (
            len(row_ids) == len(document_ids) == len(chunk_indexes)
            == len(texts) == vectors.shape[0]
        ):
            raise MemoryError("add() length mismatch")
        self._ids.extend(row_ids)
        self._doc_ids.extend(document_ids)
        self._chunk_idxs.extend(chunk_indexes)
        self._texts.extend(texts)
        if self._matrix is None:
            self._matrix = vectors.astype(np.float32, copy=True)
        else:
            self._matrix = np.vstack([self._matrix, vectors.astype(np.float32)])

    def search(self, query: np.ndarray, *, k: int = 5) -> list[SearchHit]:
        if self._matrix is None or self._matrix.shape[0] == 0:
            return []
        q = query.astype(np.float32).reshape(-1)
        qn = float(np.linalg.norm(q))
        if qn > 0:
            q = q / qn
        scores = self._matrix @ q
        order = np.argsort(-scores)[: max(1, k)]
        hits: list[SearchHit] = []
        for idx in order:
            hits.append(SearchHit(
                chunk_row_id=self._ids[int(idx)],
                document_id=self._doc_ids[int(idx)],
                chunk_index=self._chunk_idxs[int(idx)],
                text=self._texts[int(idx)],
                score=float(scores[int(idx)]),
            ))
        return hits

    def __len__(self) -> int:
        return len(self._ids)
