"""Loading the history in batches (#876, epic #872): turn ``active: true`` on one batch of seasons of ``config/competitions.json`` at a time.

The history and the youth championships of FEB (``packages: false``) are in the catalogue paused, and a refresh loads about two seasons (~2,000 games each, ~0.5 s a game) inside its 90 minutes; so
a batch is a few seasons, and Tercera FEB (~1,770 games a season) goes on its own (``exclude``/``only``). The current season (entries with packages) and what is already active are never touched,
and a second run changes nothing, not even a byte. FBCYL seasons are turned on the same way (``league="fbcyl"``).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def activate_seasons(path: Any, seasons: Iterable[str], league: str = "feb", only: Optional[Iterable[str]] = None, exclude: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """``{"activated": n, "by_season": {season: n}}``: the paused entries of ``league`` for those seasons turned on; the file is only written if something changed, in the format it already has.

    For FEB only the history and youth entries (``packages: false``) are candidates. ``only`` and ``exclude`` are names of competitions."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    wanted, only_names, skipped = {str(s) for s in seasons}, set(only or ()), set(exclude or ())
    by_season: Dict[str, int] = {}
    for entry in data["competitions"]:
        if entry.get("league", "feb") != league or str(entry["season_value"]) not in wanted or entry.get("active", True):
            continue
        if league == "feb" and entry.get("packages", True):
            continue
        if (only_names and entry["competition"] not in only_names) or entry["competition"] in skipped:
            continue
        entry["active"] = True
        by_season[entry["season_value"]] = by_season.get(entry["season_value"], 0) + 1
    if by_season:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"activated": sum(by_season.values()), "by_season": by_season}
