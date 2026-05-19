"""Entry point for the BasketLab scraper service.

Starts a minimal FastAPI app with ONLY scrape + collections routers.
Heavy ML libraries (sklearn / scipy / numpy / pandas) are never imported
in this process, saving ~200 MB vs the full analytics app.

Usage
-----
    python run_scraper.py

Or with hot-reload::

    BASKETLAB_DEV=1 python run_scraper.py
"""
import sys
import os
import socket as _socket

# Ensure 'src/' is on the path so internal absolute imports resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ── Windows ghost-socket workaround (same as run_api.py) ────────────────────
if sys.platform == "win32":
    _OrigSocket = _socket.socket

    class _ReuseAddrSocket(_OrigSocket):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            try:
                self.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            except OSError:
                pass

    _socket.socket = _ReuseAddrSocket  # type: ignore[misc]
# ─────────────────────────────────────────────────────────────────────────────

import uvicorn  # noqa: E402

if __name__ == "__main__":
    dev_mode = os.environ.get("BASKETLAB_DEV", "0") == "1"
    # Render injects PORT dynamically; fall back to 8001 locally
    # (8000 is reserved for the main analytics app in local dev).
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(
        "src.api.scraper_app:app",
        host="0.0.0.0",
        port=port,
        reload=dev_mode,
        workers=None if dev_mode else 1,
        log_level="info",
    )
