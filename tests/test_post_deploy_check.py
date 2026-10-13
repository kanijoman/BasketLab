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


# --- slow Render deploys and newer commits (issue #269) ------------------------------------

def test_the_wait_covers_the_slowest_render_deploy_seen_regression():
    """Render's free plan took 20-25 min to deploy a commit that normally takes 5; a 15 min wait turned main red."""
    assert check.TIMEOUT_S >= 40 * 60


def test_a_newer_commit_that_contains_ours_counts_as_deployed_regression():
    """Bug #269: the API served a LATER commit (a newer merge deployed first) and the run of ours failed."""
    newer = "c" * 40
    fake = Fake(live=[{"status": "ok", "commit": newer}], db=[{"connected": True, "collections": 3}])
    seen = []

    def superseded(sha, served):
        seen.append((sha, served))
        return True

    ticks = {"t": 0.0}
    result = check.wait_for_deploy(URL, SHA, get_json=fake, sleep=lambda s: ticks.update(t=ticks["t"] + s),
                                   clock=lambda: ticks["t"], timeout=60, interval=10, superseded=superseded)
    assert result.ok is True and "newer" in result.message and newer[:7] in result.message
    assert seen == [(SHA, newer)]
    assert any(u.endswith("/health/db") for u in fake.calls), "the database must still be healthy"


def test_an_older_or_unrelated_commit_keeps_the_wait_going():
    fake = Fake(live=[{"status": "ok", "commit": "b" * 40}], db=[{"connected": True}])
    ticks = {"t": 0.0}
    result = check.wait_for_deploy(URL, SHA, get_json=fake, sleep=lambda s: ticks.update(t=ticks["t"] + s),
                                   clock=lambda: ticks["t"], timeout=30, interval=10, superseded=lambda sha, served: False)
    assert result.ok is False and "Render" in result.message


def test_the_commit_served_is_not_compared_with_itself_and_a_failing_comparison_is_not_a_crash():
    calls = []

    def exploding(sha, served):
        calls.append(served)
        raise RuntimeError("rate limited")

    fake = Fake(live=[{"status": "ok", "commit": "b" * 40}, {"status": "ok", "commit": SHA}], db=[{"connected": True}])
    ticks = {"t": 0.0}
    result = check.wait_for_deploy(URL, SHA, get_json=fake, sleep=lambda s: ticks.update(t=ticks["t"] + s),
                                   clock=lambda: ticks["t"], timeout=60, interval=10, superseded=exploding)
    assert result.ok is True and calls == ["b" * 40]   # asked once about the old one, never about our own commit


def test_the_comparison_with_github_says_whether_the_served_commit_contains_ours():
    asked = []

    def answer(status):
        def get(url, headers=None):
            asked.append((url, headers))
            return {"status": status}
        return get

    for status, expected in (("ahead", True), ("identical", True), ("behind", False), ("diverged", False)):
        asked.clear()
        is_newer = check.github_superseded("owner/repo", "tok", get_json=answer(status))
        assert is_newer(SHA, "b" * 40) is expected
        assert asked[0][0] == f"https://api.github.com/repos/owner/repo/compare/{SHA}...{'b' * 40}"
        assert asked[0][1]["Authorization"] == "Bearer tok"


def test_a_comparison_that_cannot_be_made_is_simply_not_a_yes():
    def broken(url, headers=None):
        raise ConnectionError("no network")

    assert check.github_superseded("owner/repo", "tok", get_json=broken)(SHA, "b" * 40) is False
    assert check.github_superseded("owner/repo", "", get_json=lambda url, headers=None: {"status": "ahead"})(SHA, "b" * 40) is True


def test_main_passes_the_github_comparison_only_when_it_knows_the_repository(monkeypatch):
    seen = {}

    def fake_wait(url, sha, **kw):
        seen.update(kw)
        return check.Result(True, "ok")

    monkeypatch.setattr(check, "wait_for_deploy", fake_wait)
    monkeypatch.setenv("RENDER_API_URL", URL)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert check.main(["--sha", SHA]) == 0 and seen.get("superseded") is None
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    assert check.main(["--sha", SHA]) == 0 and callable(seen["superseded"])
