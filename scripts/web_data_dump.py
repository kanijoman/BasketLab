"""Write the published web-data as a local export, for the studies (#938): ``python scripts/web_data_dump.py --out DIR [--source origin/web-data | PATH] [--min-games 100] [--pattern Liga_Regular]``.

The rows of ``web-data`` are what ``run_local_export.py`` writes (``export_collection``), sealed per competition. While the beta is open the manifest carries the key of the open scope
(``open_key``), so they open without a password and without a database. The dump writes them in the layout of the local export (``DIR/index.json`` with one entry per competition, and one
file per competition with its rows) so that ``FORECAST_STUDY_DIR=DIR npm run study:forecast`` / ``study:projection`` read the published games; and the per-possession CSV of the competitions
that have play-by-play next to them (``DIR/possession_csv/``) for ``scripts/pace_style_study.py``. ``--source`` is a git ref of the branch (read with ``git show``) or a directory with a
publication (such as ``tests/local_vectors/web_data``).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from src.live_prep.package_scopes import SCOPE_OPEN, open_sealed  # noqa: E402


class DirectorySource:
    """A publication on disk."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def read(self, path: str) -> bytes:
        return (self.root / path).read_bytes()


class GitSource:
    """A publication on a branch of the repository, read without checking it out."""

    def __init__(self, ref: str, repo: Path = ROOT):
        self.ref, self.repo = ref, repo

    def read(self, path: str) -> bytes:
        return subprocess.run(["git", "-C", str(self.repo), "show", f"{self.ref}:{path}"], capture_output=True, check=True).stdout


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def _open(source: Any, entry: Dict[str, Any], keys: Dict[str, bytes]) -> Any:
    return json.loads(open_sealed(json.loads(source.read(entry["file"])), entry["wraps"], keys))


def dump(source: Any, out: Path, min_games: int = 100, pattern: str = "Liga_Regular") -> Dict[str, List[Dict[str, Any]]]:
    """Write the competitions of the publication with at least ``min_games`` games whose name matches ``pattern``; returns the index written."""
    manifest = json.loads(source.read("index.json"))
    if not manifest.get("open_key"):
        raise SystemExit("The publication has no open key (the beta is closed): its rows need the key of a scope, which this dump does not take.")
    keys = {SCOPE_OPEN: base64.b64decode(manifest["open_key"])}
    csv_of = {e["collection"]: e for e in manifest.get("possession_csv", [])}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    collections: List[Dict[str, Any]] = []
    for entry in sorted(manifest["rows"], key=lambda e: e["collection"]):
        name = entry["collection"]
        if entry["games"] < min_games or not re.search(pattern, name):
            continue
        competition = _open(source, entry, keys)
        file = f"{_safe(name)}.json"
        (out / file).write_text(json.dumps(competition, ensure_ascii=False), encoding="utf-8")
        item = {"name": name, "file": file, "league": competition.get("league", entry.get("league")), "games": entry["games"], "gender": entry.get("gender")}
        if name in csv_of:
            (out / "possession_csv").mkdir(exist_ok=True)
            item["possession_csv"] = f"possession_csv/{_safe(name)}.csv"
            (out / item["possession_csv"]).write_bytes(_open(source, csv_of[name], keys)["csv"].encode("utf-8"))      # as published (its rows end in CRLF)
        collections.append(item)
    index = {"collections": collections}
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return index


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write the published web-data as a local export, for the studies")
    parser.add_argument("--out", required=True)
    parser.add_argument("--source", default="origin/web-data", help="a git ref of the published branch or a directory with a publication")
    parser.add_argument("--min-games", type=int, default=100)
    parser.add_argument("--pattern", default="Liga_Regular", help="a regular expression the name of a competition must match")
    args = parser.parse_args(argv)
    source = DirectorySource(Path(args.source)) if Path(args.source).is_dir() else GitSource(args.source)
    index = dump(source, Path(args.out), args.min_games, args.pattern)
    for e in index["collections"]:
        print(f"{e['name']}: {e['games']} games{' + possessions' if 'possession_csv' in e else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
