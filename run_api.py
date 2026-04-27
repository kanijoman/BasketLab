"""Development entry point for the BasketLab FastAPI server.

Usage::

    python run_api.py

Or with hot-reload::

    uvicorn src.api.app:app --reload --port 8000
"""

import sys
import os

# Ensure 'src/' is on the path so internal absolute imports resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    dev_mode = os.environ.get("BASKETLAB_DEV", "0") == "1"
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=dev_mode,
        workers=1 if dev_mode else 4,
        log_level="info",
    )
