"""FBCYL per-game aggregation pipelines for consistency / dispersion analysis.

Each pipeline returns **one document per (team|player) per game** — equivalent
to FEB's ``build_per_game_raw_pipeline`` and ``build_per_player_per_game_pipeline``
so the same FIELD_MAP dictionaries can be reused in the consistency service.

Output field names intentionally mirror the FEB per-game pipeline so that the
same ``OWN_FIELD_MAP`` / ``FIELD_MAP`` structures in the service layer work for
both leagues without branching.
"""

from __future__ import annotations

from typing import Dict, List


def build_fbcyl_team_per_game_pipeline() -> List[Dict]:
    """Return one aggregation document per (team, game) for FBCYL collections.

    Raw counting fields are projected with field names that match FEB's
    ``build_per_game_raw_pipeline`` output.  Derived per-game metrics (fg3_pct,
    efg_pct, possessions, oer/der/net, rate stats) are computed in a subsequent
    Python pass via :func:`enrich_fbcyl_team_row`.

    Returns:
        List of MongoDB aggregation pipeline stages.
    """
    return [
        # Stage 1: only documents that have team stats
        {"$match": {"stats.teams": {"$exists": True, "$ne": None}}},

        # Stage 2: preserve full teams array before unwind
        {"$addFields": {
            "teams": "$stats.teams",
            "original_teams": "$stats.teams",
        }},

        # Stage 3: one doc per team per game
        {"$unwind": {"path": "$teams", "includeArrayIndex": "teamIndex"}},

        # Stage 4: add team identity + opponent sub-document
        {"$addFields": {
            "team_name": "$teams.name",
            "opponent_data": {
                "$cond": {
                    "if":   {"$eq": ["$teamIndex", 0]},
                    "then": {"$arrayElemAt": ["$original_teams", 1]},
                    "else": {"$arrayElemAt": ["$original_teams", 0]},
                }
            },
        }},

        # Stage 5: project raw counting stats with FEB-compatible field names
        {"$project": {
            "_id": 0,
            "team_name": 1,
            # Own counting stats
            "points":          "$teams.data.score",
            "opponent_points": "$opponent_data.data.score",
            "fg2_made":        "$teams.data.shotsOfTwoSuccessful",
            "fg2_attempts":    "$teams.data.shotsOfTwoAttempted",
            "fg3_made":        "$teams.data.shotsOfThreeSuccessful",
            "fg3_attempts":    "$teams.data.shotsOfThreeAttempted",
            "ft_made":         "$teams.data.shotsOfOneSuccessful",
            "ft_attempts":     "$teams.data.shotsOfOneAttempted",
            "off_rebounds":    "$teams.data.offensiveRebound",
            "def_rebounds":    "$teams.data.defensiveRebound",
            "total_rebounds":  "$teams.data.rebounds",
            "assists":         "$teams.data.assists",
            "steals":          "$teams.data.steals",
            "turnovers":       "$teams.data.lost",
            "blocks":          "$teams.data.block",
            # Opponent counting stats (for rival consistency)
            "opp_fg2_made":     "$opponent_data.data.shotsOfTwoSuccessful",
            "opp_fg2_attempts": "$opponent_data.data.shotsOfTwoAttempted",
            "opp_fg3_made":     "$opponent_data.data.shotsOfThreeSuccessful",
            "opp_fg3_attempts": "$opponent_data.data.shotsOfThreeAttempted",
            "opp_ft_attempts":  "$opponent_data.data.shotsOfOneAttempted",
            "opp_off_rebounds": "$opponent_data.data.offensiveRebound",
            "opp_def_rebounds": "$opponent_data.data.defensiveRebound",
            "opp_total_rebounds": "$opponent_data.data.rebounds",
            "opp_assists":     "$opponent_data.data.assists",
            "opp_steals":      "$opponent_data.data.steals",
            "opp_turnovers":   "$opponent_data.data.lost",
            "opp_blocks":      "$opponent_data.data.block",
            "opp_points":      "$opponent_data.data.score",
        }},
    ]


