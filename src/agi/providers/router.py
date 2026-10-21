"""Provider construction and dispatch."""

from __future__ import annotations

from ..core.config import ProviderConfig
from ..core.errors import ProviderError
from .base import Completion, Message, Provider
from .echo import EchoProvider
from .openai_compat import OpenAICompatProvider


def build_provider(cfg: ProviderConfig) -> Provider:
    if cfg.kind == "echo":
        return EchoProvider()
    if cfg.kind == "openai_compat":
        return OpenAICompatProvider(
            name=cfg.name,
            base_url=cfg.base_url,
            model=cfg.model,
            api_key_env=cfg.api_key_env,
            timeout_s=cfg.timeout_s,
            max_retries=cfg.max_retries,
        )
    raise ProviderError(f"unsupported provider kind: {cfg.kind!r}")


class ProviderRouter:
    """Holds providers by name and forwards calls to one of them."""

    def __init__(self, default: Provider | None = None) -> None:
        self._providers: dict[str, Provider] = {}
        self.default_name: str | None = default.name if default else None
        if default is not None:
            self._providers[default.name] = default

    def register(self, provider: Provider, *, default: bool = False) -> None:
        self._providers[provider.name] = provider
        if default or self.default_name is None:
            self.default_name = provider.name

    def get(self, name: str | None = None) -> Provider:
        key = name or self.default_name
        if key is None:
            raise ProviderError("no provider registered")
        if key not in self._providers:
            raise ProviderError(f"provider not registered: {key}")
        return self._providers[key]

    def names(self) -> list[str]:
        return sorted(self._providers)

    def complete(
        self,
        messages: list[Message],
        *,
        provider: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Completion:
        return self.get(provider).complete(
            messages, max_tokens=max_tokens, temperature=temperature
        )

    def health(self) -> list[dict]:
        return [provider.health() for provider in self._providers.values()]
