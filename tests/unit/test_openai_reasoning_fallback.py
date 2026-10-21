from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agi.providers import Message, OpenAICompatProvider


class _ReasoningResponse(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(n)
        body = json.dumps({
            "model": "reasoner",
            "choices": [{
                "message": {
                    "content": "",
                    "reasoning_content": "the answer is ok",
                },
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _ReasoningResponse)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_reasoning_content_fallback(server: str) -> None:
    p = OpenAICompatProvider(name="stub", base_url=server, model="reasoner",
                             max_retries=0)
    completion = p.complete([Message(role="user", content="hi")])
    assert completion.text == "the answer is ok"
