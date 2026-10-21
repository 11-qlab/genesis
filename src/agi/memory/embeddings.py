"""Embedding providers. Two implementations, both plug-and-play."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

from .documents import MemoryError


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


class HashEmbedding:
    """Deterministic hash-based embedding. Offline, fast, good for tests.

    Tokenizes text into whitespace-free word shingles, hashes each to a bucket
    in [0, dim), sums counts, L2-normalizes. Similar texts land near each other
    because they share words; it is not semantically meaningful, but it gives
    the retriever real signal and needs no network.
    """

    name = "hash"

    def __init__(self, dim: int = 256) -> None:
        if np is None:
            raise MemoryError("numpy is required for HashEmbedding")
        if dim <= 0:
            raise MemoryError("dim must be > 0")
        self.dim = dim

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in text.lower().split():
            token = token.strip(".,;:!?()[]{}'\"`")
            if not token:
                continue
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest, "big") % self.dim
            vec[bucket] += 1.0
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._vector(t) for t in texts])


class OpenAICompatEmbedding:
    """Calls POST {base_url}/embeddings. Works with DeepSeek, OpenAI, local servers."""

    name = "openai_compat"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key_env: str = "AGI_API_KEY",
        dim: int = 1536,
        timeout_s: float = 30.0,
    ) -> None:
        if np is None:
            raise MemoryError("numpy is required for OpenAICompatEmbedding")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.dim = dim
        self.timeout_s = timeout_s

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "agi-platform/0.1 (+https://github.com/)",
        }
        key = os.environ.get(self.api_key_env)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        body = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise MemoryError(f"embeddings http error: {exc.code} {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise MemoryError(f"embeddings transport error: {exc}") from exc
        try:
            data = payload["data"]
            vectors = [row["embedding"] for row in data]
        except (KeyError, TypeError) as exc:
            raise MemoryError(f"unexpected embeddings response: {payload!r}") from exc
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.shape[0] != len(texts):
            raise MemoryError(
                f"expected {len(texts)} vectors, got {arr.shape[0]}"
            )
        return arr


def build_embedding(kind: str, dim: int = 256, **kwargs: object) -> EmbeddingProvider:
    if kind == "hash":
        return HashEmbedding(dim=dim)
    if kind == "openai_compat":
        return OpenAICompatEmbedding(dim=dim, **kwargs)  # type: ignore[arg-type]
    raise MemoryError(f"unknown embedding kind: {kind!r}")
