"""Builders of the per-team possession entries served by ``TeamStatsService.get_possession_stats``.

Pure functions (no database): the service loads the season rows and the play-by-play possession stats, these
build and enrich the entries. Same pattern as ``_consistency_calculator``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Play-by-play derived fields that stay None when the team has no play-by-play data
_PBP_FIELDS = (
    "avg_duration", "pct_fast", "pct_medium", "pct_slow", "oer_fast", "oer_medium", "oer_slow",
    "est_possessions_per_game",
)


def rival_avg_duration_general(
    breakdown: Dict[str, Dict[str, float]],
    avg_duration_by_id: Dict[str, float],
) -> Optional[float]:
    """Weight each faced rival's own season avg_duration by possessions they played against us."""
    weighted_sum = 0.0
    total_weight = 0.0
    for opp_id, data in breakdown.items():
        opp_general = avg_duration_by_id.get(opp_id)
        if opp_general is None:
            continue
        weighted_sum += opp_general * data["possessions"]
        total_weight += data["possessions"]
    return round(weighted_sum / total_weight, 2) if total_weight > 0 else None


def base_possession_entry(season_row: Dict[str, Any], team_id: Any) -> Dict[str, Any]:
    """Entry from the boxscore-based season row, with the play-by-play fields empty."""
    pace = round(float(season_row.get("possessions_per_game") or 0), 2)
    entry: Dict[str, Any] = {
        "team_name":            season_row.get("team_name", ""),
        "team_id":              str(team_id) if team_id else None,
        "possessions_per_game": pace,
        "pace":                 pace,
        "oer":                  round(float(season_row.get("offensive_rating") or 0), 2),
        "der":                  round(float(season_row.get("defensive_rating") or 0), 2),
        "net_rating":           round(float(season_row.get("net_rating") or 0), 2),
        "total_games":          int(season_row.get("total_games") or 0),
    }
    entry.update({field: None for field in _PBP_FIELDS})
    return entry


def apply_pbp_fields(entry: Dict[str, Any], poss: Optional[Dict[str, Any]]) -> None:
    """Add the play-by-play breakdown, data quality and rival fields to ``entry`` (no-op without possessions)."""
    total = poss.get("total_possessions", 0) if poss else 0
    if total <= 0:
        return
    avg_dur = poss["avg_duration"]
    by_dur = poss.get("possessions_by_duration", {})
    fast, medium, slow = by_dur.get("<=8s", {}), by_dur.get("8-16s", {}), by_dur.get(">16s", {})

    def _pct(count: int) -> float:
        return round(count / total * 100, 1)

    entry["avg_duration"] = avg_dur
    entry["pct_fast"] = _pct(fast.get("count", 0))
    entry["pct_medium"] = _pct(medium.get("count", 0))
    entry["pct_slow"] = _pct(slow.get("count", 0))
    entry["oer_fast"] = fast.get("oer")
    entry["oer_medium"] = medium.get("oer")
    entry["oer_slow"] = slow.get("oer")
    entry["est_possessions_per_game"] = round(2400 / avg_dur / 2, 1) if avg_dur and avg_dur > 0 else None

    # Reconciliation metadata — general OER is untouched (already boxscore-formula from pipeline)
    entry["data_quality_score"] = poss.get("data_quality_score", 100)
    entry["phantom_pct"] = poss.get("phantom_pct", 0)
    entry["reconciliation"] = poss.get("recommendation", "use_playbyplay")
    entry["boxscore_oer"] = poss.get("boxscore_oer", 0)

    # Rival (opponent) possession breakdown
    for key in ("rival_pct_fast", "rival_pct_medium", "rival_pct_slow",
                "rival_oer_fast", "rival_oer_medium", "rival_oer_slow", "rival_avg_duration"):
        entry[key] = poss.get(key)


def apply_exact_fields(entry: Dict[str, Any], poss: Optional[Dict[str, Any]]) -> None:
    """Use the exact possessions of the play-by-play for pace and ratings, and say where they come from (#351)."""
    exact = (poss or {}).get("exact")
    if not exact:
        return
    entry.update(
        pace=exact["pace"], possessions_per_game=exact["pace"], oer=exact["oer"], der=exact["der"],
        net_rating=exact["net_rating"], possessions_source=exact["possessions_source"],
        games_by_source=exact["games_by_source"], games_by_quality=exact["games_by_quality"],
        offensive_rebound_pct=exact["orb_pct"], defensive_rebound_pct=exact["drb_pct"])


def apply_pace_impact(entries: List[Dict[str, Any]], poss_by_team_id: Dict[str, Dict[str, Any]]) -> None:
    """Compare each team's rivals' pace against us to those same rivals' own season-wide pace.

    Weighted by possessions played against us; adds ``rival_avg_duration_general`` and
    ``rival_pace_differential`` to every entry.
    """
    avg_duration_by_id = {
        e["team_id"]: e["avg_duration"]
        for e in entries
        if e.get("team_id") and e.get("avg_duration") is not None
    }
    for entry in entries:
        tid = entry.get("team_id")
        poss = poss_by_team_id.get(tid) if tid else None
        breakdown = poss.get("rival_opponent_breakdown") if poss else None
        general = rival_avg_duration_general(breakdown, avg_duration_by_id) if breakdown else None
        entry["rival_avg_duration_general"] = general
        rival_avg = entry.get("rival_avg_duration")
        entry["rival_pace_differential"] = (
            round(rival_avg - general, 2) if general is not None and rival_avg is not None else None
        )
