"""Derived basketball stats computation — extracted from historical_ingestion_service.py."""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.pbp.game_possessions import estimate_possessions
from src.utils.time_utils import utc_now_naive


def _efg(fgm: int, fg3m: int, fga: int) -> float:
    if fga <= 0:
        return 0.0
    return round((fgm + 0.5 * fg3m) / fga * 100.0, 2)


def _efg_ftr(raw: Dict[str, Any]) -> float:
    """FT rate for a team (FTA / FGA)."""
    fga = raw["fg2a"] + raw["fg3a"]
    return raw["fta"] / fga * 100.0 if fga > 0 else 0.0


def compute_derived(
    pts: int,
    opp_pts: int,
    fg2m: int,
    fg2a: int,
    fg3m: int,
    fg3a: int,
    ftm: int,
    fta: int,
    oreb: int,
    dreb: int,
    ast: int,
    stl: int,
    tov: int,
    blk: int,
    opp_fg2a: int,
    opp_fg3a: int,
    opp_fta: int,
    opp_oreb: int,
    opp_tov: int,
    opp_pts_check: int,
    exact_poss: Optional[float] = None,
    exact_opp_poss: Optional[float] = None,
) -> Dict[str, float]:
    """Compute possession-based derived stats.

    All formulas are identical to those in ``StatsCalculator`` so both layers
    stay consistent.  ``exact_poss`` / ``exact_opp_poss`` (the stored possessions of the game, #372) replace the box-score
    estimate; without them it falls back to ``estimate_possessions``.
    ``efg_pct`` and ``opp_efg_pct`` are initialised to 0.0 and must be
    overwritten by the caller using :func:`_efg` on the actual field-goal data.
    """
    fga = fg2a + fg3a
    opp_fga = opp_fg2a + opp_fg3a

    poss = max(exact_poss if exact_poss else estimate_possessions(fga, oreb, tov, fta), 1.0)
    opp_poss = max(exact_opp_poss if exact_opp_poss else estimate_possessions(opp_fga, opp_oreb, opp_tov, opp_fta), 1.0)

    pace = (poss + opp_poss) / 2.0
    ortg = pts / poss * 100.0
    drtg = opp_pts / opp_poss * 100.0
    net_rtg = ortg - drtg

    tov_rate = tov / poss * 100.0
    oreb_pct = oreb / (oreb + dreb) * 100.0 if (oreb + dreb) > 0 else 0.0
    ftr = fta / fga * 100.0 if fga > 0 else 0.0
    fg3a_rate = fg3a / fga * 100.0 if fga > 0 else 0.0

    return {
        "poss":        round(poss, 2),
        "opp_poss":    round(opp_poss, 2),
        "pace":        round(pace, 2),
        "ortg":        round(ortg, 2),
        "drtg":        round(drtg, 2),
        "net_rtg":     round(net_rtg, 2),
        "efg_pct":     0.0,      # filled by caller
        "opp_efg_pct": 0.0,      # filled by caller
        "tov_rate":    round(tov_rate, 2),
        "oreb_pct":    round(oreb_pct, 2),
        "ftr":         round(ftr, 2),
        "fg3a_rate":   round(fg3a_rate, 2),
    }


def build_team_docs(
    raws: tuple,
    exact: Optional[Dict[str, float]],
    *,
    match_id: str,
    date: Any,
    season: str,
    competition: str,
    league: str,
    gender: Optional[str],
    group: str,
    home_id: str,
    source_collection: str,
    scraped_at: Any,
) -> list:
    """The two HISTORICAL documents (one per team) of a match from the raw stats of both teams.

    What differs between FEB and FBCYL (how the raw stats are read, the league, the date and
    the home team) is passed in; the derived metrics and the record layout are the same for both.
    ``exact`` holds the possessions per team id when the tracker gave them (FEB), else None.
    """
    exact = exact or {}
    docs = []
    for my_raw, opp_raw in (raws, raws[::-1]):
        derived = compute_derived(
            exact_poss=exact.get(my_raw["team_id"]), exact_opp_poss=exact.get(opp_raw["team_id"]),
            pts=my_raw["pts"], opp_pts=opp_raw["pts"],
            fg2m=my_raw["fg2m"], fg2a=my_raw["fg2a"], fg3m=my_raw["fg3m"], fg3a=my_raw["fg3a"],
            ftm=my_raw["ftm"], fta=my_raw["fta"], oreb=my_raw["oreb"], dreb=my_raw["dreb"],
            ast=my_raw["ast"], stl=my_raw["stl"], tov=my_raw["tov"], blk=my_raw["blk"],
            opp_fg2a=opp_raw["fg2a"], opp_fg3a=opp_raw["fg3a"], opp_fta=opp_raw["fta"],
            opp_oreb=opp_raw["oreb"], opp_tov=opp_raw["tov"], opp_pts_check=opp_raw["pts"],
        )
        fga = my_raw["fg2a"] + my_raw["fg3a"]
        opp_fga = opp_raw["fg2a"] + opp_raw["fg3a"]
        derived["efg_pct"] = _efg(my_raw["fg2m"] + my_raw["fg3m"], my_raw["fg3m"], fga)
        derived["opp_efg_pct"] = _efg(opp_raw["fg2m"] + opp_raw["fg3m"], opp_raw["fg3m"], opp_fga)

        poss, opp_poss = derived["poss"], derived["opp_poss"]
        both = bool(poss and opp_poss)
        diff_pts_100 = (my_raw["pts"] - opp_raw["pts"]) / poss * 100.0 if poss else 0.0
        diff_efg = derived["efg_pct"] - derived["opp_efg_pct"]
        diff_tov_100 = (my_raw["tov"] / poss - opp_raw["tov"] / opp_poss) * 100.0 if both else 0.0
        diff_oreb_100 = (my_raw["oreb"] / poss - opp_raw["oreb"] / opp_poss) * 100.0 if both else 0.0
        diff_ftr = derived["ftr"] - _efg_ftr(opp_raw)

        docs.append({
            "match_id": match_id, "date": date, "season": season, "competition": competition,
            "league": league, "gender": gender, "group": group,
            "team_id": my_raw["team_id"], "team_name": my_raw["team_name"],
            "is_home": my_raw["team_id"] == home_id,
            "opp_id": opp_raw["team_id"], "opp_name": opp_raw["team_name"],
            "pts": my_raw["pts"], "opp_pts": opp_raw["pts"],
            "fga": fga, "fgm": my_raw["fg2m"] + my_raw["fg3m"],
            **{k: my_raw[k] for k in ("fg2a", "fg2m", "fg3a", "fg3m", "fta", "ftm", "oreb", "dreb", "ast", "stl", "tov", "blk", "pf")},
            **derived,
            "diff_pts_100": round(diff_pts_100, 3), "diff_efg": round(diff_efg, 3),
            "diff_tov_100": round(diff_tov_100, 3), "diff_oreb_100": round(diff_oreb_100, 3),
            "diff_ftr": round(diff_ftr, 3),
            "source_collection": source_collection,
            "scraped_at": scraped_at or utc_now_naive(),
        })
    return docs
