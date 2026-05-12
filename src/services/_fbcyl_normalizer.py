"""FBCYL match normalizer — extracted from historical_ingestion_service.py."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.numeric_utils import safe_int
from src.services._historical_derived import compute_derived, _efg, _efg_ftr


def extract_fbcyl_team_raw(team: Dict[str, Any]) -> Dict[str, Any]:
    """Extract raw integer stats from a FBCYL stats.teams entry."""
    return {
        "team_id":   str(team.get("id", "")),
        "team_name": str(team.get("name", "")),
        "pts":  safe_int(team.get("score", 0) or team.get("totalPoints", 0)),
        "fg2m": safe_int(team.get("shotsOfTwoSuccessful", 0)),
        "fg2a": safe_int(team.get("shotsOfTwoAttempted", 0)),
        "fg3m": safe_int(team.get("shotsOfThreeSuccessful", 0)),
        "fg3a": safe_int(team.get("shotsOfThreeAttempted", 0)),
        "ftm":  safe_int(team.get("shotsOfOneSuccessful", 0)),
        "fta":  safe_int(team.get("shotsOfOneAttempted", 0)),
        "oreb": safe_int(team.get("offensiveRebound", 0)),
        "dreb": safe_int(team.get("defensiveRebound", 0)),
        "ast":  safe_int(team.get("assists", 0)),
        "stl":  safe_int(team.get("steals", 0)),
        "tov":  safe_int(team.get("lost", 0)),
        "blk":  safe_int(team.get("block", 0)),
        "pf":   safe_int(team.get("foulsCommited", 0) or team.get("fouls", 0)),
    }


def normalize_fbcyl_match(
    doc: Dict[str, Any],
    season: str,
    competition: str,
    group: str,
    gender: Optional[str],
    source_collection: str,
    parse_date,
    scraped_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Convert a FBCYL game document into two HISTORICAL documents.

    Args:
        doc:               Full FBCYL match document as stored in MongoDB.
        season:            Normalised season label, e.g. ``"2024-25"``.
        competition:       Competition label.
        group:             Group label.
        gender:            ``"F"`` / ``"M"`` / ``None``.
        source_collection: Original collection name for traceability.
        parse_date:        Callable ``(str) -> Optional[datetime]``.
        scraped_at:        Ingestion timestamp (defaults to now).

    Returns:
        List of two normalised documents ready for ``upsert_match_team``.
    """
    match_id = str(doc.get("_id") or doc.get("uuid", ""))
    stats = doc.get("stats", {})
    teams = stats.get("teams", [])
    date_raw = doc.get("date") or stats.get("date") or ""
    date = parse_date(str(date_raw))

    if len(teams) != 2:
        return []

    raw0 = extract_fbcyl_team_raw(teams[0])
    raw1 = extract_fbcyl_team_raw(teams[1])
    home_id = raw0["team_id"]

    docs = []
    for my_raw, opp_raw in ((raw0, raw1), (raw1, raw0)):
        derived = compute_derived(
            pts=my_raw["pts"],
            opp_pts=opp_raw["pts"],
            fg2m=my_raw["fg2m"],
            fg2a=my_raw["fg2a"],
            fg3m=my_raw["fg3m"],
            fg3a=my_raw["fg3a"],
            ftm=my_raw["ftm"],
            fta=my_raw["fta"],
            oreb=my_raw["oreb"],
            dreb=my_raw["dreb"],
            ast=my_raw["ast"],
            stl=my_raw["stl"],
            tov=my_raw["tov"],
            blk=my_raw["blk"],
            opp_fg2a=opp_raw["fg2a"],
            opp_fg3a=opp_raw["fg3a"],
            opp_fta=opp_raw["fta"],
            opp_oreb=opp_raw["oreb"],
            opp_tov=opp_raw["tov"],
            opp_pts_check=opp_raw["pts"],
        )
        fga = my_raw["fg2a"] + my_raw["fg3a"]
        opp_fga = opp_raw["fg2a"] + opp_raw["fg3a"]
        derived["efg_pct"] = _efg(my_raw["fg2m"] + my_raw["fg3m"], my_raw["fg3m"], fga)
        derived["opp_efg_pct"] = _efg(opp_raw["fg2m"] + opp_raw["fg3m"], opp_raw["fg3m"], opp_fga)

        poss = derived["poss"]
        opp_poss = derived["opp_poss"]
        diff_pts_100 = (my_raw["pts"] - opp_raw["pts"]) / poss * 100.0 if poss else 0.0
        diff_efg = derived["efg_pct"] - derived["opp_efg_pct"]
        diff_tov_100 = (my_raw["tov"] / poss - opp_raw["tov"] / opp_poss) * 100.0 if poss and opp_poss else 0.0
        diff_oreb_100 = (my_raw["oreb"] / poss - opp_raw["oreb"] / opp_poss) * 100.0 if poss and opp_poss else 0.0
        diff_ftr = derived["ftr"] - _efg_ftr(opp_raw)

        hdoc: Dict[str, Any] = {
            "match_id": match_id,
            "date": date,
            "season": season,
            "competition": competition,
            "league": "FBCYL",
            "gender": gender,
            "group": group,
            "team_id": my_raw["team_id"],
            "team_name": my_raw["team_name"],
            "is_home": my_raw["team_id"] == home_id,
            "opp_id": opp_raw["team_id"],
            "opp_name": opp_raw["team_name"],
            "pts": my_raw["pts"],
            "opp_pts": opp_raw["pts"],
            "fga": fga,
            "fgm": my_raw["fg2m"] + my_raw["fg3m"],
            "fg2a": my_raw["fg2a"],
            "fg2m": my_raw["fg2m"],
            "fg3a": my_raw["fg3a"],
            "fg3m": my_raw["fg3m"],
            "fta": my_raw["fta"],
            "ftm": my_raw["ftm"],
            "oreb": my_raw["oreb"],
            "dreb": my_raw["dreb"],
            "ast": my_raw["ast"],
            "stl": my_raw["stl"],
            "tov": my_raw["tov"],
            "blk": my_raw["blk"],
            "pf": my_raw["pf"],
            **derived,
            "diff_pts_100": round(diff_pts_100, 3),
            "diff_efg": round(diff_efg, 3),
            "diff_tov_100": round(diff_tov_100, 3),
            "diff_oreb_100": round(diff_oreb_100, 3),
            "diff_ftr": round(diff_ftr, 3),
            "source_collection": source_collection,
            "scraped_at": scraped_at or datetime.utcnow(),
        }
        docs.append(hdoc)
    return docs
