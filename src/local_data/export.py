"""Export of the rows of the local-first contract: one file per competition plus an index (#327, step 2).

A file holds what the season pipelines read, one row per team and game and (FEB) one per player and game; ``frontend/src/localdata`` sums
them on the device. Files carry no timestamp and keep the order of the pipelines, so a refresh that brings no new game changes no byte.
``player_rows`` is ``None`` for FBCYL (its player table still comes from the API, issue #644).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

from src.database.aggregation import AggregationPipelineBuilder
from src.database.aggregation.fbcyl_per_game_pipeline import build_fbcyl_season_rows_pipeline
from src.utils.collection_utils import is_fbcyl

FORMAT = 1
INDEX = "index.json"


def _rows(collection: Any, pipeline: List[Dict]) -> List[Dict]:
    return [{k: v for k, v in row.items() if k != "_id"} for row in collection.aggregate(pipeline, allowDiskUse=True)]


def export_collection(collection: Any, name: str) -> Dict[str, Any]:
    """The payload of one competition: its team rows, its player rows (FEB; ``None`` for FBCYL) and how many games they come from."""
    fbcyl = is_fbcyl(name)
    team_rows = _rows(collection, build_fbcyl_season_rows_pipeline() if fbcyl else AggregationPipelineBuilder.build_season_rows_pipeline())
    player_rows = None if fbcyl else _rows(collection, AggregationPipelineBuilder.build_season_player_rows_pipeline())
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if fbcyl else "feb", "games": len({r["match_id"] for r in team_rows}),
            "team_rows": team_rows, "player_rows": player_rows}


def file_name(name: str) -> str:
    """An ASCII file name for a collection (names have accents, ``ª`` and ``º``): the percent-encoding with ``~`` for ``%`` (names have ``_``, not ``~``)."""
    return quote(name, safe="").replace("%", "~") + ".json"


def _dump(payload: Dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str) + "\n").encode("utf-8")


def _write_if_changed(path: Path, data: bytes) -> None:
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def _games_collections(db: Any) -> List[str]:
    from src.services.derived_backfill import fbcyl_collection_names, feb_collection_names

    return sorted(set(feb_collection_names(db)) | set(fbcyl_collection_names(db)))


def export_all(db: Any, out_dir: Path, only: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Write the file of every games collection (or of ``only``, keeping the rest of the directory) and the index; returns the index.

    Without ``only`` the directory mirrors the database: files of competitions that no longer exist are removed.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = list(only) if only is not None else _games_collections(db)
    previous = {}
    if only is not None and (out_dir / INDEX).is_file():
        previous = {c["name"]: c for c in json.loads((out_dir / INDEX).read_text(encoding="utf-8"))["collections"]}
    entries = dict(previous)
    for name in wanted:
        payload = export_collection(db[name], name)
        data = _dump(payload)
        _write_if_changed(out_dir / file_name(name), data)
        entries[name] = {"name": name, "file": file_name(name), "league": payload["league"], "games": payload["games"], "bytes": len(data)}
    index = {"format": FORMAT, "collections": [entries[n] for n in sorted(entries)]}
    if only is None:
        keep = {e["file"] for e in index["collections"]} | {INDEX}
        for stale in out_dir.glob("*.json"):
            if stale.name not in keep:
                stale.unlink()
    _write_if_changed(out_dir / INDEX, _dump(index))
    return index
