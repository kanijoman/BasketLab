"""Build a PreparationPackage from stored games.

Baselines are computed with the SAME engine used live (``LiveEngine``), so stints, minutes
and Four Factors are defined identically on both sides. This module is a pure function over
game documents; ``db_source`` reads them from MongoDB.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from src.live_core.engine import LiveEngine
from src.live_core.four_factors import DEFAULT_SD, WEIGHTS, differentials, possessions
from src.live_core.package import PreparationPackage
from src.live_core.profiles import (
    League,
    league_distribution,
    raw_rates,
    shrink_rates,
    z_scores,
)
from src.live_core.state import PLAYER_STAT_KEYS

FEATURE_MIN_GAMES_FOR_SPREAD = 8   # samples needed before trusting a league spread
MIN_GAMES_FOR_P90 = 5
PRIOR_SHRINK_GAMES = 6             # prior weight: games / (games + 6)
SPREAD_FLOOR = 0.5                 # never below half of the default spread
GAME_SECONDS = 2400
MIN_LEAGUE_SECONDS = 300           # players below this do not shape the league distribution


def league_spread(samples: List[Dict[str, float]]) -> Dict[str, float]:
    """Standard deviation of single-game differentials per factor ({} when too few samples)."""
    if len(samples) < FEATURE_MIN_GAMES_FOR_SPREAD:
        return {}
    out = {}
    for factor in WEIGHTS:
        values = [s[factor] for s in samples]
        mean = sum(values) / len(values)
        sd = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
        out[factor] = round(max(sd, SPREAD_FLOOR * DEFAULT_SD[factor]), 4)
    return out


def _mean(samples: List[Dict[str, float]]) -> Dict[str, float]:
    return {f: (sum(s[f] for s in samples) / len(samples) if samples else 0.0) for f in WEIGHTS}


def matchup_prior(own: List[Dict[str, float]], rival: List[Dict[str, float]]) -> Dict[str, float]:
    """Expected differential own-vs-rival: strength gap shrunk by how much data backs it."""
    own_mean, rival_mean = _mean(own), _mean(rival)
    games = min(len(own), len(rival)) if rival else len(own)
    weight = games / (games + PRIOR_SHRINK_GAMES) if games else 0.0
    return {f: round((own_mean[f] - rival_mean[f]) * weight, 4) for f in WEIGHTS}


def _percentile(values: List[int], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


class _PlayerAcc:
    def __init__(self, name: str, team_id: str) -> None:
        self.name, self.team_id = name, team_id
        self.minutes: List[int] = []
        self.stint_sum = self.stints = self.pf = 0
        self.stats = {k: 0 for k in PLAYER_STAT_KEYS}

    def add(self, p: Dict[str, Any]) -> None:
        if p["minutes"] <= 0:
            return
        self.minutes.append(p["minutes"])
        self.pf += p["pf"]
        for key in PLAYER_STAT_KEYS:
            self.stats[key] += p["stats"][key]
        self.stint_sum += p["stint_sum"] + (p["stint"] if p["on_court"] else 0)
        self.stints += p["stints_done"] + (1 if p["on_court"] else 0)

    def baseline(self, league: "League") -> Dict[str, Any]:
        total = sum(self.minutes)
        rates = raw_rates(self.stats, total)
        fga = self.stats["fg2a"] + self.stats["fg3a"]
        shrunk = shrink_rates(rates, total, fga, league)
        return {
            "rates": {k: round(v, 3) for k, v in shrunk.items()},
            "z": {k: round(v, 3) for k, v in z_scores(shrunk, league).items()},
            "seconds": total, "fga": fga,
            "name": self.name, "team_id": self.team_id, "games": len(self.minutes),
            "avg_min": round(total / len(self.minutes)),
            "p90_min": round(_percentile(self.minutes, 0.9)) if len(self.minutes) >= MIN_GAMES_FOR_P90 else None,
            "avg_stint": round(self.stint_sum / self.stints) if self.stints else None,
            "stints": self.stints,
            "pf_per40": round(self.pf / total * GAME_SECONDS, 2) if total else 0.0,
        }


def build_package(
    games: Iterable[Dict[str, Any]],
    collection: str,
    season: str,
    team_id: str,
    rival_id: str,
    competition_meta: Optional[Dict[str, Any]] = None,
    created_at: Optional[str] = None,
) -> PreparationPackage:
    team_id, rival_id = str(team_id), str(rival_id)
    accs: Dict[str, Dict[str, _PlayerAcc]] = {team_id: {}, rival_id: {}}
    names: Dict[str, str] = {}
    diffs: Dict[str, List[Dict[str, float]]] = {team_id: [], rival_id: []}
    league: List[Dict[str, float]] = []
    paces: List[float] = []
    played = {team_id: 0, rival_id: 0}
    league_players: Dict[str, _PlayerAcc] = {}
    total_games = 0

    for game in games:
        header_teams = [(str(t["id"]), (t.get("name") or str(t["id"])).strip()) for t in game["HEADER"]["TEAM"]]
        ids = [tid for tid, _ in header_teams]
        if len(ids) != 2:
            continue
        total_games += 1
        names.update(dict(header_teams))
        snap = LiveEngine().update(game)
        stats = {tid: snap["teams"][tid]["stats"] for tid in ids}
        league.append(differentials(stats[ids[0]], stats[ids[1]]))
        for pid, p in snap["players"].items():
            league_players.setdefault(pid, _PlayerAcc(p["name"], str(p["team_id"]))).add(p)

        for tid in (team_id, rival_id):
            if tid not in ids:
                continue
            other = ids[1] if ids[0] == tid else ids[0]
            played[tid] += 1
            diffs[tid].append(differentials(stats[tid], stats[other]))
            if snap["elapsed"]:
                n = (possessions(stats[tid]) + possessions(stats[other])) / 2
                paces.append(n / snap["elapsed"] * GAME_SECONDS)
            for pid, p in snap["players"].items():
                if p["team_id"] == tid:
                    accs[tid].setdefault(pid, _PlayerAcc(p["name"], tid)).add(p)

    baselines: Dict[str, Any] = {
        "four_factors_prior": matchup_prior(diffs[team_id], diffs[rival_id]),
        "sample_games": {"own": played[team_id], "rival": played[rival_id], "league": total_games},
    }
    spread = league_spread(league)
    if spread:
        baselines["four_factors_sd"] = spread
    if paces:
        baselines["pace_per_40"] = round(sum(paces) / len(paces), 1)

    population = [
        raw_rates(a.stats, sum(a.minutes)) for a in league_players.values() if sum(a.minutes) >= MIN_LEAGUE_SECONDS
    ]
    league_rates = league_distribution(population)
    baselines["league_rates"] = {m: {k: round(v, 4) for k, v in d.items()} for m, d in league_rates.items()}

    def table(tid: str) -> Dict[str, Dict[str, Any]]:
        return {pid: acc.baseline(league_rates) for pid, acc in accs[tid].items() if acc.minutes}

    return PreparationPackage(
        collection=collection, season=season,
        team={"id": team_id, "name": names.get(team_id, team_id)},
        rival={"id": rival_id, "name": names.get(rival_id, rival_id)},
        tables={"players": table(team_id), "rival_players": table(rival_id),
                "lineups": [], "roles": [], "zones": {}},
        created_at=created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        competition_meta=competition_meta or {},
        baselines=baselines,
    )
