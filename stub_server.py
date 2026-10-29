#!/usr/bin/env python3
"""Local server for family D. Serves per-path JSON at localhost:8088."""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

RESPONSES = {
    "/status.json": {"ok": True, "uptime_s": 12345},
    "/version":     {"version": "1.4.2", "build": "abc123"},
    "/summary":     {"rows": 17, "top": "alpha"},
    "/health":      {"status": "healthy"},
    "/counts":      {"users": 42, "sessions": 91},
}

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = RESPONSES.get(self.path)
        if body is None:
            self.send_response(404); self.end_headers(); return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *a): pass

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8088), H).serve_forever()
