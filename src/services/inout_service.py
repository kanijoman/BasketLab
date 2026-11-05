"""The IN/OUT analysis of a player as the web shows it (issue #334: it lived in the players router, so the exporter that publishes it imported the server).

``inout_analysis`` is what ``GET /players/{collection}/inout/{player_id}`` answers and what ``src/local_data/inout_export.py`` publishes: the raw analysis of
``PlayerStatsService`` with the legacy ``in``/``out`` keys renamed to ``on``/``off`` and the advanced metrics added to each block.
"""
from typing import Any, Dict

from src.pbp.game_possessions import estimate_possessions
from src.services import PlayerStatsService


def enrich_stat_block(block: Dict) -> Dict:
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
    poss     = estimate_possessions(fga, orb, tov, fta) if (fga + fta + tov) > 0 else 0
    opp_poss = estimate_possessions(opp_fga, opp_orb, opp_tov, opp_fta_) if (opp_fga + opp_fta_ + opp_tov) > 0 else 0

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


def inout_analysis(db: Any, collection: str, player_id: str) -> Dict[str, Any]:
    """Team performance when ``player_id`` is on and off the court, with the advanced metrics of each block."""
    result = PlayerStatsService(db).get_in_out_analysis(collection, player_id)
    # Normalize legacy in/out keys to on/off expected by the frontend
    if result and "in" in result and "on" not in result:
        result["on"] = result.pop("in")
    if result and "out" in result and "off" not in result:
        result["off"] = result.pop("out")
    # Enrich both blocks with advanced metrics
    if result:
        if "on" in result:
            result["on"] = enrich_stat_block(result["on"])
        if "off" in result:
            result["off"] = enrich_stat_block(result["off"])
    return result
