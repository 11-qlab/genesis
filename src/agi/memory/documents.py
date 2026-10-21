"""Document ingestion and chunking."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


class MemoryError(ValueError):
    """Document ingestion or retrieval failure."""


@dataclass(frozen=True)
class Document:
    id: str
    source: str
    title: str
    text: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_text(cls, source: str, text: str, title: str | None = None) -> Document:
        digest = hashlib.sha256(
            f"{source}\x00{text}".encode()
        ).hexdigest()[:16]
        return cls(
            id=digest,
            source=source,
            title=title or source.rsplit("/", 1)[-1] or source,
            text=text,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> Document:
        p = Path(path)
        if not p.is_file():
            raise MemoryError(f"not a file: {p}")
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise MemoryError(f"not utf-8: {p}") from exc
        if not text.strip():
            raise MemoryError(f"empty file: {p}")
        return cls.from_text(str(p), text, title=p.name)


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    offset: int


def chunk_text(text: str, *, size: int = 400, overlap: int = 50) -> list[Chunk]:
    if size <= 0:
        raise MemoryError("chunk size must be > 0")
    if overlap < 0 or overlap >= size:
        raise MemoryError("overlap must be >= 0 and < size")
    if not text:
        return []
    chunks: list[Chunk] = []
    step = size - overlap
    i = 0
    idx = 0
    while i < len(text):
        end = min(i + size, len(text))
        chunks.append(Chunk(index=idx, text=text[i:end], offset=i))
        if end == len(text):
            break
        i += step
        idx += 1
    return chunks
