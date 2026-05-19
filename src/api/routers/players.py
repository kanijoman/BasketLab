"""Players router — per-player statistics and IN/OUT analysis."""

from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.services import PlayerStatsService

router = APIRouter()


def _enrich_stat_block(block: Dict) -> Dict:
    """Add advanced metrics to a raw IN/OUT stat block (mirrors StatsCalculator logic).

    Input keys expected: fgm_2, fga_2, fgm_3, fga_3, ftm, fta,
    orb, drb, ast, stl, blk, tov, pf, points_for, points_against,
    opp_fgm_2, opp_fga_2, opp_fgm_3, opp_fga_3, opp_ftm, opp_fta,
    opp_orb, opp_drb, opp_ast, opp_stl, opp_blk, opp_tov, minutes.
    """
    def _s(k: str) -> float:
        return float(block.get(k, 0) or 0)

    pts       = _s("points_for")
    opp_pts   = _s("points_against")
    fg2m      = _s("fgm_2");    fg2a  = _s("fga_2")
    fg3m      = _s("fgm_3");    fg3a  = _s("fga_3")
    ftm       = _s("ftm");      fta   = _s("fta")
    orb       = _s("orb");      drb   = _s("drb")
    ast       = _s("ast");      stl   = _s("stl")
    blk       = _s("blk");      tov   = _s("tov")
    pf        = _s("pf")
    opp_fg2a  = _s("opp_fga_2") + _s("opp_fgm_2") * 0  # just opp_fga_2
    opp_fg2a  = _s("opp_fga_2")
    opp_fg3a  = _s("opp_fga_3")
    opp_fta_  = _s("opp_fta")
    opp_orb   = _s("opp_orb");  opp_drb = _s("opp_drb")
    opp_tov   = _s("opp_tov")
    minutes   = _s("minutes")

    fga = fg2a + fg3a
    fgm = fg2m + fg3m
    opp_fga = opp_fg2a + opp_fg3a

    # Possessions
    poss     = fga  + 0.45 * fta  + tov  - orb  if (fga + fta + tov) > 0 else 0
    opp_poss = opp_fga + 0.45 * opp_fta_ + opp_tov - opp_orb if (opp_fga + opp_fta_ + opp_tov) > 0 else 0

    def _pct(a, b): return round(a / b * 100, 2) if b > 0 else 0.0

    efg_pct   = _pct(fgm + 0.5 * fg3m, fga)
    ts_pct    = _pct(pts, 2 * (fga + 0.44 * fta))
    fg2_pct   = _pct(fg2m, fg2a)
    fg3_pct   = _pct(fg3m, fg3a)
    ft_pct    = _pct(ftm, fta)
    three_rate = _pct(fg3a, fga)
    ft_rate    = _pct(fta, fga)
    ast_rate   = _pct(ast, poss)
    tov_rate   = _pct(tov, poss)
    oreb_rate  = _pct(orb, orb + opp_drb)
    dreb_rate  = _pct(drb, drb + opp_orb)
    ortg       = _pct(pts, poss)
    drtg       = _pct(opp_pts, opp_poss)
    # Prefer computed net_rating from possessions; fall back to existing value if no shooting data
    net_rtg = round(ortg - drtg, 2) if poss > 0 else round(float(block.get("net_rating") or 0), 2)

    poss_per_40 = round(poss * 40 / minutes, 2) if minutes > 0 else 0.0

    block.update({
        "net_rating":              net_rtg,
        "offensive_rating":        round(ortg, 2) if poss > 0 else round(float(block.get("offensive_rating") or 0), 2),
        "defensive_rating":        round(drtg, 2) if opp_poss > 0 else round(float(block.get("defensive_rating") or 0), 2),
        "possessions":             round(poss, 1),
        "possessions_per_40":      poss_per_40,
        "efg_percentage":          efg_pct,
        "true_shooting":           ts_pct,
        "fg2_percentage":          fg2_pct,
        "fg3_percentage":          fg3_pct,
        "ft_percentage":           ft_pct,
        "three_point_rate":        three_rate,
        "free_throw_rate":         ft_rate,
        "assist_rate":             ast_rate,
        "turnover_rate":           tov_rate,
        "offensive_rebound_rate":  oreb_rate,
        "defensive_rebound_rate":  dreb_rate,
        "fg2_made":  int(fg2m), "fg2_attempts":  int(fg2a),
        "fg3_made":  int(fg3m), "fg3_attempts":  int(fg3a),
        "ft_made":   int(ftm),  "ft_attempts":   int(fta),
        "assists":   int(ast),  "steals":  int(stl),
        "blocks":    int(blk),  "turnovers": int(tov),
        "fouls":     int(pf),
        "off_rebounds": int(orb), "def_rebounds": int(drb),
    })
    return block


