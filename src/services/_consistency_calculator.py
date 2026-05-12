"""Consistency (CV) calculator helpers — extracted from team_stats_service.py.

Provides module-level functions to build per-team coefficient-of-variation maps
and compute derived dispersion indexes.  Used by TeamStatsService.get_consistency
for both FEB and FBCYL collections.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

import numpy as np


def build_cv_map(rows: List[Dict], field_map: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Accumulate per-game values for each team and compute mean / std / CV.

    Args:
        rows:       Per-game raw documents (one dict per game-team pair).
        field_map:  Mapping of ``{stat_key: raw_field_in_row}``.

    Returns:
        ``{team_name: {stat_key: {"mean", "std", "cv", "n"}}}``
        Teams or stat keys with fewer than 3 observations are omitted.
    """
    by_team: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        team = row.get("team_name")
        if not team:
            continue
        for stat_key, raw_field in field_map.items():
            val = row.get(raw_field)
            if val is not None:
                try:
                    by_team[team][stat_key].append(float(val))
                except (TypeError, ValueError):
                    pass

    result: Dict[str, Dict[str, Any]] = {}
    for team, stats in by_team.items():
        result[team] = {}
        for stat_key, values in stats.items():
            if len(values) < 3:
                continue
            arr = np.array(values)
            mean = float(np.mean(arr))
            std = float(np.std(arr))
            # Use abs(mean) with a floor to avoid absurd CV for signed/near-zero
            # metrics (e.g. net_rating).  Cap at 200% so edge cases don't
            # produce misleading badge values.
            cv = (std / abs(mean) * 100) if abs(mean) >= 1.0 else 0.0
            cv = min(cv, 200.0)
            result[team][stat_key] = {
                "mean": round(mean, 2),
                "std":  round(std, 2),
                "cv":   round(cv, 1),
                "n":    len(values),
            }
    return result


def add_derived_indexes(own_map: Dict[str, Dict[str, Any]]) -> None:
    """Compute per-team derived dispersion indexes and append them in-place.

    Two indexes are added per team:

    * **volatilidad_triple** — ``std(3PT%) × mean(fg3_attempts_per_game)``.
    * **sostenibilidad_efg** — ``mean(eFG%) − league_mean_eFG``.
    """
    efg_means = [
        v["efg_percentage"]["mean"]
        for v in own_map.values()
        if "efg_percentage" in v
    ]
    league_efg = float(np.mean(efg_means)) if efg_means else None

    for team, stats in own_map.items():
        fg3_pct = stats.get("fg3_percentage", {})
        fg3_vol = stats.get("fg3_attempts_per_game", {})
        if fg3_pct.get("std") is not None and fg3_vol.get("mean") is not None:
            stats["volatilidad_triple"] = {
                "value": round(fg3_pct["std"] * fg3_vol["mean"], 2),
                "n":     min(fg3_pct.get("n", 0), fg3_vol.get("n", 0)),
            }
        efg = stats.get("efg_percentage", {})
        if efg.get("mean") is not None and league_efg is not None:
            stats["sostenibilidad_efg"] = {
                "value": round(efg["mean"] - league_efg, 2),
                "n":     efg.get("n", 0),
            }


# Field maps shared between FEB and FBCYL consistency calculations.
# Exported so callers can inspect or extend them without editing this module.

OWN_FIELD_MAP: Dict[str, str] = {
    "points_per_game":             "points",
    "points_against_per_game":     "opponent_points",
    "fg3_percentage":              "fg3_pct_game",
    "fg2_percentage":              "fg2_pct_game",
    "ft_percentage":               "ft_pct_game",
    "fg3_attempts_per_game":       "fg3_attempts",
    "rebounds_per_game":           "total_rebounds",
    "offensive_rebounds_per_game": "off_rebounds",
    "defensive_rebounds_per_game": "def_rebounds",
    "assists_per_game":            "assists",
    "steals_per_game":             "steals",
    "turnovers_per_game":          "turnovers",
    "blocks_per_game":             "blocks",
    "possessions_per_game":        "possessions",
    "offensive_rating":            "oer_game",
    "oer":                         "oer_game",
    "defensive_rating":            "der_game",
    "der":                         "der_game",
    "net_rating":                  "net_game",
    "efg_percentage":              "efg_pct_game",
    "true_shooting":               "ts_pct_game",
    "turnover_rate":               "tov_pct_game",
    "three_point_rate":            "three_point_rate_game",
    "free_throw_rate":             "free_throw_rate_game",
    "assist_fg_rate":              "assist_fg_rate_game",
    "assist_rate":                 "assist_rate_game",
    "steal_rate":                  "steal_rate_game",
    "block_rate":                  "block_rate_game",
    "offensive_rebound_rate":      "oreb_rate_game",
    "defensive_rebound_rate":      "dreb_rate_game",
}

