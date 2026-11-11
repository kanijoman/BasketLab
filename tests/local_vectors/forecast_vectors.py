"""Parity vectors of the browser forecast (#846): the Python reference answers, the TypeScript port (``frontend/src/forecast``) must give the same.

The preview of a match and the simulation of a league are computed in the browser (#841), but the models they live on are the ones the live engine validated: the Bayesian (Kalman) rating of
the teams (``live_prep.team_rating``), the win probability at tip-off (``live_core.win_prob``, with ``WP_BY_GENDER``) and the four factors (``live_core.four_factors``, ``shrunk_team_level``).
Nothing here re-implements them: every expected value comes from calling the real code, over the REAL rows of the fixture leagues (``export_collection``: FEB and FBCYL), so a change in the
Python side shows up as a diff of ``forecast.json`` (``test_forecast_vectors.py``) and then as a failure of the vitest suite until the port follows.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import mongomock

sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[2] / "src"), str(Path(__file__).resolve().parent)]

import fbcyl_games  # noqa: E402
import games  # noqa: E402

from src.live_core.config import WP_BY_GENDER, RuleConfig  # noqa: E402
from src.live_core.four_factors import FT_POSSESSION_COST, WEIGHTS, factors, points_per_unit  # noqa: E402
from src.live_core.win_prob import DEFAULT_PACE_PER_40, WinProbabilityModel  # noqa: E402
from src.live_prep import team_rating  # noqa: E402
from src.live_prep.package_builder import PRIOR_SHRINK_GAMES, shrunk_team_level  # noqa: E402
from src.live_prep.team_rating import TeamRatings  # noqa: E402
from src.local_data.export import export_collection  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
GENDERS = ("F", "M", "")
COURTS = ("own", "rival", "neutral")           # who plays at home: the own team, the rival, nobody
PACES = (0.0, 64.5, 70.0, 78.2)                # 0: no pace known (the package then carries none and the model assumes 70)
OWN_STATS = {"fg2m": "fg2_made", "fg2a": "fg2_attempts", "fg3m": "fg3_made", "fg3a": "fg3_attempts", "ftm": "ft_made", "fta": "ft_attempts", "orb": "off_rebounds", "drb": "def_rebounds",
             "tov": "turnovers", "pts": "points"}
OPP_STATS = {key: ("opponent_" + field if field != "points" else "opponent_points") for key, field in OWN_STATS.items()}


def _rows(name: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    collection = mongomock.MongoClient()["BASKETBALL"][name]
    collection.insert_many(docs)
    return export_collection(collection, name)["team_rows"]


def _erf_grid() -> List[List[float]]:
    """``math.erf`` over the whole range (the win probability is ``0.5 * (1 + erf(z / sqrt 2))``), the edges of its pieces included."""
    edges = [1e-30, 2.0 ** -28, 0.1, 0.84375 - 1e-9, 0.84375, 1.25 - 1e-9, 1.25, 2.857142857142857, 2.9, 5.999999, 6.0, 8.0]
    xs = [k * 0.125 for k in range(-56, 57)] + edges + [-e for e in edges]
    return [[x, math.erf(x)] for x in xs]


def box(row: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, int]:
    """The stat totals of one side of a game row in the keys the live engine uses (what the browser's ``boxOf`` must give too)."""
    return {key: int(row[field]) for key, field in mapping.items()}


def _sequence(docs: List[Dict[str, Any]], fbcyl: bool) -> List[Tuple[str, str, int]]:
    """``(home, away, margin)`` of each game in order: the home team is the first one of the document."""
    out = []
    for doc in docs:
        if fbcyl:
            home, away = doc["stats"]["teams"][:2]
            out.append((str(home["teamIdExtern"]), str(away["teamIdExtern"]), int(home["data"]["score"]) - int(away["data"]["score"])))
        else:
            home, away = doc["HEADER"]["TEAM"]
            out.append((str(home["id"]), str(away["id"]), int(home["pts"]) - int(away["pts"])))
    return out


def _ratings_vectors(sequence: List[Tuple[str, str, int]]) -> Tuple[Dict[str, Any], TeamRatings]:
    ratings, steps = TeamRatings(), []
    for home, away, margin in sequence:
        ratings.update(home, away, margin)
        teams = sorted({t for h, a, _ in sequence for t in (h, a)})
        steps.append({"home": home, "away": away, "margin": margin, "home_advantage": ratings.home_advantage(),
                      "after": {t: {"mean": ratings.rating(t), "var": ratings.variance(t)} for t in teams}})
    return {"steps": steps}, ratings


def _snapshot(own: str, rival: str, court: str) -> Dict[str, Any]:
    home = {"own": own, "rival": rival}.get(court)
    return {"home_id": home, "score": {own: 0, rival: 0}, "elapsed": 0}


def _headline(ratings: TeamRatings, own: str, rival: str, gender: str, court: str, pace: float) -> Dict[str, Any]:
    """The win probability at tip-off exactly as the package and the engine produce it: the rounded ``net_rtg_prior`` of the matchup at its pace and the home court of the family."""
    prior = round(ratings.gap_per_100(own, rival, pace), 3)
    baselines: Dict[str, Any] = {"net_rtg_prior": prior}
    if pace:
        baselines["pace_per_40"] = pace
    config = RuleConfig.from_dict({"gender": gender} if gender else {})
    result = WinProbabilityModel(own, rival, baselines, config).evaluate(_snapshot(own, rival, court), None)
    return {"own": own, "rival": rival, "gender": gender, "court": court, "pace": pace, "gap100": prior, **{k: result[k] for k in ("p", "projected_margin", "sd", "poss_remaining", "mu_per_100")}}


def _gaps(ratings: TeamRatings, teams: List[str]) -> List[Dict[str, Any]]:
    return [{"own": a, "rival": b, "pace": pace, "gap100": ratings.gap_per_100(a, b, pace)} for a in teams for b in teams if a != b for pace in (0.0, 66.3, 70.0, -5.0)]


def _factor_cases(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        own, opp = box(row, OWN_STATS), box(row, OPP_STATS)
        out.append({"row": row, "own": own, "opp": opp, "factors": factors(own, opp), "per_unit": points_per_unit(own)})
    return out


def _levels(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The season level of each team over these rows (what the package's ``team_levels`` is made of), through the real ``shrunk_team_level``."""
    keys = list(OWN_STATS)
    league_sums = {k: sum(box(r, OWN_STATS)[k] for r in rows) for k in keys}
    league = factors(league_sums, league_sums)
    teams: Dict[str, Any] = {}
    for tid in sorted({str(r["team_id"]) for r in rows}):
        mine = [r for r in rows if str(r["team_id"]) == tid]
        sums = {"for": {k: sum(box(r, OWN_STATS)[k] for r in mine) for k in keys}, "against": {k: sum(box(r, OPP_STATS)[k] for r in mine) for k in keys}}
        teams[tid] = {"games": len(mine), "level": shrunk_team_level(sums, league, len(mine))}
    return {"league": league, "teams": teams}


def _competition(name: str, docs: List[Dict[str, Any]], fbcyl: bool) -> Dict[str, Any]:
    rows = _rows(name, docs)
    steps, ratings = _ratings_vectors(_sequence(docs, fbcyl))
    teams = sorted({r["team_id"] if isinstance(r["team_id"], str) else str(r["team_id"]) for r in rows})
    pairs = [(teams[0], teams[1]), (teams[2], teams[3]), (teams[3], teams[0]), ("999", teams[0])]
    return {"collection": name, "league": "fbcyl" if fbcyl else "feb", "ratings": steps, "gaps": _gaps(ratings, teams + ["999"]),
            "headline": [_headline(ratings, a, b, g, c, p) for a, b in pairs for g in GENDERS for c in COURTS for p in PACES],
            "factors": _factor_cases(rows), "levels": _levels(rows)}


def build() -> Dict[str, Any]:
    config = {g: RuleConfig.from_dict({"gender": g} if g else {}) for g in GENDERS}
    return {
        "constants": {
            "team_ratings": {"P0": team_rating.P0, "Q_GAME": team_rating.Q_GAME, "NOISE": team_rating.NOISE, "HOME_PRIOR": team_rating.HOME_PRIOR, "HOME_WEIGHT": team_rating.HOME_WEIGHT,
                             "DEFAULT_PACE": team_rating.DEFAULT_PACE, "DEFAULT_PACE_PER_40": DEFAULT_PACE_PER_40},
            "win_prob": {g or "default": {"sigma": c.wp_sigma, "home_adv": c.wp_home_adv} for g, c in config.items()},
            "wp_by_gender": WP_BY_GENDER,
            "four_factors": {"weights": WEIGHTS, "shrink_games": PRIOR_SHRINK_GAMES, "ft_possession_cost": FT_POSSESSION_COST},
        },
        "erf": _erf_grid(),
        "own_stats": OWN_STATS, "opp_stats": OPP_STATS,
        "competitions": [_competition(FEB, games.build_games(), False), _competition(FBCYL, fbcyl_games.build_games(), True)],
    }
