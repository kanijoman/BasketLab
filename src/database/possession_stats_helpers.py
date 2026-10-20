"""Pure helpers of the possession-stats repository mixin (no database access): projections, per-game
aggregation, the boxscore-based estimate, reconciliation and the empty result.
"""
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from src.pbp.game_possessions import estimate_possessions, team_game_possessions


def possession_projection(is_fbcyl: bool) -> Dict:
    """Return the narrow Mongo projection used to load play-by-play for possession stats.

    FEB must include 'num' (the possession tracker uses it to break ties between same-timestamp events), 'idPlayer'
    (a rebound without player is a team rebound) and 'deleted' (corrected lines are ignored); FBCYL 'actorId'.
    """
    if is_fbcyl:
        return {
            "moves.move":   1,
            "moves.period": 1,
            "moves.min":    1,
            "moves.sec":    1,
            "moves.idTeam": 1,
            "moves.actorId": 1,
            "stats.teams.teamIdIntern": 1,
            "stats.teams.teamIdExtern": 1,
            "stats.teams.data": 1,                  # the team box (#432: validates rebounds and turnovers; ``exact_season_stats``)
            "stats.periodDurationList": 1,
            "_id": 0,
        }
    return {
        "PLAYBYPLAY.LINES.num":     1,
        "PLAYBYPLAY.LINES.text":    1,
        "PLAYBYPLAY.LINES.quarter": 1,
        "PLAYBYPLAY.LINES.time":    1,
        "PLAYBYPLAY.LINES.action":  1,
        "PLAYBYPLAY.LINES.idTeam":  1,
        "PLAYBYPLAY.LINES.idPlayer": 1,
        "PLAYBYPLAY.LINES.deleted": 1,
        "BOXSCORE.TEAM.id": 1,
        "BOXSCORE.TEAM.TOTAL": 1,
        "HEADER.TEAM.id":           1,
        "_id": 0,
    }


def boxscore_projection(is_fbcyl: bool) -> Dict:
    """Narrow Mongo projection for the boxscore-based possession estimate."""
    if is_fbcyl:
        return {"stats.teams": 1, "_id": 0}
    return {"BOXSCORE.TEAM": 1, "HEADER.TEAM.id": 1, "_id": 0}


def aggregate_game_possession(game_stats: Dict) -> Tuple[float, Dict, Dict, Dict]:
    """Extract per-game possession totals from a single game's calculate_possessions result.

    Returns:
        Tuple of (weighted_duration_sum, short_stats, medium_stats, long_stats) where
        weighted_duration_sum = avg_duration * total_possessions for this game,
        each stats dict has keys 'count' and 'total_points'.
    """
    by_dur = game_stats.get("possessions_by_duration", {})
    total = game_stats.get("total_possessions", 0)
    weighted = game_stats.get("avg_duration", 0.0) * total
    return (
        weighted,
        by_dur.get("<=8s",  {"count": 0, "total_points": 0}),
        by_dur.get("8-16s", {"count": 0, "total_points": 0}),
        by_dur.get(">16s",  {"count": 0, "total_points": 0}),
    )


def boxscore_possession_stats(games: list, team_id: str, is_fbcyl: bool) -> Dict:
    """Formula-based possessions (FGA - ORB + TOV + 0.44*FTA) and OER from the boxscores of ``games``.

    A statistical estimate that does not depend on play-by-play quality.
    Returns a dict with boxscore_possessions, boxscore_oer and total_games.
    """
    if not games:
        return {"boxscore_possessions": 0, "boxscore_oer": 0, "total_games": 0}

    total_possessions = 0.0
    total_points = 0
    total_games = 0

    for game in games:
        try:
            if is_fbcyl:
                # FBCYL format
                stats = game.get("stats", {}).get("teams", [])
                for team in stats:
                    team_id_check = team.get("teamIdIntern") or team.get("teamIdExtern")
                    if str(team_id_check) == str(team_id):
                        # the team has ``data{...}`` (the old FGA / REB_O / TO / FTA / PTS keys do not exist: always 0, #373)
                        data = team.get("data") or {}
                        fga = (data.get("shotsOfTwoAttempted") or 0) + (data.get("shotsOfThreeAttempted") or 0)
                        orb = data.get("offensiveRebound") or 0
                        tov = data.get("lost") or 0
                        fta = data.get("shotsOfOneAttempted") or 0
                        pts = data.get("score") or 0

                        poss = estimate_possessions(fga, orb, tov, fta)
                        if poss > 0:
                            total_possessions += poss
                            total_points += pts
                            total_games += 1
                        break
            else:
                # FEB format — stats live in BOXSCORE.TEAM[i].TOTAL with short names
                boxscore = game.get("BOXSCORE", {}).get("TEAM", [])
                header_teams = game.get("HEADER", {}).get("TEAM", [])
                for i, team_data in enumerate(boxscore):
                    team_id_check = header_teams[i].get("id") if i < len(header_teams) else None
                    if str(team_id_check) == str(team_id):
                        total = team_data.get("TOTAL", {})
                        fga = int(total.get("p2a", 0)) + int(total.get("p3a", 0))
                        orb = int(total.get("ro", 0))
                        tov = int(total.get("to", 0))
                        fta = int(total.get("p1a", 0))
                        pts = int(total.get("pts", 0))

                        poss = estimate_possessions(fga, orb, tov, fta)
                        if poss > 0:
                            total_possessions += poss
                            total_points += pts
                            total_games += 1
                        break
        except Exception:
            continue

    if total_possessions > 0:
        boxscore_oer = (total_points / total_possessions) * 100
    else:
        boxscore_oer = 0

    return {
        "boxscore_possessions": round(total_possessions, 1),
        "boxscore_oer": round(boxscore_oer, 2),
        "total_games": total_games
    }


