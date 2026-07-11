"""Tests for the web application."""

import json
from unittest.mock import patch

from src.app import AppHandler


class MockRequestHandler:
    """Helper to simulate HTTP requests."""

    def __init__(self, path):
        self.path = path
        self.response_code = None
        self.response_headers = {}
        self.response_body = b""

    def send_response(self, code):
        self.response_code = code

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass

    def wfile_write(self, data):
        self.response_body += data


def test_health_endpoint():
    """Test that /health returns 200 with healthy status."""
    handler = AppHandler.__new__(AppHandler)
    handler.path = "/health"
    handler.send_response = lambda code: setattr(handler, "_code", code)
    handler.send_header = lambda k, v: None
    handler.end_headers = lambda: None
    handler.wfile = type("WFile", (), {"write": lambda self, d: setattr(handler, "_body", d)})()
    handler._body = b""

    handler.do_GET()

    assert handler._code == 200
    body = json.loads(handler._body)
    assert body == {"status": "healthy"}


def test_unknown_endpoint():
    """Test that unknown paths return 404."""
    handler = AppHandler.__new__(AppHandler)
    handler.path = "/unknown"
    handler.send_response = lambda code: setattr(handler, "_code", code)
    handler.send_header = lambda k, v: None
    handler.end_headers = lambda: None
    handler.wfile = type("WFile", (), {"write": lambda self, d: setattr(handler, "_body", d)})()
    handler._body = b""

    handler.do_GET()

    assert handler._code == 404
    body = json.loads(handler._body)
    assert body == {"error": "Not found"}