RIVAL_FIELD_MAP: Dict[str, str] = {
    "points_per_game":             "opponent_points",
    "points_against_per_game":     "points",
    "fg3_percentage":              "opp_fg3_pct_game",
    "fg2_percentage":              "opp_fg2_pct_game",
    "ft_percentage":               "opp_ft_pct_game",
    "rebounds_per_game":           "opp_total_rebounds",
    "offensive_rebounds_per_game": "opp_off_rebounds",
    "defensive_rebounds_per_game": "opp_def_rebounds",
    "assists_per_game":            "opp_assists",
    "steals_per_game":             "opp_steals",
    "turnovers_per_game":          "opp_turnovers",
    "blocks_per_game":             "opp_blocks",
    "possessions_per_game":        "opp_possessions",
    "offensive_rating":            "opp_oer_game",
    "defensive_rating":            "opp_der_game",
    "net_rating":                  "opp_net_game",
    "efg_percentage":              "opp_efg_pct_game",
    "true_shooting":               "opp_ts_pct_game",
    "turnover_rate":               "opp_tov_pct_game",
    "three_point_rate":            "opp_three_point_rate_game",
    "free_throw_rate":             "opp_free_throw_rate_game",
    "assist_fg_rate":              "opp_assist_fg_rate_game",
    "assist_rate":                 "opp_assist_rate_game",
    "steal_rate":                  "opp_steal_rate_game",
    "block_rate":                  "opp_block_rate_game",
    "offensive_rebound_rate":      "opp_orb_rate_game",
    "defensive_rebound_rate":      "opp_drb_rate_game",
}

FBCYL_OWN_FIELD_MAP: Dict[str, str] = {
    "points_per_game":             "points",
    "points_against_per_game":     "opponent_points",
    "fg3_percentage":              "fg3_pct_game",
    "fg2_percentage":              "fg2_pct_game",
    "ft_percentage":               "ft_pct_game",
    "fg3_attempts_per_game":       "fg3_attempts",
    "rebounds_per_game":           "total_rebounds",
    "offensive_rebounds_per_game": "off_rebounds",
    "defensive_rebounds_per_game": "def_rebounds",
    "assists_per_game":            "assists",
    "steals_per_game":             "steals",
    "turnovers_per_game":          "turnovers",
    "blocks_per_game":             "blocks",
    "possessions_per_game":        "possessions",
    "offensive_rating":            "oer_game",
    "oer":                         "oer_game",
    "defensive_rating":            "der_game",
    "der":                         "der_game",
    "net_rating":                  "net_game",
    "efg_percentage":              "efg_pct_game",
    "true_shooting":               "ts_pct_game",
    "turnover_rate":               "tov_pct_game",
    "three_point_rate":            "three_point_rate_game",
    "free_throw_rate":             "free_throw_rate_game",
    "assist_fg_rate":              "assist_fg_rate_game",
    "assist_rate":                 "assist_rate_game",
    "steal_rate":                  "steal_rate_game",
    "block_rate":                  "block_rate_game",
    "offensive_rebound_rate":      "oreb_rate_game",
    "defensive_rebound_rate":      "dreb_rate_game",
}

FBCYL_RIVAL_FIELD_MAP: Dict[str, str] = {
    "points_per_game":             "opp_points",
    "points_against_per_game":     "points",
    "fg3_percentage":              "opp_fg3_pct_game",
    "fg2_percentage":              "opp_fg2_pct_game",
    "ft_percentage":               "opp_ft_pct_game",
    "rebounds_per_game":           "opp_total_rebounds",
    "offensive_rebounds_per_game": "opp_off_rebounds",
    "defensive_rebounds_per_game": "opp_def_rebounds",
    "assists_per_game":            "opp_assists",
    "steals_per_game":             "opp_steals",
    "turnovers_per_game":          "opp_turnovers",
    "blocks_per_game":             "opp_blocks",
    "possessions_per_game":        "opp_possessions",
    "offensive_rating":            "opp_oer_game",
    "defensive_rating":            "opp_der_game",
    "net_rating":                  "opp_net_game",
    "efg_percentage":              "opp_efg_pct_game",
    "true_shooting":               "opp_ts_pct_game",
    "turnover_rate":               "opp_tov_pct_game",
    "three_point_rate":            "opp_three_point_rate_game",
    "free_throw_rate":             "opp_free_throw_rate_game",
    "assist_fg_rate":              "opp_assist_fg_rate_game",
    "assist_rate":                 "opp_assist_rate_game",
    "steal_rate":                  "opp_steal_rate_game",
    "block_rate":                  "opp_block_rate_game",
    "offensive_rebound_rate":      "opp_orb_rate_game",
    "defensive_rebound_rate":      "opp_drb_rate_game",
}
