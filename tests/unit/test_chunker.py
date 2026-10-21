from __future__ import annotations

from agi.memory import MemoryError, chunk_text


def test_empty() -> None:
    assert chunk_text("") == []


def test_short_text_single_chunk() -> None:
    chunks = chunk_text("hello world", size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"
    assert chunks[0].offset == 0


def test_overlap_and_offsets() -> None:
    text = "a" * 1000
    chunks = chunk_text(text, size=400, overlap=50)
    assert chunks[0].offset == 0
    assert chunks[0].text == "a" * 400
    assert chunks[1].offset == 350
    assert chunks[-1].offset + len(chunks[-1].text) == 1000


def test_bad_params() -> None:
    for kwargs in ({"size": 0}, {"size": 10, "overlap": -1}, {"size": 10, "overlap": 10}):
        try:
            chunk_text("abc", **kwargs)
        except MemoryError:
            continue
        raise AssertionError(f"should reject {kwargs}")
