"""The private repository of the archive (#646): where the refresh downloads the games from and saves them to.

The archive is rewritten as a single commit on every change (no history growth: it is a few MB per refresh), but the last versions stay reachable
through tags, so a bad refresh (a scrape that lost games, a corrupt write) can be rolled back. Tested against a local bare repository, which is
exactly what the remote is for git.
"""
import subprocess
from urllib.parse import urlparse
from urllib.request import url2pathname
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.local_data.archive_repo import TAG_PREFIX, pull, push


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def remote(tmp_path):
    path = tmp_path / "remote.git"
    git("init", "-q", "--bare", "-b", "main", str(path))
    return path.as_uri()


def _bare(url: str) -> Path:
    return Path(url2pathname(urlparse(url).path))


def _write(folder: Path, files: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")


def _at(day: int) -> datetime:
    return datetime(2026, 10, day, 5, 30, tzinfo=timezone.utc)


def _remote_files(remote, tmp_path) -> dict:
    out = tmp_path / "check"
    git("clone", "-q", "--depth", "1", remote, str(out))
    return {p.name: p.read_text(encoding="utf-8") for p in out.iterdir() if p.is_file()}


def test_pulling_an_empty_remote_gives_an_empty_directory(remote, tmp_path):
    work = tmp_path / "work"
    pull(remote, work)
    assert work.is_dir() and not any(work.iterdir())


def test_what_is_pushed_is_pulled_back(remote, tmp_path):
    _write(tmp_path / "a", {"archive.json": "one"})
    assert push(remote, tmp_path / "a", "seed", now=_at(1)) is True
    pull(remote, tmp_path / "b")
    assert (tmp_path / "b" / "archive.json").read_text(encoding="utf-8") == "one"
    assert not (tmp_path / "b" / ".git").exists()                      # a plain directory: the archive tools do not know about git


def test_an_unchanged_archive_is_not_pushed(remote, tmp_path):
    _write(tmp_path / "a", {"archive.json": "one"})
    push(remote, tmp_path / "a", "seed", now=_at(1))
    head = git("ls-remote", remote, "main")
    pull(remote, tmp_path / "b")
    assert push(remote, tmp_path / "b", "again", now=_at(2)) is False
    assert git("ls-remote", remote, "main") == head


def test_history_stays_one_commit_and_the_previous_versions_are_tagged(remote, tmp_path):
    work = tmp_path / "w"
    _write(work, {"archive.json": "v1"})
    push(remote, work, "r1", now=_at(1))
    pull(remote, tmp_path / "w2")
    _write(tmp_path / "w2", {"archive.json": "v2"})
    push(remote, tmp_path / "w2", "r2", now=_at(2))
    bare = _bare(remote)
    assert git("rev-list", "--count", "main", cwd=bare) == "1"
    tags = git("tag", "--list", f"{TAG_PREFIX}*", cwd=bare).split()
    assert len(tags) == 1
    assert git("show", f"{tags[0]}:archive.json", cwd=bare) == "v1"      # the version that was replaced
    assert _remote_files(remote, tmp_path) == {"archive.json": "v2"}


def test_only_the_last_versions_keep_their_tag(remote, tmp_path):
    work = tmp_path / "w"
    _write(work, {"archive.json": "v0"})
    push(remote, work, "r0", now=_at(1), keep=2)
    for day in range(2, 7):
        pull(remote, tmp_path / f"w{day}")
        _write(tmp_path / f"w{day}", {"archive.json": f"v{day}"})
        push(remote, tmp_path / f"w{day}", f"r{day}", now=_at(day), keep=2)
    bare = _bare(remote)
    tags = git("tag", "--list", f"{TAG_PREFIX}*", cwd=bare).split()
    assert len(tags) == 2
    assert [git("show", f"{t}:archive.json", cwd=bare) for t in sorted(tags)] == ["v4", "v5"]   # the two versions before the current v6


def test_a_remote_that_changed_meanwhile_is_not_overwritten(remote, tmp_path):
    """Two refreshes must not run at once (the workflow has a concurrency group), but if one did, the second must fail, not erase the first."""
    _write(tmp_path / "a", {"archive.json": "v1"})
    push(remote, tmp_path / "a", "seed", now=_at(1))
    pull(remote, tmp_path / "slow")
    pull(remote, tmp_path / "fast")
    _write(tmp_path / "fast", {"archive.json": "fast"})
    push(remote, tmp_path / "fast", "fast", now=_at(2))
    _write(tmp_path / "slow", {"archive.json": "slow"})
    with pytest.raises(RuntimeError, match="changed"):
        push(remote, tmp_path / "slow", "slow", now=_at(3))
    assert _remote_files(remote, tmp_path) == {"archive.json": "fast"}


def test_the_entry_point_pulls_and_pushes(remote, tmp_path, capsys):
    import run_archive

    assert run_archive.main(["pull", "--repo", remote, "--dir", str(tmp_path / "dir")]) == 0
    _write(tmp_path / "dir", {"archive.json": "x"})
    assert run_archive.main(["push", "--repo", remote, "--dir", str(tmp_path / "dir")]) == 0
    assert run_archive.main(["pull", "--repo", remote, "--dir", str(tmp_path / "again")]) == 0
    assert (tmp_path / "again" / "archive.json").read_text(encoding="utf-8") == "x"
    assert run_archive.main(["push", "--repo", remote, "--dir", str(tmp_path / "again")]) == 0
    assert "unchanged" in capsys.readouterr().out