def enrich_fbcyl_team_row(row: Dict) -> Dict:
    """Compute derived per-game fields (in Python) for one FBCYL team row.

    Adds field names that match the FEB ``OWN_FIELD_MAP`` / ``RIVAL_FIELD_MAP``
    values so the consistency service requires no branching on league type.

    Args:
        row: A raw document from :func:`build_fbcyl_team_per_game_pipeline`.

    Returns:
        The same dict, mutated in-place, with derived fields added.
    """
    def _pct(num, denom):
        return (num / denom * 100) if denom else None

    def _safe(v):
        return v if v is not None else 0

    pts  = _safe(row.get("points"))
    opp  = _safe(row.get("opponent_points"))
    fg2m = _safe(row.get("fg2_made"))
    fg2a = _safe(row.get("fg2_attempts"))
    fg3m = _safe(row.get("fg3_made"))
    fg3a = _safe(row.get("fg3_attempts"))
    fta  = _safe(row.get("ft_attempts"))
    orb  = _safe(row.get("off_rebounds"))
    drb  = _safe(row.get("def_rebounds"))
    ast  = _safe(row.get("assists"))
    tov  = _safe(row.get("turnovers"))
    blk  = _safe(row.get("blocks"))
    stl  = _safe(row.get("steals"))

    o_fg2m = _safe(row.get("opp_fg2_made"))
    o_fg2a = _safe(row.get("opp_fg2_attempts"))
    o_fg3m = _safe(row.get("opp_fg3_made"))
    o_fg3a = _safe(row.get("opp_fg3_attempts"))
    o_fta  = _safe(row.get("opp_ft_attempts"))
    o_orb  = _safe(row.get("opp_off_rebounds"))
    o_drb  = _safe(row.get("opp_def_rebounds"))
    o_ast  = _safe(row.get("opp_assists"))
    o_tov  = _safe(row.get("opp_turnovers"))
    o_blk  = _safe(row.get("opp_blocks"))
    o_stl  = _safe(row.get("opp_steals"))
    o_pts  = _safe(row.get("opp_points"))

    fga  = fg2a + fg3a
    fgm  = fg2m + fg3m
    o_fga = o_fg2a + o_fg3a
    o_fgm = o_fg2m + o_fg3m

    # Possessions (0.45 multiplier matches the codebase convention)
    poss     = fga + 0.45 * fta + tov - orb
    opp_poss = o_fga + 0.45 * o_fta + o_tov - o_orb

    row["fg2_pct_game"] = _pct(fg2m, fg2a)
    row["fg3_pct_game"] = _pct(fg3m, fg3a)
    row["ft_pct_game"]  = _pct(row.get("ft_made", 0), fta)
    row["efg_pct_game"] = _pct(fg2m + 1.5 * fg3m, fga)
    row["ts_pct_game"]  = _pct(pts, 2 * (fga + 0.44 * fta))
    row["tov_pct_game"] = _pct(tov, fga + 0.44 * fta + tov)
    row["possessions"]  = poss if poss > 0 else None
    row["oer_game"]     = _pct(pts, poss)
    row["der_game"]     = _pct(opp, poss)
    row["net_game"]     = (row["oer_game"] - row["der_game"]
                           if row["oer_game"] is not None and row["der_game"] is not None
                           else None)

    # Rate stats (matching FEB field names)
    row["three_point_rate_game"] = _pct(fg3a, fga)
    row["free_throw_rate_game"]  = _pct(fta, fga)
    row["assist_fg_rate_game"]   = _pct(ast, fgm)
    row["assist_rate_game"]      = _pct(ast, poss)
    row["steal_rate_game"]       = _pct(stl, opp_poss)
    row["block_rate_game"]       = _pct(blk, o_fg2a)
    row["oreb_rate_game"]        = _pct(orb, orb + o_drb)
    row["dreb_rate_game"]        = _pct(drb, drb + o_orb)

    # Opponent derived fields
    row["opp_fg2_pct_game"]         = _pct(o_fg2m, o_fg2a)
    row["opp_fg3_pct_game"]         = _pct(o_fg3m, o_fg3a)
    row["opp_ft_pct_game"]          = _pct(row.get("opp_ft_made", 0), o_fta)
    row["opp_efg_pct_game"]         = _pct(o_fg2m + 1.5 * o_fg3m, o_fga)
    row["opp_ts_pct_game"]          = _pct(o_pts, 2 * (o_fga + 0.44 * o_fta))
    row["opp_tov_pct_game"]         = _pct(o_tov, o_fga + 0.44 * o_fta + o_tov)
    row["opp_possessions"]          = opp_poss if opp_poss > 0 else None
    row["opp_oer_game"]             = _pct(o_pts, opp_poss)
    row["opp_der_game"]             = _pct(pts, opp_poss)
    row["opp_net_game"]             = (row["opp_oer_game"] - row["opp_der_game"]
                                       if row["opp_oer_game"] is not None
                                       and row["opp_der_game"] is not None else None)
    row["opp_three_point_rate_game"] = _pct(o_fg3a, o_fga)
    row["opp_free_throw_rate_game"]  = _pct(o_fta, o_fga)
    row["opp_assist_fg_rate_game"]   = _pct(o_ast, o_fgm)
    row["opp_assist_rate_game"]      = _pct(o_ast, opp_poss)
    row["opp_steal_rate_game"]       = _pct(o_stl, poss)
    row["opp_block_rate_game"]       = _pct(o_blk, fg2a)
    row["opp_orb_rate_game"]         = _pct(o_orb, o_orb + drb)
    row["opp_drb_rate_game"]         = _pct(o_drb, o_drb + orb)

    return row