def opponent_id_from_game(game: Dict, team_id: str, is_fbcyl: bool):
    """Return the opponent team ID from a game document, or None if not found."""
    team_id_str = str(team_id)
    if is_fbcyl:
        for team in game.get("stats", {}).get("teams", []):
            tid = str(team.get("teamIdIntern") or team.get("teamIdExtern") or "")
            if tid and tid != team_id_str:
                return tid
    else:
        for header_team in game.get("HEADER", {}).get("TEAM", []):
            tid = str(header_team.get("id") or "")
            if tid and tid != team_id_str:
                return tid
    return None


def reconciliation_metrics(stats: Dict) -> Dict:
    """Calculate data quality metrics comparing play-by-play vs boxscore OER."""
    total_points = sum(
        stats.get("possessions_by_duration", {}).get(k, {}).get("total_points", 0)
        for k in ["<=8s", "8-16s", ">16s"]
    )
    total_poss = stats.get("total_possessions", 0)
    pbp_oer = (total_points / total_poss * 100) if total_poss > 0 else 0

    boxscore_oer = stats.get("boxscore_oer", 0)
    mismatch_pct = abs(pbp_oer - boxscore_oer) / boxscore_oer * 100 if boxscore_oer > 0 else 0

    data_quality_score = max(0, 100 - int(mismatch_pct * 2))

    if mismatch_pct > 15:
        recommendation = "use_boxscore"
    elif mismatch_pct > 5:
        recommendation = "use_hybrid"
    else:
        recommendation = "use_playbyplay"

    return {
        "mismatch_pct": round(mismatch_pct, 1),
        "data_quality_score": data_quality_score,
        "recommendation": recommendation,
    }


def empty_possession_result() -> Dict:
    return {
        "total_possessions": 0,
        "avg_duration": 0.0,
        "possessions_by_duration": {
            "<=8s":  {"count": 0, "total_points": 0, "oer": 0.0},
            "8-16s": {"count": 0, "total_points": 0, "oer": 0.0},
            ">16s":  {"count": 0, "total_points": 0, "oer": 0.0},
        },
        "games_analyzed": 0,
        # Boxscore fields
        "boxscore_possessions": 0,
        "boxscore_oer": 0,
        # Reconciliation fields
        "mismatch_pct": 0.0,
        "data_quality_score": 100,
        "recommendation": "use_playbyplay",
        # Rival possession breakdown (None = no PBP data)
        "rival_pct_fast": None,
        "rival_pct_medium": None,
        "rival_pct_slow": None,
        "rival_oer_fast": None,
        "rival_oer_medium": None,
        "rival_oer_slow": None,
    }


def _team_key(game: Dict[str, Any], team_id: str) -> str:
    """The id the tracker used for ``team_id`` in this game: FEB, the team id; FBCYL, the ``teamIdIntern`` of the team whose stable
    ``teamIdExtern`` is ``team_id`` (the intern id changes in every game, #432)."""
    for team in (game.get("stats") or {}).get("teams") or []:
        if str(team.get("teamIdExtern")) == str(team_id) or str(team.get("teamIdIntern")) == str(team_id):
            return str(team.get("teamIdIntern"))
    return str(team_id)


def exact_season_stats(games: List[Dict[str, Any]], team_id: str) -> Optional[Dict[str, Any]]:
    """Season figures of a FEB team from its games' play-by-play, validated against the box score (#351).

    Possessions per game and per 40 minutes, OER/DER and ORB%/DRB% with team rebounds included, and how many games
    used the exact count or the estimate and which data quality they had. None if no game can be read.
    """
    games_n = 0
    poss = opp_poss = pts = opp_pts = orb = drb = opp_orb = opp_drb = 0.0
    pace_sum = 0.0
    sources: Counter = Counter()
    levels: Counter = Counter()
    rebound_fallbacks = 0
    for game in games:
        per_team = team_game_possessions(game)
        key = _team_key(game, team_id)
        if not per_team or key not in per_team:
            continue
        mine = per_team[key]
        rival = next(t for tid, t in per_team.items() if tid != key)
        games_n += 1
        poss, opp_poss, pts, opp_pts = poss + mine["possessions"], opp_poss + rival["possessions"], pts + mine["pts"], opp_pts + rival["pts"]
        orb, drb, opp_orb, opp_drb = orb + mine["orb"], drb + mine["drb"], opp_orb + rival["orb"], opp_drb + rival["drb"]
        pace_sum += mine["possessions"] * 40 / mine["game_minutes"]
        sources[mine["possessions_source"]] += 1
        levels[mine["quality_level"]] += 1
        rebound_fallbacks += "boxscore" in (mine["orb_source"], mine["drb_source"])
    if not games_n:
        return None
    oer = pts / poss * 100 if poss else 0.0
    der = opp_pts / opp_poss * 100 if opp_poss else 0.0
    return {
        "games": games_n,
        "possessions_per_game": round(poss / games_n, 2),
        "pace": round(pace_sum / games_n, 2),
        "oer": round(oer, 2), "der": round(der, 2), "net_rating": round(oer - der, 2),
        "orb_pct": round(orb / (orb + opp_drb) * 100, 2) if orb + opp_drb else 0.0,
        "drb_pct": round(drb / (drb + opp_orb) * 100, 2) if drb + opp_orb else 0.0,
        "possessions_source": next(iter(sources)) if len(sources) == 1 else "mixed",
        "games_by_source": dict(sources), "games_by_quality": dict(levels), "rebound_fallbacks": rebound_fallbacks,
    }
