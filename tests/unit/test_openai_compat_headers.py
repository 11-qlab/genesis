from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import pytest

from agi.providers import Message, OpenAICompatProvider


class _Capture(BaseHTTPRequestHandler):
    last_headers: ClassVar[dict] = {}

    def log_message(self, *_args) -> None:
        pass

    def do_GET(self) -> None:
        _Capture.last_headers = dict(self.headers)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"data":[]}')

    def do_POST(self) -> None:
        _Capture.last_headers = dict(self.headers)
        n = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(n)
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
    _Capture.last_headers = {}
    httpd = HTTPServer(("127.0.0.1", 0), _Capture)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_user_agent_sent(server: str) -> None:
    p = OpenAICompatProvider(
        name="stub", base_url=server, model="m",
        api_key_env="AGI_TEST_KEY_XYZ", max_retries=0,
    )
    p.complete([Message(role="user", content="hi")])
    ua = _Capture.last_headers.get("User-Agent", "")
    assert "agi-platform" in ua.lower()


def test_authorization_sent_when_key_set(
    server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGI_TEST_KEY_XYZ", "secret-123")
    p = OpenAICompatProvider(
        name="stub", base_url=server, model="m",
        api_key_env="AGI_TEST_KEY_XYZ", max_retries=0,
    )
    p.complete([Message(role="user", content="hi")])
    assert _Capture.last_headers.get("Authorization") == "Bearer secret-123"
