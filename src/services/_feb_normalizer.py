"""FEB match normalizer — extracted from historical_ingestion_service.py."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.numeric_utils import safe_int
from src.services._historical_derived import build_team_docs


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


def _apply_derived(doc: Dict[str, Any], raws: tuple) -> Dict[str, float]:
    """Overwrite rebounds and turnovers with the validated ones of ``DERIVED`` (stored, else derived from the pbp; #372).

    Returns the possessions per team id."""
    from src.pbp.game_derived import derive_game_fields

    derived = ((doc.get("DERIVED") or derive_game_fields(doc)) or {}).get("TEAM") or []
    exact: Dict[str, float] = {}
    for raw, stored in zip(raws, derived):
        if str(stored.get("id")) != raw["team_id"]:
            continue
        raw["oreb"], raw["dreb"], raw["tov"] = stored["orb"], stored["drb"], stored["tov"]
        exact[raw["team_id"]] = stored["possessions"]
    return exact


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
    exact = _apply_derived(doc, (raw0, raw1))

    return build_team_docs(
        (raw0, raw1), exact, match_id=match_id, date=date, season=season, competition=competition,
        league="FEB", gender=None, group=group, home_id=home_id,
        source_collection=source_collection, scraped_at=scraped_at,
    )
