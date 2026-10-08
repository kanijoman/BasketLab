"""Fake FEB server: replays a recorded game as if it were being played live.

Serves what the real scraper consumes (match page with a JWT in a hidden input, and the
BoxScore / KeyFacts / ShotChart endpoints behind a Bearer token). Standard library only.

Run it for manual / app testing::

    python -m src.live_core.fake_feb --speed 30 --start-period 2 --port 8765
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from .clock import elapsed_seconds, period_and_remaining
from .events import parse_line
from .replay import ReplayClock, truncate_doc

_API_RE = re.compile(r"^/LiveStats\.API/api/v1/(BoxScore|KeyFacts|ShotChart)/(\d+)$")
_PAGE_RE = re.compile(r"^/partido/(\d+)$")


def game_end_elapsed(doc: Dict[str, Any]) -> int:
    events = [parse_line(line) for line in doc["PLAYBYPLAY"]["LINES"]]
    return max(e.elapsed for e in events if e is not None)


class FakeFebServer:
    def __init__(self, doc: Dict[str, Any], clock: ReplayClock, token: str = "eyJhbGciFAKE.replay.token",
                 host: str = "127.0.0.1", port: int = 0) -> None:
        self.doc, self.clock, self.token = doc, clock, token
        self._httpd = ThreadingHTTPServer((host, port), self._make_handler())
        self._thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def current_document(self) -> Dict[str, Any]:
        if self.clock.finished():
            return self.doc
        period, remaining = period_and_remaining(self.clock.elapsed())
        return truncate_doc(self.doc, period, remaining)

    def _make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output quiet
                pass

            def _send(self, status: int, body: str, content_type: str) -> None:
                data = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):  # noqa: N802
                if _PAGE_RE.match(self.path):
                    html = (f'<html><body><input type="hidden" id="token" '
                            f'value="{server.token}" /></body></html>')
                    return self._send(200, html, "text/html")
                match = _API_RE.match(self.path)
                if not match:
                    return self._send(404, "{}", "application/json")
                if self.headers.get("Authorization") != f"Bearer {server.token}":
                    return self._send(401, '{"error": "unauthorized"}', "application/json")

                doc = server.current_document()
                endpoint = match.group(1)
                payload = {"BoxScore": lambda: {k: v for k, v in doc.items() if k not in ("PLAYBYPLAY", "SHOTCHART")},
                           "KeyFacts": lambda: {"PLAYBYPLAY": doc["PLAYBYPLAY"]},
                           "ShotChart": lambda: {"SHOTCHART": doc.get("SHOTCHART") or []}}[endpoint]()
                self._send(200, json.dumps(payload), "application/json")

        return Handler


def main() -> None:  # pragma: no cover - manual tool
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Replay a recorded FEB game as a live feed.")
    parser.add_argument("--game", default=str(Path(__file__).resolve().parents[1] / "JSON_samples" / "feb_game.json"))
    parser.add_argument("--speed", type=float, default=30.0)
    parser.add_argument("--start-period", type=int, default=1)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    doc = json.loads(Path(args.game).read_text(encoding="utf-8"))
    clock = ReplayClock(elapsed_seconds(args.start_period, 600), args.speed, game_end_elapsed(doc), time.monotonic)
    server = FakeFebServer(doc, clock, port=args.port)
    print(f"Fake FEB replay on {server.base_url} (speed x{args.speed}); token: {server.token}")
    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":  # pragma: no cover
    main()
