"""OpenAI-compatible chat-completions client, stdlib only."""

from __future__ import annotations

import contextlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

from ..core.errors import ProviderError
from .base import Completion, Message, Usage

# Cap planner output. Prevents runaway reasoning (6870-token
# responses at 52 tok/s = 132s, exceeding the client timeout).
MAX_TOKENS_DEFAULT = 6144

# Cloudflare (used by Groq and others) blocks default Python UAs.
_USER_AGENT = "agi-platform/0.1 (+https://github.com/)"


class OpenAICompatProvider:
    """Works with any server exposing POST {base_url}/chat/completions.

    Multi-key rotation: set ``AGI_API_KEYS`` to a comma-separated list of
    keys. On each request the client uses the next key from the pool; on a
    429 it rotates to the next key before sleeping. Keys from the same
    provider org share the TPM limit; keys from distinct orgs each get
    their own. Rotation is a client-side feature; whether it multiplies
    effective throughput depends on how the keys were provisioned.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key_env: str = "AGI_API_KEY",
        timeout_s: float = 240.0,
        max_retries: int = 2,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout_s = timeout_s
        self.max_retries = max_retries

        multi = os.environ.get("AGI_API_KEYS", "").strip()
        self._key_pool: list[str] = []
        if multi:
            for raw in multi.split(","):
                cleaned = raw.strip().strip("'\"").strip()
                if cleaned:
                    self._key_pool.append(cleaned)
        self._key_idx = 0

    # --- keys --------------------------------------------------------

    def _current_key(self) -> str | None:
        if self._key_pool:
            key = self._key_pool[self._key_idx % len(self._key_pool)]
        else:
            key = os.environ.get(self.api_key_env)
        if key is None:
            return None
        key = key.strip().strip("'\"").strip()
        return key or None

    def _rotate_key(self) -> None:
        if len(self._key_pool) > 1:
            self._key_idx = (self._key_idx + 1) % len(self._key_pool)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        key = self._current_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    # --- payload -----------------------------------------------------

    def _payload(
        self,
        messages: list[Message],
        *,
        stream: bool,
        max_tokens: int | None,
        temperature: float | None,
    ) -> bytes:
        payload: dict = {
            "model": self.model,
            "messages": [m.as_dict() for m in messages],
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        return json.dumps(payload).encode("utf-8")

    def _open(self, body: bytes) -> urllib.response.addinfourl:
        url = f"{self.base_url}/chat/completions"
        request = urllib.request.Request(
            url, data=body, headers=self._headers(), method="POST"
        )
        return urllib.request.urlopen(request, timeout=self.timeout_s)

    # --- HTTP core ---------------------------------------------------

    def _read_error_body(self, exc: urllib.error.HTTPError) -> str:
        text = ""
        with contextlib.suppress(Exception):
            text = exc.read().decode("utf-8", "replace")[:600]
        return text or str(exc.reason)

    def _post(self, body: bytes) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with self._open(body) as response:
                    return response.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                text = self._read_error_body(exc)
                last_error = ProviderError(f"client error {exc.code}: {text}")
                if exc.code == 429:
                    if len(self._key_pool) > 1:
                        self._rotate_key()
                        if attempt < self.max_retries:
                            time.sleep(0.1)
                            continue
                    retry_after = 0.0
                    with contextlib.suppress(Exception):
                        raw = (
                            exc.headers.get("Retry-After")
                            or exc.headers.get("retry-after")
                        )
                        if raw:
                            retry_after = float(raw)
                    if retry_after <= 0:
                        retry_after = min(30.0, 2.0 * (2 ** attempt))
                    if attempt < self.max_retries:
                        time.sleep(retry_after)
                        continue
                    break
                if 400 <= exc.code < 500:
                    break
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8) * 0.1)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = ProviderError(f"transport error: {exc}")
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8) * 0.1)
        raise ProviderError(
            f"request failed after {self.max_retries + 1} attempt(s): {last_error}"
        )

    # --- public API --------------------------------------------------

    def _complete_once(
        self,
        messages: list[Message],
        *,
        max_tokens: int | None,
        temperature: float | None,
    ) -> Completion:
        body = self._payload(
            messages,
            stream=False,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = self._post(body)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"invalid JSON from upstream: {text[:300]}"
            ) from exc
        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
            if not content:
                content = (
                    message.get("reasoning_content")
                    or message.get("reasoning")
                    or ""
                )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected response shape: {data!r}") from exc
        usage_raw = data.get("usage") or {}
        return Completion(
            text=content,
            model=data.get("model", self.model),
            usage=Usage(
                prompt_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
            ),
            finish_reason=choice.get("finish_reason"),
            raw=data,
        )

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int | None = MAX_TOKENS_DEFAULT,
        temperature: float | None = None,
    ) -> Completion:
        completion = self._complete_once(
            messages, max_tokens=max_tokens, temperature=temperature,
        )
        # Detect reasoning-starvation: model burned the whole budget on CoT
        # and never emitted structured output. Retry with a hard nudge.
        if (
            completion.finish_reason == "length"
            and "{" not in completion.text
            and len(messages) < 100
        ):
            nudge = Message(
                role="system",
                content=(
                    "STOP. Your prior response used the entire output budget "
                    "on reasoning without producing the final answer. Now "
                    "respond with a COMPLETE JSON object that includes every "
                    "field the original request specified. Do NOT output an "
                    "empty object {} or a placeholder — output the actual "
                    "data. No prose, no reasoning, just the complete JSON."
                ),
            )
            retried = self._complete_once(
                messages + [nudge],
                max_tokens=max_tokens,
                temperature=0.0,
            )
            if "{" in retried.text or retried.finish_reason != "length":
                return retried
            # Both attempts starved — return the retry so caller sees the error
            return retried
        return completion

    def stream(
        self,
        messages: list[Message],
        *,
        max_tokens: int | None = MAX_TOKENS_DEFAULT,
        temperature: float | None = None,
    ) -> Iterator[str]:
        body = self._payload(
            messages,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            response = self._open(body)
        except urllib.error.HTTPError as exc:
            text = self._read_error_body(exc)
            raise ProviderError(f"stream error {exc.code}: {text}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"stream transport error: {exc}") from exc

        try:
            for raw_line in response:
                line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
                if not line:
                    continue
                if line.startswith("data: "):
                    line = line[len("data: "):]
                if line == "[DONE]":
                    return
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                piece = delta.get("content")
                # Reasoning models stream thinking in a sibling field.
                if not piece:
                    piece = (
                        delta.get("reasoning_content")
                        or delta.get("reasoning")
                    )
                if piece:
                    yield piece
        finally:
            response.close()

    def health(self) -> dict:
        url = f"{self.base_url}/models"
        request = urllib.request.Request(
            url, headers=self._headers(), method="GET"
        )
        try:
            with urllib.request.urlopen(request, timeout=5.0) as response:
                return {
                    "ok": response.status < 400,
                    "provider": self.name,
                    "status": response.status,
                    "model": self.model,
                }
        except urllib.error.HTTPError as exc:
            return {
                "ok": False,
                "provider": self.name,
                "status": exc.code,
                "error": str(exc.reason),
                "model": self.model,
            }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {
                "ok": False,
                "provider": self.name,
                "error": str(exc),
                "model": self.model,
            }
