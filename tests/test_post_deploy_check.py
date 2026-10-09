"""Post-deploy check (issue #111): wait until the API serves the pushed commit, then require a healthy database."""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "post_deploy_check.py"
spec = importlib.util.spec_from_file_location("post_deploy_check", SCRIPT)
check = importlib.util.module_from_spec(spec)
sys.modules["post_deploy_check"] = check  # dataclasses resolves its module by name
spec.loader.exec_module(check)

SHA = "a" * 40
URL = "https://api.example"


class Fake:
    """Scripted ``get_json(url)``: answers per path, in order; an Exception item is raised."""

    def __init__(self, live, db):
        self.live, self.db, self.calls = list(live), list(db), []

    def __call__(self, url):
        self.calls.append(url)
        queue = self.db if url.endswith("/health/db") else self.live
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item


def run(fake, timeout=60):
    ticks = {"t": 0.0}

    def sleep(seconds):
        ticks["t"] += seconds

    return check.wait_for_deploy(URL, SHA, get_json=fake, sleep=sleep, clock=lambda: ticks["t"], timeout=timeout, interval=10)


def test_passes_once_the_new_commit_is_served_and_the_database_is_connected():
    fake = Fake(live=[{"status": "ok", "commit": SHA}], db=[{"connected": True, "collections": 2}])
    assert run(fake).ok is True


def test_keeps_waiting_while_the_old_version_is_still_serving():
    fake = Fake(live=[{"status": "ok", "commit": "b" * 40}, {"status": "ok", "commit": "b" * 40}, {"status": "ok", "commit": SHA}],
                db=[{"connected": True}])
    result = run(fake)
    assert result.ok is True
    assert sum(u.endswith("/api/v1/health") for u in fake.calls) == 3


def test_survives_the_cold_start_of_the_free_plan():
    fake = Fake(live=[ConnectionError("boom"), TimeoutError("slow"), {"status": "ok", "commit": SHA}], db=[{"connected": True}])
    assert run(fake).ok is True


def test_fails_when_the_new_commit_never_shows_up():
    fake = Fake(live=[{"status": "ok", "commit": "b" * 40}], db=[{"connected": True}])
    result = run(fake, timeout=30)
    assert result.ok is False and "b" * 7 in result.message and SHA[:7] in result.message


def test_fails_when_the_database_is_not_connected():
    fake = Fake(live=[{"status": "ok", "commit": SHA}], db=[{"connected": False, "error": "auth_failed"}])
    result = run(fake)
    assert result.ok is False and "auth_failed" in result.message


def test_a_database_endpoint_error_is_a_failure_not_a_crash():
    fake = Fake(live=[{"status": "ok", "commit": SHA}], db=[ConnectionError("503")])
    assert run(fake).ok is False


def test_main_skips_with_exit_0_when_no_url_is_configured(monkeypatch, capsys):
    monkeypatch.delenv("RENDER_API_URL", raising=False)
    assert check.main(["--sha", SHA]) == 0
    assert "skipping" in capsys.readouterr().out.lower()


def test_main_normalises_the_url(monkeypatch):
    seen = {}

    def fake_wait(url, sha, **kw):
        seen["url"] = url
        return check.Result(True, "ok")

    monkeypatch.setattr(check, "wait_for_deploy", fake_wait)
    monkeypatch.setenv("RENDER_API_URL", URL + "/")
    assert check.main(["--sha", SHA]) == 0
    assert seen["url"] == URL
