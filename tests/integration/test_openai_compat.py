from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import pytest

from agi.core.errors import ProviderError
from agi.providers import Message, OpenAICompatProvider


class _Handler(BaseHTTPRequestHandler):
    ok = True
    captured: ClassVar[dict] = {}

    def log_message(self, *_args) -> None:  # silence
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        _Handler.captured = {"path": self.path, "body": json.loads(body)}
        if not _Handler.ok:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"server down")
            return
        reply = {
            "model": "stub-model",
            "choices": [
                {"message": {"content": "hello from stub"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4},
        }
        payload = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")


@pytest.fixture()
def stub_server():
    _Handler.ok = True
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_complete_ok(stub_server: str) -> None:
    p = OpenAICompatProvider(
        name="stub", base_url=stub_server, model="stub-model", max_retries=0
    )
    completion = p.complete([Message(role="user", content="hi")])
    assert completion.text == "hello from stub"
    assert completion.usage.total_tokens == 7
    assert _Handler.captured["path"].endswith("/chat/completions")


def test_5xx_raises(stub_server: str) -> None:
    _Handler.ok = False
    p = OpenAICompatProvider(
        name="stub", base_url=stub_server, model="stub-model", max_retries=0
    )
    with pytest.raises(ProviderError):
        p.complete([Message(role="user", content="hi")])


def test_health_ok(stub_server: str) -> None:
    p = OpenAICompatProvider(
        name="stub", base_url=stub_server, model="stub-model", max_retries=0
    )
    h = p.health()
    assert h["ok"] is True