def build_fbcyl_player_per_game_pipeline() -> List[Dict]:
    """Return one document per (player, game) for FBCYL collections.

    Output field names match those used by the FEB per-player-per-game pipeline
    so the same ``FIELD_MAP`` in ``PlayerStatsService.get_consistency`` can be
    reused without branching.

    Returns:
        List of MongoDB aggregation pipeline stages.
    """
    return [
        # Stage 1: only documents that have team stats
        {"$match": {"stats.teams": {"$exists": True, "$ne": None}}},

        # Stage 2: unwind teams
        {"$unwind": {"path": "$stats.teams", "includeArrayIndex": "teamIndex"}},

        # Stage 3: unwind players within each team
        {"$unwind": {
            "path": "$stats.teams.players",
            "preserveNullAndEmptyArrays": False,
        }},

        # Stage 4: only players who actually played.
        # Also exclude phantom players: inscribed but never played; FBCYL
        # assigns them timePlayed=40 (full game) with all activity stats==0.
        # $nor excludes any player where timePlayed==40 AND every listed stat is
        # zero or absent — those are registered-but-did-not-play entries.
        {"$match": {
            "stats.teams.players.timePlayed": {"$gt": 0},
            "$nor": [{
                "stats.teams.players.timePlayed": 40,
                "stats.teams.players.data.score":               {"$in": [0, None]},
                "stats.teams.players.data.shotsOfTwoAttempted":   {"$in": [0, None]},
                "stats.teams.players.data.shotsOfThreeAttempted": {"$in": [0, None]},
                "stats.teams.players.data.shotsOfOneAttempted":   {"$in": [0, None]},
                "stats.teams.players.data.offensiveRebound":      {"$in": [0, None]},
                "stats.teams.players.data.defensiveRebound":      {"$in": [0, None]},
                "stats.teams.players.data.assists":               {"$in": [0, None]},
                "stats.teams.players.data.lost":                  {"$in": [0, None]},
                "stats.teams.players.data.block":                 {"$in": [0, None]},
                "stats.teams.players.data.steals":                {"$in": [0, None]},
            }],
        }},

        # Stage 5: project with FEB-compatible field names
        {"$project": {
            "_id": 0,
            "player_id": "$stats.teams.players.uuid",
            "player_name": "$stats.teams.players.name",
            "team_name": "$stats.teams.name",
            "minutes": "$stats.teams.players.timePlayed",
            "pts":    "$stats.teams.players.data.score",
            "val":    "$stats.teams.players.data.valoration",
            "p1a":    "$stats.teams.players.data.shotsOfOneAttempted",
            "p1m":    "$stats.teams.players.data.shotsOfOneSuccessful",
            "p2a":    "$stats.teams.players.data.shotsOfTwoAttempted",
            "p2m":    "$stats.teams.players.data.shotsOfTwoSuccessful",
            "p3a":    "$stats.teams.players.data.shotsOfThreeAttempted",
            "p3m":    "$stats.teams.players.data.shotsOfThreeSuccessful",
            "ro":     "$stats.teams.players.data.offensiveRebound",
            "rd":     "$stats.teams.players.data.defensiveRebound",
            "rt": {
                "$add": [
                    {"$ifNull": ["$stats.teams.players.data.offensiveRebound", 0]},
                    {"$ifNull": ["$stats.teams.players.data.defensiveRebound", 0]},
                ]
            },
            "assist": "$stats.teams.players.data.assists",
            "to":     "$stats.teams.players.data.lost",
            "bs":     "$stats.teams.players.data.block",
            "st":     "$stats.teams.players.data.steals",
            "pf":     "$stats.teams.players.data.faults",
        }},
    ]


def enrich_fbcyl_player_row(row: Dict) -> Dict:
    """Compute derived per-game shooting percentages for one FBCYL player row.

    Args:
        row: Raw document from :func:`build_fbcyl_player_per_game_pipeline`.

    Returns:
        The same dict with shooting percentage fields added.
    """
    def _pct(num, denom):
        return (num / denom * 100) if denom else None

    p1a = row.get("p1a") or 0
    p1m = row.get("p1m") or 0
    p2a = row.get("p2a") or 0
    p2m = row.get("p2m") or 0
    p3a = row.get("p3a") or 0
    p3m = row.get("p3m") or 0
    pts = row.get("pts") or 0

    fga = p2a + p3a
    fgm = p2m + p3m

    row["fg1_pct_game"] = _pct(p1m, p1a)
    row["fg2_pct_game"] = _pct(p2m, p2a)
    row["fg3_pct_game"] = _pct(p3m, p3a)
    row["efg_pct_game"] = _pct(p2m + 1.5 * p3m, fga)
    row["ts_pct_game"]  = _pct(pts, 2 * (fga + 0.44 * p1a))
    row["ftr_game"]     = _pct(p1a, fga)
    row["three_pr_game"] = _pct(p3a, fga)
    row["tov_pct_game"] = _pct(row.get("to", 0), fga + 0.44 * p1a + (row.get("to") or 0))

    return row
