from __future__ import annotations

import pytest

from agi.providers.openai_compat import OpenAICompatProvider


def _make_provider(
    monkeypatch: pytest.MonkeyPatch,
    keys_csv: str | None = None,
    fallback: str | None = None,
) -> OpenAICompatProvider:
    """Build a provider with explicit env, hermetic to the shell."""
    monkeypatch.delenv("AGI_API_KEYS", raising=False)
    if keys_csv is not None:
        monkeypatch.setenv("AGI_API_KEYS", keys_csv)
    if fallback is not None:
        monkeypatch.setenv("MY_KEY", fallback)
    else:
        monkeypatch.delenv("MY_KEY", raising=False)
    return OpenAICompatProvider(
        name="t", base_url="http://127.0.0.1:1/v1",
        model="m", api_key_env="MY_KEY", max_retries=0,
    )


def test_single_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_provider(monkeypatch, fallback="k1")
    assert p._current_key() == "k1"


def test_pool_from_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_provider(monkeypatch, keys_csv="k1,k2,k3")
    assert p._key_pool == ["k1", "k2", "k3"]
    assert p._current_key() == "k1"


def test_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_provider(monkeypatch, keys_csv="k1,k2,k3")
    assert p._current_key() == "k1"
    p._rotate_key()
    assert p._current_key() == "k2"
    p._rotate_key()
    assert p._current_key() == "k3"
    p._rotate_key()
    assert p._current_key() == "k1"


def test_pool_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_provider(monkeypatch, keys_csv="a,b", fallback="single")
    assert p._current_key() == "a"


def test_rotate_noop_on_single_key(monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_provider(monkeypatch, fallback="only")
    p._rotate_key()
    assert p._current_key() == "only"


def test_headers_strip_single_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_provider(monkeypatch, keys_csv="'gsk_quoted','gsk_quoted2'")
    assert p._headers()["Authorization"] == "Bearer gsk_quoted"


def test_headers_strip_double_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_provider(monkeypatch, keys_csv='"a","b"')
    assert p._headers()["Authorization"] == "Bearer a"
