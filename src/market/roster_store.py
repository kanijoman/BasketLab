"""Where the roster sweep leaves its result and where the publication reads it (A5 #905 writes, B2 #878 reads): ``rosters/<season>.json`` of the private ``basketlab-archive-ext``.

One file per season, ``{"format": 1, "season": "2025", "rows": [...]}``, rows sorted and no timestamp, so a run with no news changes no byte (and git has nothing to commit). A file that cannot
be read raises: the alternative is publishing every player without a birth date and nobody noticing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

FORMAT = 1


def _sorted(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return sorted((dict(r) for r in rows), key=lambda r: (str(r["person_id"]), str(r["team_id"])))


def write_season(folder: Any, season: str, rows: Iterable[Mapping[str, Any]]) -> bool:
    """Write ``<season>.json`` and return whether the bytes changed. Rows of another season are a mistake, not a guess."""
    rows = _sorted(rows)
    if any(str(r.get("season")) != str(season) for r in rows):
        raise ValueError(f"rows of another season than {season}")
    data = (json.dumps({"format": FORMAT, "season": str(season), "rows": rows}, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    path = Path(folder) / f"{season}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def read_rosters(folder: Any) -> List[Dict[str, Any]]:
    """The rows of every season of ``folder``, in season order; no folder is no rosters."""
    folder = Path(folder)
    rows: List[Dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"{path.name} cannot be read: {exc}") from exc
        if doc.get("format") != FORMAT:
            raise ValueError(f"{path.name}: format {doc.get('format')!r} is not the {FORMAT} this code reads")
        rows.extend(doc.get("rows", []))
    return rows
