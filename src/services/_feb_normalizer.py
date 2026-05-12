"""FEB match normalizer — extracted from historical_ingestion_service.py."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.numeric_utils import safe_int
from src.services._historical_derived import compute_derived, _efg, _efg_ftr


def extract_feb_team_raw(team_box: Dict[str, Any]) -> Dict[str, Any]:
    """Extract raw integer stats from a FEB BOXSCORE.TEAM entry (via TOTAL)."""
    total = team_box.get("TOTAL") or {}
    return {
        "team_id":   str(team_box.get("id", "")),
        "team_name": str(team_box.get("name", "")),
        "win_lose":  str(team_box.get("win_lose", "")),
        "pts":  safe_int(total.get("pts", 0)),
        "fg2m": safe_int(total.get("p2m", 0)),
        "fg2a": safe_int(total.get("p2a", 0)),
        "fg3m": safe_int(total.get("p3m", 0)),
        "fg3a": safe_int(total.get("p3a", 0)),
        "ftm":  safe_int(total.get("p1m", 0)),
        "fta":  safe_int(total.get("p1a", 0)),
        "oreb": safe_int(total.get("ro", 0)),
        "dreb": safe_int(total.get("rd", 0)),
        "ast":  safe_int(total.get("assist", 0)),
        "stl":  safe_int(total.get("st", 0)),
        "tov":  safe_int(total.get("to", 0)),
        "blk":  safe_int(total.get("bs", 0)),
        "pf":   safe_int(total.get("pf", 0)),
    }


def normalize_feb_match(
    doc: Dict[str, Any],
    season: str,
    competition: str,
    group: str,
    source_collection: str,
    parse_date,
    scraped_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Convert a FEB game document into two HISTORICAL documents (one per team).

    Args:
        doc:               Full FEB boxscore document as stored in MongoDB.
        season:            Normalised season label, e.g. ``"2024-25"``.
        competition:       Competition label, e.g. ``"LF2"``.
        group:             Group label, e.g. ``"A"``.
        source_collection: Original collection name for traceability.
        parse_date:        Callable ``(str) -> Optional[datetime]`` — pass
                           ``_parse_date`` from the main module.
        scraped_at:        Ingestion timestamp (defaults to now).

    Returns:
        List of two normalised documents ready for ``upsert_match_team``.
    """
    header = doc.get("HEADER", {})
    teams_box = doc.get("BOXSCORE", {}).get("TEAM", [])

    match_id = str(doc.get("_id") or header.get("game_code", ""))
    date = parse_date(header.get("starttime", ""))
    header_teams = header.get("TEAM", [])
    home_id = str(header_teams[0].get("id", "")) if header_teams else ""

    if len(teams_box) != 2:
        return []

    raw0 = extract_feb_team_raw(teams_box[0])
    raw1 = extract_feb_team_raw(teams_box[1])

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
            "league": "FEB",
            "gender": None,
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
