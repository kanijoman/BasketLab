"""The checks before opening a pull request (``scripts/pre_pr.py``) and the hook that runs them on ``gh pr create``.

CLAUDE.md lists what must be true before a PR (ruff clean, rebased on ``origin/main``, red proof, docs). The rules that only lived in a memory file were kept by habit; the script
makes them a command, and the hook of ``.claude/settings.json`` runs it when ``gh pr create`` is about to. What blocks is what is deterministic (ruff, the branch behind main,
the docs consistency); the red proof only warns.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pre_pr  # noqa: E402

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=GIT_ENV)


def commit(repo, name):
    (Path(repo) / name).write_text(name, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)


@pytest.fixture()
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    commit(tmp_path, "base.txt")
    git(tmp_path, "checkout", "-q", "-b", "work")
    return tmp_path


def test_a_branch_that_contains_the_tip_of_main_is_rebased(repo):
    commit(repo, "mine.txt")
    assert pre_pr.is_rebased(repo, "main")


def test_a_branch_behind_main_is_not_rebased_regression(repo):
    """Main moved on after the branch was cut (another PR came in): opening the PR now would be the stale-branch case the rebase rule exists for."""
    git(repo, "checkout", "-q", "main")
    commit(repo, "another-pr.txt")
    git(repo, "checkout", "-q", "work")
    commit(repo, "mine.txt")
    assert not pre_pr.is_rebased(repo, "main")


@pytest.mark.parametrize("command, expected", [
    ("gh pr create --title x --body y", True),
    ("cd repo && gh pr create --fill", True),
    ("gh pr list", False),
    ("git commit -m 'gh pr create is how a PR is opened'", False),
    ("gh pr checks 1189", False),
])
def test_the_hook_only_acts_on_gh_pr_create(command, expected):
    assert pre_pr.targets_pr_create(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})) is expected


@pytest.mark.parametrize("payload", ["", "not json", "[]", json.dumps({"tool_input": None}), json.dumps({"tool_input": {}})])
def test_a_hook_payload_it_cannot_read_never_blocks(payload):
    assert pre_pr.targets_pr_create(payload) is False


def test_a_failing_blocking_check_stops_the_pr_and_a_failing_warning_does_not():
    ok = pre_pr.Result("ruff", True, True, "")
    assert pre_pr.verdict([ok, pre_pr.Result("red proof", False, False, "no red")])[0] == 0
    code, lines = pre_pr.verdict([ok, pre_pr.Result("rebase", True, False, "behind origin/main")])
    assert code == 1 and any("rebase" in line and "behind origin/main" in line for line in lines)


def test_the_hook_blocks_with_exit_code_two_because_that_is_what_the_harness_reads_as_a_stop():
    assert pre_pr.exit_code_for(1, hook=True) == 2 and pre_pr.exit_code_for(1, hook=False) == 1 and pre_pr.exit_code_for(0, hook=True) == 0
