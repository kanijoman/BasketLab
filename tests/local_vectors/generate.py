"""Regenerate ``team_stats_feb.json``: the parity vectors of the local team tables (#327).

Python is the reference: the real season pipelines (team and rival) run on mongomock over the league of ``games.py``, once per filter, and the
file keeps the contract rows plus what the API answers. The web aggregates the rows on the device (``frontend/src/localdata``) and must give the
same figures. Run ``python tests/local_vectors/generate.py`` and review the diff after changing the pipelines or ``games.py``.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import mongomock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(Path(__file__).resolve().parent)]

from games import build_games  # noqa: E402

from src.database.aggregation import AggregationPipelineBuilder as Pipelines  # noqa: E402
from src.services._team_id import with_team_id  # noqa: E402

OUT = Path(__file__).resolve().parent / "team_stats_feb.json"
FILTERS = [
    {"name": "all"},
    {"name": "home", "venue": "home"},
    {"name": "away", "venue": "away"},
    {"name": "won", "result": "won"},
    {"name": "lost", "result": "lost"},
    {"name": "home won", "venue": "home", "result": "won"},
    {"name": "from date", "from": "2025-11-01"},
    {"name": "to date (the last day's games are left out: midnight bound)", "to": "2025-11-12"},
    {"name": "date range", "from": "2025-10-20", "to": "2025-11-25"},
    {"name": "date range away lost", "from": "2025-10-20", "to": "2025-11-25", "venue": "away", "result": "lost"},
    {"name": "empty range", "from": "2030-01-01"},
]


def _played(doc: dict) -> datetime:
    return datetime.strptime(doc["HEADER"]["starttime"], "%d-%m-%Y - %H:%M")


def _run(games: list, filt: dict) -> dict:
    """What ``GET /teams/{collection}`` answers for these games and the venue / result of the filter (dates are applied by choosing the games)."""
    col = mongomock.MongoClient()["v"]["LEAGUE"]
    if games:
        col.insert_many(games)
    venue = {"home": True, "away": False}.get(filt.get("venue"))
    result = filt.get("result")
    return {"team_stats": with_team_id(list(col.aggregate(Pipelines.build_team_stats_pipeline(None, venue, result)))),
            "opponent_stats": with_team_id(list(col.aggregate(Pipelines.build_opponent_stats_pipeline(None, venue, result))))}


def _in_range(doc: dict, filt: dict) -> bool:
    """The API turns ``YYYY-MM-DD`` into midnight and compares inclusively: a game played on the ``to`` day is out."""
    played = _played(doc)
    return ("from" not in filt or played >= datetime.fromisoformat(filt["from"])) and ("to" not in filt or played <= datetime.fromisoformat(filt["to"]))


def _clean(rows: list) -> list:
    return [{k: v for k, v in row.items() if k != "_id" or isinstance(v, str)} for row in rows]


def build_vectors() -> dict:
    games = build_games()
    col = mongomock.MongoClient()["v"]["LEAGUE"]
    col.insert_many(build_games())
    rows = [{k: v for k, v in r.items() if k != "_id"} for r in col.aggregate(Pipelines.build_season_rows_pipeline())]
    cases = []
    for filt in FILTERS:
        out = _run([g for g in build_games() if _in_range(g, filt)], filt)
        cases.append({"filter": {k: v for k, v in filt.items() if k != "name"}, "name": filt["name"], "team_stats": _clean(out["team_stats"]),
                      "opponent_stats": _clean(out["opponent_stats"])})
    return {"games": len(games), "rows": rows, "cases": cases}


def main() -> None:
    OUT.write_text(json.dumps(build_vectors(), ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
