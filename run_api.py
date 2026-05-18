"""Development entry point for the BasketLab FastAPI server.

Usage::

    python run_api.py

Or with hot-reload::

    uvicorn src.api.app:app --reload --port 8000
"""

import sys
import os
import socket as _socket

# Ensure 'src/' is on the path so internal absolute imports resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ── Windows ghost-socket workaround ─────────────────────────────────────────
# On Windows, killing a uvicorn process sometimes leaves LISTEN sockets in a
# ghost state (owning PID no longer exists but socket still shown in netstat).
# Monkey-patching socket.socket to always set SO_REUSEADDR forces the kernel
# to allow re-binding to such a port.
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

import uvicorn  # noqa: E402 (import after path + patch)


if __name__ == "__main__":
    dev_mode = os.environ.get("BASKETLAB_DEV", "0") == "1"
    # Render (and most PaaS) inject PORT dynamically; fall back to 8000 locally.
    port = int(os.environ.get("PORT", 8000))
    # Windows does not support uvicorn's multiprocessing socket sharing
    # (WinError 10022 on sock.listen).  Always use a single worker.
    _workers = 1 if sys.platform == "win32" else (1 if dev_mode else 4)
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=dev_mode,
        workers=_workers if not dev_mode else None,
        log_level="info",
    )
