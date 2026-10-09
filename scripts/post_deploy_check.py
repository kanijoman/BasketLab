"""Post-deploy check of the API on Render (issue #111).

``python scripts/post_deploy_check.py --sha <commit>`` (URL from ``RENDER_API_URL``) waits until
``GET /api/v1/health`` reports the pushed commit (the deploy hook is asynchronous, so the previous version
keeps answering for a while and the free plan also needs a cold start), then requires
``GET /api/v1/health/db`` to be connected. Exit 0 = healthy or not configured (skipped), 1 = failed.
Standard library only: it runs in CI without installing anything.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

TIMEOUT_S = 15 * 60
INTERVAL_S = 15


@dataclass
class Result:
    ok: bool
    message: str


def http_get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https URL from our own config
        return json.loads(response.read().decode("utf-8"))


def _short(sha: Optional[str]) -> str:
    return (sha or "none")[:7]


def wait_for_deploy(base_url: str, sha: str, get_json: Callable[[str], Any] = http_get_json,
                    sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                    timeout: float = TIMEOUT_S, interval: float = INTERVAL_S) -> Result:
    started, serving = clock(), None
    while True:
        try:
            serving = get_json(f"{base_url}/api/v1/health").get("commit")
            if serving == sha:
                break
        except Exception:  # noqa: BLE001 - cold start / redeploy in progress: keep waiting
            pass
        if clock() - started >= timeout:
            return Result(False, f"The API still serves {_short(serving)} instead of {_short(sha)} after {int(timeout)} s")
        sleep(interval)
    try:
        db = get_json(f"{base_url}/api/v1/health/db")
    except Exception as exc:  # noqa: BLE001 - the endpoint answers 503 when the database is down
        return Result(False, f"/health/db failed after the deploy of {_short(sha)}: {type(exc).__name__}: {exc}")
    if not db.get("connected"):
        return Result(False, f"Database not connected after the deploy: {db.get('error')} ({db.get('hint')})")
    return Result(True, f"{_short(sha)} deployed, database connected ({db.get('collections')} collections)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Wait for the Render deploy and check the database")
    parser.add_argument("--sha", required=True, help="commit that was pushed (GITHUB_SHA)")
    args = parser.parse_args(argv)
    url = (os.environ.get("RENDER_API_URL") or "").strip().rstrip("/")
    if not url:
        print("RENDER_API_URL is not set: skipping the post-deploy check")
        return 0
    result = wait_for_deploy(url, args.sha)
    print(result.message)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
