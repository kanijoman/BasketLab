"""The bio an external source lends to a FEB person (#979): FIBA's birth, height and nationality of a player the identity link (``identity_link``, ``links/<source>.json``) says IS that person.

Only ``linked`` links are used; a ``review`` waits for the staff (#980). The candidates go through ``season_rows.attach_bio``, which lets FEB win and fills only what FEB leaves empty. Pure functions except ``read_games`` and ``read_external_bio``, which read the external archive;
the value of a field does not depend on the order of the games: the most said one, a tie to the smallest.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional

SOURCE = "fiba"
FIELDS = ("birth", "height", "nationality")


def linked_persons(links: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """``{external id: FEB person id}`` of the ``linked`` links of a ``links/<source>.json`` document (``None`` or without links: nothing)."""
    return {str(l["external"]): str(l["feb"]) for l in (links or {}).get("links", []) if l.get("status") == "linked" and l.get("feb")}


def external_bio(games: Iterable[Mapping[str, Any]], persons: Mapping[str, str], source: str = SOURCE) -> Dict[str, List[Dict[str, Any]]]:
    """``{FEB person id: [{source, birth, height, nationality}]}`` from the players of ``games`` (canonical documents) that ``persons`` links; a field no game says is left out."""
    seen: Dict[str, Dict[str, Counter]] = {}
    for game in games:
        for team in (game.get("BOXSCORE") or {}).get("TEAM") or []:
            for player in team.get("PLAYER") or []:
                pid = str(player.get("id"))
                if pid in persons:
                    counts = seen.setdefault(pid, {f: Counter() for f in FIELDS})
                    for field in FIELDS:
                        if player.get(field):
                            counts[field][str(player[field])] += 1
    out: Dict[str, List[Dict[str, Any]]] = {}
    for pid in sorted(seen):
        values = {f: min(c.items(), key=lambda kv: (-kv[1], kv[0]))[0] for f, c in seen[pid].items() if c}
        if values:
            out.setdefault(persons[pid], []).append({"source": source, **values})
    return out


def read_games(folder: Path) -> Iterator[Dict[str, Any]]:
    """The games of ``<source>/*.jsonl.gz`` of the external archive, in file order."""
    for path in sorted(Path(folder).glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def read_external_bio(root: Any, source: str = SOURCE) -> Dict[str, List[Dict[str, Any]]]:
    """``external_bio`` of the external archive at ``root``: its ``links/<source>.json`` and its ``<source>/`` games. Missing links or games are no bio, not an error (the links file is written by the
    workflow before the build); one that cannot be read raises, so a broken file is not published as 'no bio'."""
    root = Path(root)
    path = root / "links" / f"{source}.json"
    if not path.is_file() or not (root / source).is_dir():
        return {}
    return external_bio(read_games(root / source), linked_persons(json.loads(path.read_text(encoding="utf-8"))), source)
