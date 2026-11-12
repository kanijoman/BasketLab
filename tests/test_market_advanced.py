"""Advanced figures of the Talent rows (B2, #878): usage, ORtg, DRtg, net rating, AST%, TOV%, STL%, BLK%, REB% and PIE of a player in HIS team's context.

The reference is the parity vectors of the web (``tests/local_vectors/players_feb.json`` and ``players_fbcyl.json``): what ``GET /players/{collection}`` answers, which the browser reproduces. A row of
Talent must say the same as the Players page for the same player of the same competition; a transfer is two rows, each with its team's context."""
import json
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent))

from local_vectors import fbcyl_games  # noqa: E402
from local_vectors.games import build_games  # noqa: E402
from src.local_data.export import export_collection  # noqa: E402
from src.market.advanced import ADVANCED_FIELDS, add_advanced, team_context  # noqa: E402
from src.market.season_rows import season_player_rows  # noqa: E402

VECTORS = Path(__file__).resolve().parent / "local_vectors"


def _case(file):
    return next(c for c in json.loads((VECTORS / file).read_text(encoding="utf-8"))["cases"] if c["name"] == "all")["players"]


def _rows(name, games):
    collection = new_mock_db(name)[name]
    collection.insert_many(games)
    payload = export_collection(collection, name)
    return payload, add_advanced(season_player_rows([("g", payload)]), team_context(payload["team_rows"]))


@pytest.mark.parametrize("name,games,file,key", [
    ("LEAGUE", build_games, "players_feb.json", lambda v: (str(v["player_id"]), str(v["team_id"]))),
    ("FBCYL_LEAGUE", fbcyl_games.build_games, "players_fbcyl.json", lambda v: (str(v["player_uuid"]), str(v["team_id"]))),
])
def test_the_advanced_figures_are_the_ones_of_the_players_page(name, games, file, key):
    _, rows = _rows(name, games())
    expected = {key(v): v for v in _case(file)}
    prefix = "fbcyl:" if name.startswith("FBCYL") else "feb:"
    ours = {(r["person_id"].removeprefix(prefix), r["team_id"]): r for r in rows}
    assert set(ours) == set(expected)
    for k, want in expected.items():
        for field in ("usage_pct", "orating", "drating", "net_rtg", "ast_pct", "tov_pct_adv", "stl_pct", "blk_pct", "drb_pct", "orb_pct", "pie"):
            assert ours[k][field] == pytest.approx(want[field], abs=1e-9), (name, k, field)


def test_the_context_of_a_team_and_of_its_opponents_comes_from_the_games_of_the_competition():
    payload, _ = _rows("LEAGUE", build_games())
    context = team_context(payload["team_rows"])
    team, opponents = context["101"]
    rows = [r for r in payload["team_rows"] if r["team_id"] == "101"]
    assert team["total_games"] == len(rows) == opponents["total_games"]
    assert team["points_scored"] == sum(r["points"] for r in rows) and opponents["points_scored"] == sum(r["opponent_points"] for r in rows)
    assert team["fg3_made"] == sum(r["fg3_made"] for r in rows) and opponents["fg3_made"] == sum(r["opponent_fg3_made"] for r in rows)


def test_a_transfer_gets_the_context_of_each_of_his_teams():
    row = {"person_id": "feb:7", "name": "A. B C", "league": "feb", "groups": ["g"], "games": 4, "minutes": 4 * 1800, "pts": 40, "p1m": 4, "p1a": 5, "p2m": 10, "p2a": 20, "p3m": 4, "p3a": 8,
           "assist": 8, "ro": 4, "rd": 12, "rt": 16, "st": 4, "to": 8, "bs": 2, "pf": 8, "rf": 6, "val": 40, "pllss": 0}
    low = {"team_id": "A", "total_games": 4, "fg2_made": 100, "fg2_attempted": 200, "fg3_made": 40, "fg3_attempted": 100, "ft_made": 50, "ft_attempted": 70, "rebounds_def": 120,
           "rebounds_off": 40, "turnovers": 60, "assists": 80, "steals": 30, "blocks": 10, "personal_fouls": 70, "points_scored": 330}
    high = {**low, "team_id": "B", "points_scored": 420, "turnovers": 40}
    opp = {**low, "possessions_per_game": 70, "total_rebounds": 160}
    context = {"A": (low, opp), "B": (high, opp)}
    rows = add_advanced([{**row, "team_id": "A"}, {**row, "team_id": "B"}], context)
    assert rows[0]["usage_pct"] != rows[1]["usage_pct"] and rows[0]["team_id"] == "A"


def test_a_player_whose_team_has_no_context_gets_zeros_like_the_page_does():
    """#647: the service gives zeros under the keys of the normal path when it finds no context for the team."""
    (row,) = add_advanced([{"person_id": "feb:1", "team_id": "ZZ", "minutes": 600, "games": 1, "league": "feb", "pts": 0}], {})
    assert all(row[f] == 0 for f in ADVANCED_FIELDS)


def test_nothing_in_nothing_out_and_a_second_run_changes_nothing():
    assert add_advanced([], {}) == []
    payload, rows = _rows("LEAGUE", build_games())
    assert add_advanced(season_player_rows([("g", payload)]), team_context(payload["team_rows"])) == rows
