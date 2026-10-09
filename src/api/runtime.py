"""Process settings for the API server."""
from typing import Mapping, Optional

# Each worker imports the whole app (~170 MB at idle): more than a couple does not fit the
# 512 MB of Render's free plan.
MAX_WORKERS = 4


def uvicorn_workers(env: Mapping[str, str], platform: str, dev_mode: bool) -> Optional[int]:
    """Number of uvicorn workers (None in dev mode, where reload is used instead).

    Defaults to ONE worker; ``WEB_CONCURRENCY`` raises it (capped at ``MAX_WORKERS``).
    Windows does not support uvicorn's multiprocessing socket sharing.
    """
    if dev_mode:
        return None
    if platform == "win32":
        return 1
    raw = str(env.get("WEB_CONCURRENCY", "")).strip()
    if not raw.isdigit() or int(raw) < 1:
        return 1
    return min(int(raw), MAX_WORKERS)
