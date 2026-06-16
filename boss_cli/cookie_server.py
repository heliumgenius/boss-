"""Minimal HTTP server to receive cookies from Edge Extension.

Usage:
    python -m boss_cli.cookie_server
    # Then load extension/ in edge://extensions
"""

from __future__ import annotations

import json
import logging
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from .keychain import save_credential_data

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
PORT = 9876

_last_cookies: dict[str, str] = {}
_last_sync: float = 0


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/cookies":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            cookies = data.get("cookies", {})
        except (json.JSONDecodeError, TypeError):
            self.send_response(400)
            self.end_headers()
            return

        global _last_cookies, _last_sync
        _last_cookies = cookies
        _last_sync = time.time()

        payload = {"cookies": cookies, "saved_at": _last_sync}
        save_credential_data(payload)
        logger.info("Received %d cookies from extension", len(cookies))

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def do_GET(self):
        global _last_cookies, _last_sync
        if self.path == "/status":
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "running": True,
                "last_sync": _last_sync,
                "cookies": _last_cookies,
            }).encode())
        elif self.path == "/shutdown":
            self.send_response(200)
            self.end_headers()
            import threading
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.debug(format, *args)


def run_server(host=HOST, port=PORT, daemon=False):
    if daemon:
        import subprocess
        proc = subprocess.Popen(
            [sys.executable, "-m", "boss_cli.cookie_server", "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"[*] Cookie server started on http://{host}:{port} (PID {proc.pid})")
        return proc
    server = HTTPServer((host, port), Handler)
    print(f"[*] Cookie server listening on http://{host}:{port}")
    print(f"[*] Credential file: {Path.home() / '.config' / 'boss-cli' / 'credential.json'}")
    print("[*] Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopping")
        server.server_close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_server(port=args.port)


if __name__ == "__main__":
    main()
