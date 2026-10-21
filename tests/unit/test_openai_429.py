from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agi.providers import Message, OpenAICompatProvider


class _Flaky(BaseHTTPRequestHandler):
    hits = 0
    fail_for = 1
    retry_after = "0"

    def log_message(self, *_): pass

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(n)
        _Flaky.hits += 1
        if _Flaky.hits <= _Flaky.fail_for:
            self.send_response(429)
            self.send_header("Retry-After", _Flaky.retry_after)
            self.end_headers()
            self.wfile.write(b'{"error":"rate limited"}')
            return
        body = json.dumps({
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def server():
    _Flaky.hits = 0
    _Flaky.fail_for = 1
    _Flaky.retry_after = "0"
    httpd = HTTPServer(("127.0.0.1", 0), _Flaky)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_429_retried(server: str) -> None:
    p = OpenAICompatProvider(
        name="stub", base_url=server, model="m", max_retries=2,
    )
    c = p.complete([Message(role="user", content="hi")])
    assert c.text == "ok"
    assert _Flaky.hits == 2


def test_429_exhausted_raises(server: str) -> None:
    _Flaky.fail_for = 10
    p = OpenAICompatProvider(
        name="stub", base_url=server, model="m", max_retries=0,
    )
    from agi.core.errors import ProviderError
    with pytest.raises(ProviderError):
        p.complete([Message(role="user", content="hi")])
