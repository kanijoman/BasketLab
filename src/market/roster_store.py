"""Where the roster sweep leaves its result and where the publication reads it (A5 #905 writes, B2 #878 reads): ``rosters/<season>.json`` of the private ``basketlab-archive-ext``.

One file per season, ``{"format": 1, "season": "2025", "teams": ["10", "11"], "rows": [...]}``: ``teams`` are the teams that were SWEPT (a team whose page has no players has no rows and was
swept all the same, so a first load that takes several runs knows where it stopped; a file without the list counts the teams of its rows). Rows sorted and no timestamp, so a run with no news
changes no byte (and git has nothing to commit). A file that cannot be read raises: the alternative is publishing every player without a birth date and nobody noticing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set

FORMAT = 1


def _sorted(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return sorted((dict(r) for r in rows), key=lambda r: (str(r["person_id"]), str(r["team_id"])))


def _read(path: Path) -> Dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path.name} cannot be read: {exc}") from exc
    if doc.get("format") != FORMAT:
        raise ValueError(f"{path.name}: format {doc.get('format')!r} is not the {FORMAT} this code reads")
    return doc


def _teams_of(doc: Mapping[str, Any]) -> Set[str]:
    return {str(t) for t in doc["teams"]} if "teams" in doc else {str(r["team_id"]) for r in doc.get("rows", [])}


def write_season(folder: Any, season: str, rows: Iterable[Mapping[str, Any]], teams: Optional[Iterable[str]] = None) -> bool:
    """Write ``<season>.json`` and return whether the bytes changed. Rows of another season are a mistake, not a guess; ``teams`` (default: those of the rows) must include the rows' teams."""
    rows = _sorted(rows)
    if any(str(r.get("season")) != str(season) for r in rows):
        raise ValueError(f"rows of another season than {season}")
    row_teams = {str(r["team_id"]) for r in rows}
    swept = row_teams if teams is None else {str(t) for t in teams}
    if not row_teams <= swept:
        raise ValueError("teams swept must include the teams of the rows")
    data = (json.dumps({"format": FORMAT, "season": str(season), "teams": sorted(swept), "rows": rows}, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    path = Path(folder) / f"{season}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def merge_season(folder: Any, season: str, rows: Iterable[Mapping[str, Any]], swept: Iterable[str]) -> bool:
    """Put what a sweep found into the file of the season: the rows of the swept teams REPLACE the old ones (a player who left a roster must disappear), the rest stays, and the swept teams
    add up between runs. Nothing swept writes nothing. Returns whether the bytes changed."""
    swept = {str(t) for t in swept}
    if not swept:
        return False
    path = Path(folder) / f"{season}.json"
    old = _read(path) if path.is_file() else {"rows": []}
    kept = [r for r in old.get("rows", []) if str(r["team_id"]) not in swept]
    return write_season(folder, season, [*kept, *rows], teams=_teams_of(old) | swept if path.is_file() else swept)


def read_swept(folder: Any) -> Dict[str, Set[str]]:
    """``{season: {team ids swept}}`` of every file of ``folder``; no folder is nothing swept."""
    folder = Path(folder)
    return {str(doc["season"]): _teams_of(doc) for doc in (_read(p) for p in sorted(folder.glob("*.json")))} if folder.is_dir() else {}


def read_rosters(folder: Any) -> List[Dict[str, Any]]:
    """The rows of every season of ``folder``, in season order; no folder is no rosters."""
    folder = Path(folder)
    rows: List[Dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        rows.extend(_read(path).get("rows", []))
    return rows
