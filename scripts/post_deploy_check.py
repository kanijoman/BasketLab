"""Post-deploy check of the API on Render (issue #111).

``python scripts/post_deploy_check.py --sha <commit>`` (URL from ``RENDER_API_URL``) waits until
``GET /api/v1/health`` reports the pushed commit (the deploy hook is asynchronous, so the previous version
keeps answering for a while and the free plan also needs a cold start), then requires
``GET /api/v1/health/db`` to be connected. Exit 0 = healthy or not configured (skipped), 1 = failed.
Standard library only: it runs in CI without installing anything.

Render's free plan sometimes takes 20-25 min to deploy a commit (5 min is usual), so the wait is long (issue #269).
If the API serves a NEWER commit that contains the one being checked (a later merge deployed first), the check
passes with a note: ``github_superseded`` asks GitHub's compare API (``GITHUB_REPOSITORY`` / ``GITHUB_TOKEN``).
A real failure (the old version still serving after the whole wait, or the database down) still fails.
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

TIMEOUT_S = 40 * 60
INTERVAL_S = 15


@dataclass
class Result:
    ok: bool
    message: str


def http_get_json(url: str, headers: Optional[dict] = None) -> Any:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https URL from our own config
        return json.loads(response.read().decode("utf-8"))


def github_superseded(repo: str, token: str, get_json: Callable[..., Any] = http_get_json) -> Callable[[str, str], bool]:
    """``(sha, served) -> True`` when the served commit contains ``sha`` (GitHub's compare ``sha...served``).

    Any failure (no network, rate limit, unknown commit) is "no": the check then keeps waiting as before.
    """
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "basketlab-post-deploy-check"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def superseded(sha: str, served: str) -> bool:
        try:
            status = get_json(f"https://api.github.com/repos/{repo}/compare/{sha}...{served}", headers=headers).get("status")
        except Exception:  # noqa: BLE001
            return False
        return status in ("ahead", "identical")

    return superseded


def _short(sha: Optional[str]) -> str:
    return (sha or "none")[:7]


def _is_newer(superseded: Callable[[str, str], bool], sha: str, served: str) -> bool:
    try:
        return bool(superseded(sha, served))
    except Exception:  # noqa: BLE001 - a failing comparison is not a reason to fail the check
        return False


def wait_for_deploy(base_url: str, sha: str, get_json: Callable[[str], Any] = http_get_json,
                    sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                    timeout: float = TIMEOUT_S, interval: float = INTERVAL_S,
                    superseded: Optional[Callable[[str, str], bool]] = None) -> Result:
    started, serving, newer = clock(), None, False
    while True:
        try:
            serving = get_json(f"{base_url}/api/v1/health").get("commit")
            if serving == sha:
                break
            if serving and superseded is not None and _is_newer(superseded, sha, serving):
                newer = True
                break
        except Exception:  # noqa: BLE001 - cold start / redeploy in progress: keep waiting
            pass
        if clock() - started >= timeout:
            return Result(False, f"The API still serves {_short(serving)} instead of {_short(sha)} after {int(timeout)} s: "
                                 "check the deploy of basketlab-api in the Render dashboard (build failed or still queued?)")
        sleep(interval)
    try:
        db = get_json(f"{base_url}/api/v1/health/db")
    except Exception as exc:  # noqa: BLE001 - the endpoint answers 503 when the database is down
        return Result(False, f"/health/db failed after the deploy of {_short(sha)}: {type(exc).__name__}: {exc}")
    if not db.get("connected"):
        return Result(False, f"Database not connected after the deploy: {db.get('error')} ({db.get('hint')})")
    if newer:
        return Result(True, f"{_short(sha)} was superseded by a newer deploy ({_short(serving)}); "
                            f"database connected ({db.get('collections')} collections)")
    return Result(True, f"{_short(sha)} deployed, database connected ({db.get('collections')} collections)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Wait for the Render deploy and check the database")
    parser.add_argument("--sha", required=True, help="commit that was pushed (GITHUB_SHA)")
    args = parser.parse_args(argv)
    url = (os.environ.get("RENDER_API_URL") or "").strip().rstrip("/")
    if not url:
        print("RENDER_API_URL is not set: skipping the post-deploy check")
        return 0
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    superseded = github_superseded(repo, os.environ.get("GITHUB_TOKEN", "")) if repo else None
    result = wait_for_deploy(url, args.sha, superseded=superseded)
    print(result.message)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
