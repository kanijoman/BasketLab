"""FBCYL match normalizer — extracted from historical_ingestion_service.py."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.numeric_utils import safe_int
from src.services._historical_derived import build_team_docs


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

    return build_team_docs(
        (raw0, raw1), None, match_id=match_id, date=date, season=season, competition=competition,
        league="FBCYL", gender=gender, group=group, home_id=home_id,
        source_collection=source_collection, scraped_at=scraped_at,
    )
