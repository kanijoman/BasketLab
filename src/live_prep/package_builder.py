"""Build a PreparationPackage from stored games.

Baselines are computed with the SAME engine used live (``LiveEngine``), so stints, minutes
and Four Factors are defined identically on both sides. This module is a pure function over
game documents; ``db_source`` reads them from MongoDB.
"""

from __future__ import annotations

import copy
import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.live_core.engine import LiveEngine
from src.live_core.four_factors import DEFAULT_SD, WEIGHTS, differentials, possessions
from src.live_core.package import PreparationPackage
from src.live_core.profiles import (
    League,
    impact_league,
    impact_rates,
    league_distribution,
    raw_rates,
    shrink_impact,
    shrink_rates,
    z_scores,
)
from src.live_core import clutch as clutch_mod
from src.live_core.lineups import season_table
from src.live_core.state import PLAYER_STAT_KEYS

FEATURE_MIN_GAMES_FOR_SPREAD = 8   # samples needed before trusting a league spread
MIN_GAMES_FOR_P90 = 5
LINEUPS_PER_TEAM = 30     # quintets per team in tables.lineups (the most played ones; the package must stay small)
FT_PRIOR_ATTEMPTS = 10    # free-throw attempts of weight the league mean has when shrinking a player's percentage
DEFAULT_FT_PCT = 0.72     # league mean when nobody has attempted a free throw yet (placeholder)
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
        self.clutch, self.q4 = clutch_mod.empty(), clutch_mod.empty()

    def add(self, p: Dict[str, Any]) -> None:
        if p["minutes"] <= 0:
            return
        self.minutes.append(p["minutes"])
        self.pf += p["pf"]
        for key in PLAYER_STAT_KEYS:
            self.stats[key] += p["stats"][key]
        for bucket, key in ((self.clutch, "clutch"), (self.q4, "q4")):
            for field in clutch_mod.FIELDS:
                bucket[field] += (p.get(key) or {}).get(field, 0)      # snapshots of an older engine have no clutch totals
        self.stint_sum += p["stint_sum"] + (p["stint"] if p["on_court"] else 0)
        self.stints += p["stints_done"] + (1 if p["on_court"] else 0)

    def baseline(self, league: "League", impact_means: Dict[str, float], ft_mean: float = 0.0) -> Dict[str, Any]:
        total = sum(self.minutes)
        rates = raw_rates(self.stats, total)
        fga = self.stats["fg2a"] + self.stats["fg3a"]
        shrunk = shrink_rates(rates, total, fga, league)
        impact = shrink_impact(impact_rates(self.stats, total), total, impact_means)
        return {
            "rates": {k: round(v, 3) for k, v in shrunk.items()},
            "impact40": {k: round(v, 3) for k, v in impact.items()},
            "z": {k: round(v, 3) for k, v in z_scores(shrunk, league).items()},
            "seconds": total, "fga": fga,
            "name": self.name, "team_id": self.team_id, "games": len(self.minutes),
            "avg_min": round(total / len(self.minutes)),
            "p90_min": round(_percentile(self.minutes, 0.9)) if len(self.minutes) >= MIN_GAMES_FOR_P90 else None,
            "avg_stint": round(self.stint_sum / self.stints) if self.stints else None,
            "stints": self.stints,
            "pf_per40": round(self.pf / total * GAME_SECONDS, 2) if total else 0.0,
            # free throws (issue #246): attempts and the percentage shrunk to the league mean, so a 1/1 night is not 100 %
            "fta": self.stats["fta"],
            "ft_pct": round((self.stats["ftm"] + FT_PRIOR_ATTEMPTS * ft_mean) / (self.stats["fta"] + FT_PRIOR_ATTEMPTS), 3),
            "clutch": self._clutch(total, ft_mean),
        }

    def _clutch(self, total: int, ft_mean: float) -> Dict[str, Any]:
        """Responsibility and accuracy in a close finish, shrunk to this player's season (issue #274; see ``live_core.clutch``)."""
        s = self.stats
        shots = s["fg2a"] + s["fg3a"] + clutch_mod.FT_POSSESSION_COST * s["fta"]
        points = 2 * s["fg2m"] + 3 * s["fg3m"] + s["ftm"]
        return clutch_mod.summarize(
            self.clutch, self.q4,
            usage_per10=(shots + s["tov"]) / total * 600 if total else 0.0,
            pps_season=points / shots if shots else 0.0,
            ft_pct_season=(s["ftm"] + FT_PRIOR_ATTEMPTS * ft_mean) / (s["fta"] + FT_PRIOR_ATTEMPTS))


