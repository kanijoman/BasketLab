"""The rotation analysis of every team of a competition, published for the web (#684): what ``GET /rotaciones/{collection}/{team_id}`` answers with its default thresholds,
computed once at publication (a few KB and a tenth of a second per team) so that the page does not wait for a stream."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.local_data.export import FORMAT  # noqa: E402
from src.local_data.rotations_export import export_rotations  # noqa: E402
from test_rotation_service import _fbcyl_game, _feb_game, _make_players  # noqa: E402
from services.rotation_service import RotationService  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"


def _handler(collection, per_team):
    """A database whose games are those of each team (the rotation service reads the games of a team)."""
    db = MagicMock()
    db.get_teams_with_ids.return_value = [{"id": team, "name": f"Team {team}"} for team in per_team]
    db.get_games_for_team.side_effect = lambda name, team_id, *a, **k: per_team[team_id]
    return db


def _feb(*team_ids):
    return {t: [_feb_game(t, _make_players(10)) for _ in range(6)] for t in team_ids}


def test_each_team_has_what_the_service_answers_for_it():
    db = _handler(FEB, _feb("10", "11"))
    payload = export_rotations(db, FEB)
    assert (payload["format"], payload["league"], payload["collection"]) == (FORMAT, "feb", FEB)
    assert [t["team_id"] for t in payload["teams"]] == ["10", "11"]
    for team in payload["teams"]:
        expected = RotationService(db).get_rotation_analysis(FEB, team["team_id"], team["team_name"])
        assert team["analysis"] == json.loads(json.dumps(expected, default=str)) and team["analysis"]["games_with_playbyplay"] == 6
    json.dumps(payload)


def test_fbcyl_teams_are_analysed_the_fbcyl_way():
    db = _handler(FBCYL, {"10": [_fbcyl_game("10", _make_players(10)) for _ in range(6)]})
    team = export_rotations(db, FBCYL)["teams"][0]
    assert team["analysis"] == json.loads(json.dumps(RotationService(db).get_rotation_analysis(FBCYL, "10", "Team 10"), default=str))
    assert team["analysis"]["total_games"] == 6


def test_a_team_with_no_games_is_not_published_and_a_competition_without_play_by_play_has_none():
    db = _handler(FEB, {"10": [], "11": [{k: v for k, v in _feb_game("11", _make_players(10)).items() if k != "PLAYBYPLAY"}]})
    assert [t["team_id"] for t in export_rotations(db, FEB)["teams"]] == ["11"]                  # it has games (of the box score), none with play-by-play
    assert export_rotations(db, FEB)["teams"][0]["analysis"]["games_with_playbyplay"] == 0
    assert export_rotations(_handler(FEB, {"10": []}), FEB)["teams"] == []
