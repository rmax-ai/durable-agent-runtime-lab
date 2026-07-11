"""Minimal web application."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class AppHandler(BaseHTTPRequestHandler):
    """Request handler for the web app."""

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def log_message(self, format, *args):
        """Suppress default logging for test output clarity."""
        pass


def run_server(host="0.0.0.0", port=8000):
    """Run the HTTP server."""
    server = HTTPServer((host, port), AppHandler)
    print(f"Starting server on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    run_server()
