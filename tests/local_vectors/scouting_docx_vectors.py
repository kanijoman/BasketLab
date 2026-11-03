"""The vectors of the tables of the individual scouting DOCX in the browser (#717, 17b): what ``player_tables`` says of each player against a league, the reference of
``frontend/src/lib/scoutingDocx.test.ts``.

Besides the players the API gives for the sample league, a league of awkward floats (many decimals, ties, missing figures, minutes that round to a whole minute) checks the formats
(``%``, MM:SS) and the quartile thresholds to the last digit.
"""
import json
import random
from pathlib import Path
from typing import Any, Dict, List

from src.services.scouting_docx_tables import ADVANCED, AVERAGES, player_tables

HERE = Path(__file__).resolve().parent
KEYS = [c[1] for c in AVERAGES + ADVANCED]


def _awkward() -> List[Dict[str, Any]]:
    rng = random.Random(717)
    players = []
    for i in range(14):
        row: Dict[str, Any] = {"player_id": str(i), "player_name": f"J{i}", "team_name": "T", "total_minutes": rng.choice((0, 59.999, 205.5, 1.0 / 3.0, 640.25))}
        for key in KEYS:
            row[key] = None if (i + len(key)) % 9 == 0 else (rng.choice((50.0, 12.5)) if i % 4 == 0 else rng.uniform(0, 40) / rng.choice((1, 3, 7)))
        row["games_played"] = rng.randint(1, 34)            # a count, never a float (the totals print it as it is)
        for key in ("total_pts", "total_p1m", "total_p1a", "total_p2m", "total_p2a", "total_p3m", "total_p3a", "total_ro", "total_rd", "total_rt", "total_assist", "total_st", "total_to",
                    "total_bs", "total_pf", "total_val"):
            row[key] = rng.randint(0, 400)
        players.append(row)
    return players


def build() -> Dict[str, Any]:
    sample = json.loads((HERE / "players_feb.json").read_text(encoding="utf-8"))["cases"][0]["players"]
    leagues = []
    for name, players in (("sample", sample), ("awkward", _awkward())):
        leagues.append({"name": name, "players": players, "expected": [player_tables(p, players) for p in players]})
    return {"leagues": leagues}
