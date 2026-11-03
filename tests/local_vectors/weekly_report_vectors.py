"""The vectors of the weekly report in the browser (#716, step D4a): what the row builders of ``_weekly_report_helpers`` say of a set of figures, the reference of
``frontend/src/lib/weeklyRows.test.ts``. The rows (text and cell colour), not the pixels: the tables are drawn by the browser.

The inputs are the team and player tables of the sample leagues plus a league of awkward floats (many decimals, ties, missing figures, zero games) so the formats and the
quartile thresholds are checked to the last digit.
"""
import json
import random
from pathlib import Path
from typing import Any, Dict, List

from src.services import _weekly_report_helpers as h

HERE = Path(__file__).resolve().parent
TEAM_KEYS = [f for f, _ in h.BASIC_FIELDS + h.ADV_FIELDS]
PLAYER_KEYS = ["points_per_game", "fg1_percentage", "fg2_percentage", "fg3_percentage", "rebounds_per_game", "assists_per_game", "steals_per_game", "turnovers_per_game",
               "blocks_per_game", "pllss_per_game", "valoracion_per_game", "minutes_per_game"]


def _awkward_teams(seed: int = 716) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    teams = []
    for i in range(12):
        row: Dict[str, Any] = {"team_id": str(i), "_id": str(i), "team_name": f"Equipo {i}", "total_games": rng.randint(0, 30), "games_home": rng.randint(0, 15), "games_away": rng.randint(0, 15)}
        for key in TEAM_KEYS:
            row[key] = None if (i + len(key)) % 8 == 0 else (rng.choice((50.0, 12.5, 0.0)) if i % 4 == 0 else rng.uniform(0, 120) / rng.choice((1, 3, 7)))
        teams.append(row)
    return teams


def _awkward_players(seed: int = 717) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    players = []
    for i in range(13):
        row: Dict[str, Any] = {"player_id": str(i), "player_name": f"Jugadora {i}", "games_played": rng.choice((0, 1, 7, 28)), "minutes_per_game": rng.choice((0, 0.0, 9.999, 31.25, 1 / 3))}
        for key in PLAYER_KEYS[:-1]:
            row[key] = rng.choice((0, 12.5, 50.0)) if i % 5 == 0 else rng.uniform(0, 30) / rng.choice((1, 3, 7))
        for key in ("total_pts", "total_ro", "total_rd", "total_rt", "total_assist", "total_st", "total_to", "total_bs", "total_pf", "total_rf", "total_pllss", "total_val"):
            row[key] = rng.randint(0, 300)
        row["pllss_per_game"] = rng.uniform(0, 4)
        row["valoracion_per_game"] = rng.uniform(-3, 25)
        players.append(row)
    return players


def _comparative(teams: List[Dict[str, Any]], seed: int = 5) -> List[Dict[str, Any]]:
    """The pairs the service builds with ``create_comparative_stat``: the stretch, and the rest of the season it is compared with."""
    rng = random.Random(seed)
    pairs = []
    for team in teams:
        rest = dict(team)
        for key in TEAM_KEYS:
            if team.get(key) is not None and rng.random() < 0.9:
                rest[key] = team[key] + rng.choice((0, 0.04, -0.04, 0.05, 2.25, -7.5, 0.0049))
        rest["total_games"] = rng.randint(0, 25)
        pairs.append({"_id": team["_id"], "team_name": team["team_name"], "monthly": team, "rest": rest})
    return pairs


def _consistency(teams: List[Dict[str, Any]], seed: int = 9) -> Dict[str, Dict[str, Any]]:
    rng = random.Random(seed)
    own: Dict[str, Dict[str, Any]] = {}
    for team in teams:
        stats: Dict[str, Any] = {}
        for _, key, _ in h._CONSISTENCY_KEYS:
            if rng.random() < 0.85:
                stats[key] = {"cv": rng.choice((0.0, 12.5, 15.0, 30.0)) if rng.random() < 0.3 else rng.uniform(1, 60), "n": rng.randint(1, 30)}
        own[team["team_name"]] = stats
    return own


def _pairs(rows):
    texts, colors = rows
    return {"texts": texts, "colors": colors}


def _league(name: str, teams: List[Dict[str, Any]], players: List[Dict[str, Any]]) -> Dict[str, Any]:
    comp = _comparative(teams)
    out: Dict[str, Any] = {"name": name, "teams": teams, "players": players, "comparative": comp, "consistency": _consistency(teams)}
    out["basic"] = {str(inv): _pairs(h.build_basic_rows(teams, invert_colors=inv)) for inv in (False, True)}
    out["advanced"] = {str(inv): _pairs(h.build_advanced_rows(teams, invert_colors=inv)) for inv in (False, True)}
    out["comparative_basic"] = {str(inv): _pairs(h.build_comparative_basic_rows(comp, invert_colors=inv)) for inv in (False, True)}
    out["comparative_advanced"] = {str(inv): _pairs(h.build_comparative_advanced_rows(comp, invert_colors=inv)) for inv in (False, True)}
    out["player_rows"] = {}
    for mode in ("avg", "total", "projection"):
        headers, texts, colors = h.build_player_rows(players, mode)
        out["player_rows"][mode] = {"headers": headers, "texts": texts, "colors": colors}
    out["consistency_rows"] = _pairs(h.build_consistency_rows(out["consistency"]))
    if len(teams) >= 2:
        out["last_match"] = _pairs(h.build_last_match_rows(teams[0], teams[1], teams[2], teams[3], teams[0]["team_name"], teams[1]["team_name"]))
    return out


def build() -> Dict[str, Any]:
    sample = json.loads((HERE / "team_stats_feb.json").read_text(encoding="utf-8"))["cases"][0]["team_stats"]
    sample_players = json.loads((HERE / "players_feb.json").read_text(encoding="utf-8"))["cases"][0]["players"]
    leagues = [_league("sample", sample, sample_players), _league("awkward", _awkward_teams(), _awkward_players()), _league("empty", [], [])]
    return {
        "headers": {"basic": h.BASIC_HEADERS, "advanced": h.ADV_HEADERS, "last_match": h.LAST_MATCH_ADV_HEADERS, "consistency": h.CONSISTENCY_HEADERS},
        "leagues": leagues,
    }
