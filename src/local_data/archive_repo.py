"""The private git repository that keeps the archive of the games (#646): download it at the start of a refresh, save it at the end.

The archive is a few MB that change on every refresh, so the repository is rewritten as a single commit (its history would only grow); the last
versions stay reachable through tags (``archive-<date>-<sha>``) and the older ones are pruned. ``pull`` remembers the commit it downloaded
(``<dir>.base``, beside the directory, not in it) and ``push`` refuses to overwrite a remote that moved since, so two refreshes at once cannot
erase each other. The remote is any git URL: an SSH URL with the deploy key in the workflow, a local bare repository in the tests.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

TAG_PREFIX = "archive-"
BRANCH = "main"
KEEP = 10
_IDENTITY = {"GIT_AUTHOR_NAME": "basketlab-archive", "GIT_AUTHOR_EMAIL": "archive@users.noreply.github.com",
             "GIT_COMMITTER_NAME": "basketlab-archive", "GIT_COMMITTER_EMAIL": "archive@users.noreply.github.com"}


def _git(*args: str, cwd: Optional[Path] = None, env: Optional[dict] = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _head(url: str) -> str:
    """The commit of the branch on the remote, ``""`` while the repository is empty."""
    out = _git("ls-remote", "--heads", url, BRANCH)
    return out.split()[0] if out else ""


def _rmtree(path: Path) -> None:
    """``shutil.rmtree`` that also removes the read-only files git leaves (its objects are, on Windows)."""
    def writable(func, target, _exc):
        os.chmod(target, 0o700)
        func(target)

    shutil.rmtree(path, onerror=writable)


def _base_file(directory: Path) -> Path:
    directory = Path(directory)
    return directory.parent / (directory.name + ".base")


def pull(url: str, dest: Path) -> Path:
    """Download the archive into ``dest`` (a plain directory, emptied first; empty if the repository is). Remembers the commit for ``push``."""
    dest = Path(dest)
    if dest.exists():
        _rmtree(dest)
    head = _head(url)
    if head:
        _git("clone", "-q", "--depth", "1", "--branch", BRANCH, url, str(dest))
        _rmtree(dest / ".git")
    else:
        dest.mkdir(parents=True)
    _base_file(dest).write_text(head, encoding="utf-8")
    return dest


def _tags(url: str) -> List[str]:
    out = _git("ls-remote", "--tags", url, f"refs/tags/{TAG_PREFIX}*")
    return sorted(line.split("refs/tags/")[1] for line in out.splitlines() if "^{}" not in line)


def push(url: str, src: Path, message: str, now: Optional[datetime] = None, keep: int = KEEP) -> bool:
    """Save ``src`` as the whole content of the repository; ``False`` (nothing pushed) when it equals what is there. The version it replaces is
    tagged and only the last ``keep`` tags stay. Raises ``RuntimeError`` if the remote moved since ``pull``."""
    src = Path(src)
    when = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    base = _base_file(src).read_text(encoding="utf-8").strip() if _base_file(src).is_file() else ""
    head = _head(url)
    if head != base:
        raise RuntimeError("the archive changed on the remote since it was downloaded: not overwriting it")
    dates = {"GIT_AUTHOR_DATE": when.isoformat(), "GIT_COMMITTER_DATE": when.isoformat(), **_IDENTITY}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(src, work, ignore=shutil.ignore_patterns(".git"))
        _git("init", "-q", "-b", BRANCH, str(work))
        _git("add", "-A", cwd=work)
        tree = _git("write-tree", cwd=work)
        tag = None
        if head:
            _git("fetch", "-q", "--depth", "1", url, BRANCH, cwd=work)
            if _git("rev-parse", "FETCH_HEAD^{tree}", cwd=work) == tree:
                return False
            replaced = _git("show", "-s", "--format=%cI", "FETCH_HEAD", cwd=work)
            stamp = datetime.fromisoformat(replaced).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            tag = f"{TAG_PREFIX}{stamp}-{head[:7]}"
            _git("push", "-q", url, f"{head}:refs/tags/{tag}", cwd=work)
        elif not any(work.iterdir()):
            return False
        _git("commit", "-q", "-m", message, cwd=work, env=dates)
        lease = f"--force-with-lease={BRANCH}:{head}"
        _git("push", "-q", lease, url, f"HEAD:refs/heads/{BRANCH}", cwd=work)
        new_head = _git("rev-parse", "HEAD", cwd=work)
    for old in _tags(url)[:-keep] if keep else _tags(url):
        _git("push", "-q", url, f":refs/tags/{old}")
    _base_file(src).write_text(new_head, encoding="utf-8")
    return True