class SeasonAccumulator:
    """What a package needs, accumulated while stored games are replayed through LiveEngine.

    It tracks EVERY team (or only those in ``track``, to save memory), so one pass over the season gives the
    package of any pair of teams as it would have been after the games added so far (``to_package``). The rule
    evaluator relies on that; ``build_package`` is the one-pair wrapper.
    """

    def __init__(self, track: Optional[Iterable[str]] = None) -> None:
        self._track = {str(t) for t in track} if track is not None else None
        self.players: Dict[str, Dict[str, _PlayerAcc]] = {}
        self.league_players: Dict[str, _PlayerAcc] = {}
        self.names: Dict[str, str] = {}
        self.diffs: Dict[str, List[Dict[str, float]]] = {}
        self.league_diffs: List[Dict[str, float]] = []
        self.lineup_totals: Dict[str, Dict[Tuple[str, ...], Dict[str, int]]] = {}   # team -> quintet -> season totals (#248)
        self.team_threes: Dict[str, List[int]] = {}   # team -> [three-point attempts, field-goal attempts] over the season (#291)
        self.pace_log: List[Tuple[Tuple[str, str], float]] = []  # (the two team ids, game pace) in game order
        self._played: Dict[str, int] = {}
        self.zone_league: Dict[str, Dict[str, int]] = {}
        self.zone_team: Dict[str, Dict[str, Dict[str, int]]] = {}
        self.total_games = 0

    def tracked(self, team_id: str) -> bool:
        return self._track is None or team_id in self._track

    def played(self, team_id: str) -> int:
        return self._played.get(team_id, 0)

    def add_game(self, game: Dict[str, Any]) -> None:
        header = [(str(t["id"]), (t.get("name") or str(t["id"])).strip()) for t in game["HEADER"]["TEAM"]]
        ids = [tid for tid, _ in header]
        if len(ids) != 2:
            return
        self.total_games += 1
        self.names.update(dict(header))
        snap = LiveEngine().update(game)
        stats = {tid: snap["teams"][tid]["stats"] for tid in ids}
        self.league_diffs.append(differentials(stats[ids[0]], stats[ids[1]]))
        for pid, p in snap["players"].items():
            self.league_players.setdefault(pid, _PlayerAcc(p["name"], str(p["team_id"]))).add(p)
        for tid in ids:
            self._add_zones(self.zone_league, snap["zones"].get(tid, {}))
        if snap["elapsed"] and any(self.tracked(tid) for tid in ids):
            n = (possessions(stats[ids[0]]) + possessions(stats[ids[1]])) / 2
            self.pace_log.append(((ids[0], ids[1]), n / snap["elapsed"] * GAME_SECONDS))
        for tid in ids:
            if self.tracked(tid):
                self._add_team(tid, ids[1] if ids[0] == tid else ids[0], snap, stats)

    def _add_team(self, tid: str, other: str, snap: Dict[str, Any], stats: Dict[str, Any]) -> None:
        self._played[tid] = self.played(tid) + 1
        for row in snap["lineups"].get(tid, []):
            total = self.lineup_totals.setdefault(tid, {}).setdefault(
                tuple(row["players"]), {"seconds": 0, "pts_for": 0, "pts_against": 0, "stints": 0, "games": 0})
            for key in ("seconds", "pts_for", "pts_against", "stints"):
                total[key] += row[key]
            total["games"] += 1
        shots = self.team_threes.setdefault(tid, [0, 0])
        shots[0] += stats[tid]["fg3a"]
        shots[1] += stats[tid]["fg2a"] + stats[tid]["fg3a"]
        self.diffs.setdefault(tid, []).append(differentials(stats[tid], stats[other]))
        table = self.players.setdefault(tid, {})
        for pid, p in snap["players"].items():
            if p["team_id"] == tid:
                table.setdefault(pid, _PlayerAcc(p["name"], tid)).add(p)
        self._add_zones(self.zone_team.setdefault(tid, {}), snap["zones"].get(tid, {}))

    @staticmethod
    def _add_zones(target: Dict[str, Dict[str, int]], cells: Dict[str, Dict[str, int]]) -> None:
        for zone, cell in cells.items():
            total = target.setdefault(zone, {"a": 0, "m": 0, "pts": 0})
            for key in total:
                total[key] += cell[key]

    def _paces(self, *team_ids: str) -> List[float]:
        """Pace of each game of the given teams, in game order (a game of two of them counts once per team)."""
        return [pace for ids, pace in self.pace_log for tid in team_ids if tid in ids]

    def _team_baselines(self, team_id: str, rival_id: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "four_factors_prior": matchup_prior(self.diffs.get(team_id, []), self.diffs.get(rival_id, [])),
            "sample_games": {"own": self.played(team_id), "rival": self.played(rival_id), "league": self.total_games},
        }
        spread = league_spread(self.league_diffs)
        if spread:
            out["four_factors_sd"] = spread
        for key, tid in (("fg3_rate_own", team_id), ("fg3_rate_rival", rival_id)):
            threes, attempts = self.team_threes.get(tid, [0, 0])
            if attempts:
                out[key] = round(threes / attempts, 3)     # the share of the shots a team usually takes from three (issue #291)
        paces = self._paces(team_id, rival_id)
        if paces:
            out["pace_per_40"] = round(sum(paces) / len(paces), 1)
        for key, tid in (("pace_own_per_40", team_id), ("pace_rival_per_40", rival_id)):
            own = self._paces(tid)
            if own:
                out[key] = round(sum(own) / len(own), 1)
        return out

    def _league_players_with_minutes(self) -> List[_PlayerAcc]:
        return [a for a in self.league_players.values() if sum(a.minutes) >= MIN_LEAGUE_SECONDS]

    def to_package(self, collection: str, season: str, team_id: str, rival_id: str,
                   competition_meta: Optional[Dict[str, Any]], created_at: Optional[str],
                   roster: Optional[Dict[str, Dict[str, Any]]] = None) -> PreparationPackage:
        """The package of ``team_id`` against ``rival_id`` with the games added so far (nothing is modified).

        ``roster`` (``roster_fetcher``: who is a "formación" player, for both teams) goes into ``tables.roster``;
        without it the package has no such key and is exactly what it was before.
        """
        team_id, rival_id = str(team_id), str(rival_id)
        if not (self.tracked(team_id) and self.tracked(rival_id)):
            raise ValueError("Both teams must be tracked by the accumulator")
        qualified = self._league_players_with_minutes()
        league_rates = league_distribution([raw_rates(a.stats, sum(a.minutes)) for a in qualified])
        impact_means = impact_league([impact_rates(a.stats, sum(a.minutes)) for a in qualified])
        ft_attempts = sum(a.stats["fta"] for a in qualified)
        ft_mean = sum(a.stats["ftm"] for a in qualified) / ft_attempts if ft_attempts else DEFAULT_FT_PCT

        baselines = self._team_baselines(team_id, rival_id)
        baselines["ft_league_pct"] = round(ft_mean, 4)
        baselines["league_rates"] = {m: {k: round(v, 4) for k, v in d.items()} for m, d in league_rates.items()}
        baselines["impact_league"] = {m: round(v, 3) for m, v in impact_means.items()}

        def table(tid: str) -> Dict[str, Dict[str, Any]]:
            return {pid: acc.baseline(league_rates, impact_means, ft_mean)
                    for pid, acc in self.players.get(tid, {}).items() if acc.minutes}

        tables: Dict[str, Any] = {
            "players": table(team_id), "rival_players": table(rival_id), "roles": [],
            "lineups": season_table(self.lineup_totals, team_id, LINEUPS_PER_TEAM) + season_table(self.lineup_totals, rival_id, LINEUPS_PER_TEAM),
            "zones": copy.deepcopy({"league": self.zone_league, "rival": self.zone_team.get(rival_id, {})}),
        }
        if roster:
            tables["roster"] = copy.deepcopy(roster)
        return PreparationPackage(
            collection=collection, season=season,
            team={"id": team_id, "name": self.names.get(team_id, team_id)},
            rival={"id": rival_id, "name": self.names.get(rival_id, rival_id)},
            tables=tables,
            created_at=created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            competition_meta=competition_meta or {},
            baselines=baselines,
        )


def build_package(
    games: Iterable[Dict[str, Any]],
    collection: str,
    season: str,
    team_id: str,
    rival_id: str,
    competition_meta: Optional[Dict[str, Any]] = None,
    created_at: Optional[str] = None,
    roster: Optional[Dict[str, Dict[str, Any]]] = None,
) -> PreparationPackage:
    acc = SeasonAccumulator(track=(str(team_id), str(rival_id)))
    for game in games:
        acc.add_game(game)
    return acc.to_package(collection, season, team_id, rival_id, competition_meta, created_at, roster=roster)