@router.get("/{collection}", summary="Get all player stats for a collection")
def get_player_stats(
    collection: str,
    venue: Optional[str] = Query(None, description="home | away | null for all"),
    result: Optional[str] = Query(None, description="won | lost | null for all"),
    from_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    to_date:   Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    team: Optional[str] = Query(None, description="Restrict to a single team name (server-side filter)"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return aggregated per-player statistics for all players in *collection*.

    Args:
        collection: MongoDB collection name, e.g. ``FEB_LF2_2025_A``.
        venue: Optional venue filter — ``"home"`` or ``"away"``.
        result: Optional result filter — ``"won"`` or ``"lost"``.
        from_date: Optional start date (inclusive), format ``YYYY-MM-DD``.
        to_date: Optional end date (inclusive), format ``YYYY-MM-DD``.
        team: Optional team name to restrict results (server-side, reduces memory).

    Returns:
        List of player stat dicts (one per player).
    """
    svc = PlayerStatsService(db)
    venue_filter = True if venue == "home" else (False if venue == "away" else None)
    date_filter: Optional[Dict] = None
    if from_date or to_date:
        date_filter = {}
        if from_date:
            date_filter["$gte"] = datetime.fromisoformat(from_date)
        if to_date:
            date_filter["$lte"] = datetime.fromisoformat(to_date)
    return svc.load_season_data(
        collection,
        date_filter=date_filter,
        venue_filter=venue_filter,
        result_filter=result,
        team_filter=team,
    )


@router.get("/{collection}/quartiles", summary="Get league-wide player stat quartiles")
def get_player_quartiles(collection: str, db=Depends(get_db)) -> Dict[str, Any]:
    svc = PlayerStatsService(db)
    return svc.get_quartiles(collection)


@router.get("/{collection}/consistency", summary="Get per-player intra-game consistency stats")
def get_player_consistency(collection: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Return CV (coefficient of variation) per stat for each player.

    Computes how consistent each player is game-to-game across all their
    tracked stats.  Only available for FEB collections.

    Args:
        collection: MongoDB collection name.

    Returns:
        ``{player_id: {stat_key: {mean, std, cv, n}}}``
    """
    svc = PlayerStatsService(db)
    return svc.get_consistency(collection)


@router.get("/{collection}/inout/{player_id}", summary="IN/OUT impact analysis for a player")
def get_inout_analysis(
    collection: str,
    player_id: str,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Return team performance metrics when a player is on vs off court.

    Runs a play-by-play analysis over all games in the collection to compute
    points-per-possession, efficiency differential, and per-stat splits.

    Args:
        collection: MongoDB collection name.
        player_id: Player identifier (FEB integer string or FBCYL UUID-like).

    Returns:
        Dict with ``in`` and ``out`` stat blocks, each containing shooting,
        rebounding, assists, turnovers and net rating.
    """
    svc = PlayerStatsService(db)
    result = svc.get_in_out_analysis(collection, player_id)
    # Normalize legacy in/out keys to on/off expected by the frontend
    if result and "in" in result and "on" not in result:
        result["on"] = result.pop("in")
    if result and "out" in result and "off" not in result:
        result["off"] = result.pop("out")
    # Enrich both blocks with advanced metrics
    if result:
        if "on" in result:
            result["on"] = _enrich_stat_block(result["on"])
        if "off" in result:
            result["off"] = _enrich_stat_block(result["off"])
    return result


@router.get("/{collection}/together/{player1_id}/{player2_id}", summary="Two-player together analysis")
def get_players_together(
    collection: str,
    player1_id: str,
    player2_id: str,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Return team stats when two specific players are simultaneously on court.

    Args:
        collection: MongoDB collection name.
        player1_id: First player identifier.
        player2_id: Second player identifier.

    Returns:
        Combined stat dict for the shared court time.
    """
    svc = PlayerStatsService(db)
    result = svc.get_players_together(collection, player1_id, player2_id)
    if result:
        if "together" in result:
            result["together"] = _enrich_stat_block(result["together"])
        if "apart" in result:
            result["apart"] = _enrich_stat_block(result["apart"])
    return result
