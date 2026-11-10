"""Scenarios for ``get_player_in_out_stats`` of the repository, to pin down what it returns (issue #200, second PR).

The repository reads games from Mongo: ``get_games_with_playbyplay`` / ``count_games_with_playbyplay`` and ``find_one`` are the boundary and are faked here;
everything else (the analyzer, the calculator, the accumulation) is the real code. ``python tests/inout_repo_corpus.py`` regenerates
``tests/fixtures/inout_repository_golden.json`` from the CURRENT code: only when a rule is changed on purpose (a refactor leaves the file as it is).
"""
from __future__ import annotations

import copy
import gzip
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
for extra in (ROOT, ROOT / "src"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

GOLDEN = Path(__file__).parent / "fixtures" / "inout_repository_golden.json"
FBCYL_COLLECTION = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
FEB_COLLECTION = "LF_CHALLENGE_2026_2027_Liga_Regular_Único"


def fbcyl_game() -> Dict[str, Any]:
    with gzip.open(Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz", "rt", encoding="utf-8") as f:
        return json.load(f)


def _line(quarter: str, time: str, team: str, player: str | None, text: str, action: str = "") -> Dict[str, Any]:
    line = {"quarter": quarter, "time": time, "idTeam": team, "text": text, "action": action}
    if player is not None:
        line["idPlayer"] = player
    return line


def feb_game(minutes: Dict[str, Any] | None = None, team_b_players: bool = True) -> Dict[str, Any]:
    """A small FEB game: player P1 of team A enters at 10:00 of the first quarter and leaves at 05:00; lines are stored newest first."""
    minutes = minutes or {}
    chrono = [
        _line("1", "10:00", "A", "P1", "Entra a pista"),
        _line("1", "09:50", "A", "P1", "Tiro de 2 anotado", "shoot"),
        _line("1", "09:40", "B", "Q1", "Tiro de 3 fallado", "shoot"),
        _line("1", "09:39", "A", "P2", "Rebote defensivo", "rebound"),
        _line("1", "09:20", "A", "P1", "Pérdida de balón", "turnover"),
        _line("1", "09:00", "B", "Q1", "Tiro de 2 anotado", "shoot"),
        _line("1", "08:30", "A", "P2", "Tiro de 3 fallado", "shoot"),
        _line("1", "08:29", "A", "P2", "Rebote ofensivo", "rebound"),
        _line("1", "05:00", "A", "P1", "Sale de pista"),
        _line("1", "04:30", "B", "Q1", "Falta personal", "foul"),
        _line("1", "04:00", "A", "P2", "Tiro libre anotado", "fthrow"),
        _line("1", "03:00", "A", "P2", "Asistencia", "assist"),
    ]
    return {
        "_id": "feb-1",
        "BOXSCORE": {"TEAM": [
            {"id": "A", "PLAYER": [{"id": "P1", "min": minutes.get("P1", "05:00")}, {"id": "P2", "min": minutes.get("P2", "10:00")}]},
            {"id": "B", "PLAYER": [{"id": "Q1", "min": "10:00"}] if team_b_players else []},
        ]},
        "PLAYBYPLAY": {"LINES": list(reversed(chrono))},
    }


def fbcyl_players(game: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [p for team in game["stats"]["teams"] for p in team["players"]]


def _fake_repo(games: List[Dict[str, Any]], collection: str, player_doc: Dict[str, Any] | None = None, connected: bool = True):
    from src.database.repository import BasketballRepository

    connection = MagicMock()
    connection.is_connected.return_value = connected
    connection.get_collection.return_value.find_one.return_value = player_doc
    repo = BasketballRepository(connection)
    repo.count_games_with_playbyplay = lambda name, date_filter=None: len(games)           # type: ignore[method-assign]
    repo.get_games_with_playbyplay = lambda name, date_filter=None: iter(copy.deepcopy(games))   # type: ignore[method-assign]
    return repo


def _run(games, collection, player_id, player_doc=None, connected=True) -> Dict[str, Any]:
    repo = _fake_repo(games, collection, player_doc, connected)
    progress: List[List[int]] = []
    result = repo.get_player_in_out_stats(collection, player_id, progress_callback=lambda cur, tot: progress.append([cur, tot]))
    return {"result": result, "progress": progress}


FEB_PLAYER_DOC = {"BOXSCORE": {"TEAM": [{"id": "A", "PLAYER": [{"id": "P1"}, {"id": "P2"}]}, {"id": "B", "PLAYER": [{"id": "Q1"}]}]}}


def corpus() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    real = fbcyl_game()
    # FBCYL, a real match: every player, by uuid
    for player in fbcyl_players(real):
        out[f"fbcyl real {player['uuid']}"] = _run([real], FBCYL_COLLECTION, player["uuid"])
    uuid = fbcyl_players(real)[0]["uuid"]
    # two games of the same team
    out["fbcyl two games"] = _run([real, real], FBCYL_COLLECTION, uuid)
    # the team of the player has no players listed: the game is skipped
    no_team = copy.deepcopy(real)
    next(t for t in no_team["stats"]["teams"] if any(p["uuid"] == uuid for p in t["players"]))["players"] = []
    out["fbcyl team without players"] = _run([no_team], FBCYL_COLLECTION, uuid)
    # a phantom player: 40 minutes and no activity (inscribed, never played)
    phantom = copy.deepcopy(real)
    for p in fbcyl_players(phantom):
        if p["uuid"] == uuid:
            p["timePlayed"] = 40.0
            p["data"] = {}
    out["fbcyl phantom"] = _run([phantom], FBCYL_COLLECTION, uuid)
    # no minutes at all for the player
    no_minutes = copy.deepcopy(real)
    for p in fbcyl_players(no_minutes):
        if p["uuid"] == uuid:
            p["timePlayed"] = None
    out["fbcyl no minutes"] = _run([no_minutes], FBCYL_COLLECTION, uuid)
    # identified by name instead of uuid (the surnames fallback)
    named = fbcyl_players(real)[0]["name"]
    out["fbcyl by name"] = _run([real], FBCYL_COLLECTION, named)
    out["fbcyl unknown player"] = _run([real], FBCYL_COLLECTION, "no-such-player")
    out["fbcyl no games"] = _run([], FBCYL_COLLECTION, uuid)

    # FEB
    for label, minutes in (("string", {}), ("number", {"P1": 5}), ("zero", {"P1": "0:00"}), ("none", {"P1": None}), ("plain string", {"P1": "5"}),
                           ("broken", {"P1": "x:y"}), ("seconds only", {"P1": "5:"}), ("text", {"P1": "abc"})):
        out[f"feb minutes {label}"] = _run([feb_game(minutes)], FEB_COLLECTION, "P1", FEB_PLAYER_DOC)
    out["feb two games"] = _run([feb_game(), feb_game()], FEB_COLLECTION, "P1", FEB_PLAYER_DOC)
    out["feb bench player"] = _run([feb_game()], FEB_COLLECTION, "P2", FEB_PLAYER_DOC)
    out["feb rival team without players"] = _run([feb_game(team_b_players=False)], FEB_COLLECTION, "P1", FEB_PLAYER_DOC)
    out["feb player not found"] = _run([feb_game()], FEB_COLLECTION, "P1", None)
    out["feb player in no team"] = _run([feb_game()], FEB_COLLECTION, "P1", {"BOXSCORE": {"TEAM": [{"id": "A", "PLAYER": [{"id": "P9"}]}]}})
    out["feb no games"] = _run([], FEB_COLLECTION, "P1", FEB_PLAYER_DOC)
    out["not connected"] = _run([feb_game()], FEB_COLLECTION, "P1", FEB_PLAYER_DOC, connected=False)
    return out


def write_golden() -> int:
    data = corpus()
    GOLDEN.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1, default=str), encoding="utf-8")
    return len(data)


def read_golden() -> Dict[str, Any]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(write_golden(), "scenarios written to", GOLDEN)
