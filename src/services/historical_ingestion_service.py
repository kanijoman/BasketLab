"""Historical ingestion service — orchestrates scraping + normalization + upsert.

Reutiilses the existing FEB/FBCYL scrapers without modification.  For each
downloaded match document it produces **two** HISTORICAL documents (one per
team), pre-computing all derived stats and per-100-possession differentials so
predictive-model queries are simple ``$match`` / ``$group`` pipelines.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.numeric_utils import safe_float, safe_int


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_FEB_DATE_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")


def _parse_date(raw: str) -> Optional[datetime]:
    """Parse a date string from FEB/FBCYL into a datetime object.

    Handles the FEB format ``"dd-mm-yyyy - HH:MM"`` and falls back to ISO.
    """
    if not raw:
        return None
    m = _FEB_DATE_RE.search(raw)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(year, month, day)
    try:
        return datetime.fromisoformat(raw[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Derived-stats computation (mirrors stats_calculator.py formulas)
# ---------------------------------------------------------------------------

def _compute_derived(
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
) -> Dict[str, float]:
    """Compute possession-based derived stats.

    All formulas are identical to those in ``StatsCalculator`` so both layers
    stay consistent.  Uses the same 0.45 FT coefficient.
    """
    fga = fg2a + fg3a
    opp_fga = opp_fg2a + opp_fg3a
    fgm = fg2m + fg3m

    poss = fga + 0.45 * fta + tov - oreb
    poss = max(poss, 1.0)  # guard against divide-by-zero with degenerate data

    opp_poss = opp_fga + 0.45 * opp_fta + opp_tov - opp_oreb
    opp_poss = max(opp_poss, 1.0)

    pace = (poss + opp_poss) / 2.0

    ortg = pts / poss * 100.0
    drtg = opp_pts / opp_poss * 100.0
    net_rtg = ortg - drtg

    efg_pct = ((fgm + 0.5 * fg3m) / fga * 100.0) if fga > 0 else 0.0
    opp_efg_pct = (
        ((opp_fg2a - opp_fg2a + opp_fg3m_approx) / opp_fga * 100.0)
        if opp_fga > 0
        else 0.0
    ) if False else 0.0  # placeholder; opp_efg computed from opp doc

    tov_rate = tov / poss * 100.0
    oreb_pct = oreb / (oreb + (dreb)) * 100.0 if (oreb + dreb) > 0 else 0.0
    ftr = fta / fga * 100.0 if fga > 0 else 0.0
    fg3a_rate = fg3a / fga * 100.0 if fga > 0 else 0.0

    return {
        "poss": round(poss, 2),
        "opp_poss": round(opp_poss, 2),
        "pace": round(pace, 2),
        "ortg": round(ortg, 2),
        "drtg": round(drtg, 2),
        "net_rtg": round(net_rtg, 2),
        "efg_pct": 0.0,  # filled by caller using both teams' data
        "opp_efg_pct": 0.0,  # filled by caller
        "tov_rate": round(tov_rate, 2),
        "oreb_pct": round(oreb_pct, 2),
        "ftr": round(ftr, 2),
        "fg3a_rate": round(fg3a_rate, 2),
    }


def _efg(fgm: int, fg3m: int, fga: int) -> float:
    if fga <= 0:
        return 0.0
    return round((fgm + 0.5 * fg3m) / fga * 100.0, 2)


# ---------------------------------------------------------------------------
# FEB normalizer
# ---------------------------------------------------------------------------

def _extract_feb_team_raw(team_box: Dict[str, Any]) -> Dict[str, Any]:
    """Extract raw integer stats from a FEB BOXSCORE.TEAM entry (via TOTAL)."""
    total = team_box.get("TOTAL") or {}
    return {
        "team_id": str(team_box.get("id", "")),
        "team_name": str(team_box.get("name", "")),
        "win_lose": str(team_box.get("win_lose", "")),
        "pts": safe_int(total.get("pts", 0)),
        "fg2m": safe_int(total.get("p2m", 0)),
        "fg2a": safe_int(total.get("p2a", 0)),
        "fg3m": safe_int(total.get("p3m", 0)),
        "fg3a": safe_int(total.get("p3a", 0)),
        "ftm": safe_int(total.get("p1m", 0)),
        "fta": safe_int(total.get("p1a", 0)),
        "oreb": safe_int(total.get("ro", 0)),
        "dreb": safe_int(total.get("rd", 0)),
        "ast": safe_int(total.get("assist", 0)),
        "stl": safe_int(total.get("st", 0)),
        "tov": safe_int(total.get("to", 0)),
        "blk": safe_int(total.get("bs", 0)),
        "pf": safe_int(total.get("pf", 0)),
    }


def normalize_feb_match(
    doc: Dict[str, Any],
    season: str,
    competition: str,
    group: str,
    source_collection: str,
    scraped_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Convert a FEB game document into two HISTORICAL documents (one per team).

    Args:
        doc:               Full FEB boxscore document as stored in MongoDB.
        season:            Normalised season label, e.g. ``"2024-25"``.
        competition:       Competition label, e.g. ``"LF2"``.
        group:             Group label, e.g. ``"A"``.
        source_collection: Original collection name for traceability.
        scraped_at:        Ingestion timestamp (defaults to now).

    Returns:
        List of two normalised documents ready for ``upsert_match_team``.
    """
    header = doc.get("HEADER", {})
    teams_box = doc.get("BOXSCORE", {}).get("TEAM", [])

    match_id = str(doc.get("_id") or header.get("game_code", ""))
    date = _parse_date(header.get("starttime", ""))
    header_teams = header.get("TEAM", [])
    # home team is index 0 in HEADER.TEAM for FEB
    home_id = str(header_teams[0].get("id", "")) if header_teams else ""

    if len(teams_box) != 2:
        return []

    raw0 = _extract_feb_team_raw(teams_box[0])
    raw1 = _extract_feb_team_raw(teams_box[1])

    docs = []
    for my_raw, opp_raw in ((raw0, raw1), (raw1, raw0)):
        derived = _compute_derived(
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

        # Per-100 differentials
        poss = derived["poss"]
        diff_pts_100 = (my_raw["pts"] - opp_raw["pts"]) / poss * 100.0 if poss else 0.0
        diff_efg = derived["efg_pct"] - derived["opp_efg_pct"]
        opp_poss = derived["opp_poss"]
        diff_tov_100 = (my_raw["tov"] / poss - opp_raw["tov"] / opp_poss) * 100.0 if poss and opp_poss else 0.0
        diff_oreb_100 = (my_raw["oreb"] / poss - opp_raw["oreb"] / opp_poss) * 100.0 if poss and opp_poss else 0.0
        diff_ftr = (derived["ftr"] - (_efg_ftr(opp_raw)))

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
            # Raw stats
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
            # Derived
            **derived,
            # Differentials
            "diff_pts_100": round(diff_pts_100, 3),
            "diff_efg": round(diff_efg, 3),
            "diff_tov_100": round(diff_tov_100, 3),
            "diff_oreb_100": round(diff_oreb_100, 3),
            "diff_ftr": round(diff_ftr, 3),
            # Metadata
            "source_collection": source_collection,
            "scraped_at": scraped_at or datetime.utcnow(),
        }
        docs.append(hdoc)
    return docs


def _efg_ftr(raw: Dict[str, Any]) -> float:
    """FT rate for opponent (FTA / FGA)."""
    fga = raw["fg2a"] + raw["fg3a"]
    return raw["fta"] / fga * 100.0 if fga > 0 else 0.0


# ---------------------------------------------------------------------------
# FBCYL normalizer
# ---------------------------------------------------------------------------

def _extract_fbcyl_team_raw(team: Dict[str, Any]) -> Dict[str, Any]:
    """Extract raw integer stats from a FBCYL stats.teams entry."""
    return {
        "team_id": str(team.get("id", "")),
        "team_name": str(team.get("name", "")),
        "pts": safe_int(team.get("score", 0) or team.get("totalPoints", 0)),
        "fg2m": safe_int(team.get("shotsOfTwoSuccessful", 0)),
        "fg2a": safe_int(team.get("shotsOfTwoAttempted", 0)),
        "fg3m": safe_int(team.get("shotsOfThreeSuccessful", 0)),
        "fg3a": safe_int(team.get("shotsOfThreeAttempted", 0)),
        "ftm": safe_int(team.get("shotsOfOneSuccessful", 0)),
        "fta": safe_int(team.get("shotsOfOneAttempted", 0)),
        "oreb": safe_int(team.get("offensiveRebound", 0)),
        "dreb": safe_int(team.get("defensiveRebound", 0)),
        "ast": safe_int(team.get("assists", 0)),
        "stl": safe_int(team.get("steals", 0)),
        "tov": safe_int(team.get("lost", 0)),
        "blk": safe_int(team.get("block", 0)),
        "pf": safe_int(team.get("foulsCommited", 0) or team.get("fouls", 0)),
    }


def normalize_fbcyl_match(
    doc: Dict[str, Any],
    season: str,
    competition: str,
    group: str,
    gender: Optional[str],
    source_collection: str,
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
        scraped_at:        Ingestion timestamp (defaults to now).

    Returns:
        List of two normalised documents ready for ``upsert_match_team``.
    """
    match_id = str(doc.get("_id") or doc.get("uuid", ""))
    stats = doc.get("stats", {})
    teams = stats.get("teams", [])
    date_raw = doc.get("date") or stats.get("date") or ""
    date = _parse_date(str(date_raw))

    if len(teams) != 2:
        return []

    raw0 = _extract_fbcyl_team_raw(teams[0])
    raw1 = _extract_fbcyl_team_raw(teams[1])
    # FBCYL: home team is typically index 0
    home_id = raw0["team_id"]

    docs = []
    for my_raw, opp_raw in ((raw0, raw1), (raw1, raw0)):
        derived = _compute_derived(
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


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class HistoricalIngestionService:
    """Orchestrates downloading a season and storing it in HISTORICAL.

    Designed to run inside a background thread (same pattern as the existing
    scraping jobs) so it can report progress through a shared job-state dict.
    """

    def __init__(self, repository):
        """
        Args:
            repository: ``HistoricalRepository`` instance.
        """
        self._repo = repository

    def ingest_feb_season(
        self,
        job: Dict[str, Any],
        competition_url: str,
        season_value: str,
        group_value: str,
        year: str,
        competition_label: str,
        season_label: str,
        group_label: str,
        normalized_season: str,
    ) -> None:
        """Download every FEB match for one season and upsert into HISTORICAL.

        Updates *job* in place so the caller's progress endpoint reflects live
        state.

        Args:
            job:                Mutable job-state dict (keys: status, total, done, …).
            competition_url:    FEB competition calendar URL.
            season_value:       Season dropdown value for the FEB scraper.
            group_value:        Group dropdown value.
            year:               Year hint for the FEB scraper.
            competition_label:  Human-readable label, e.g. ``"LF2"``.
            season_label:       Human-readable label, e.g. ``"LF2 2025"``.
            group_label:        Human-readable label, e.g. ``"A"``.
            normalized_season:  Normalised season string, e.g. ``"2024-25"``.
        """
        from src.scraper import FEBWebScraper
        from src.database import get_collection_name

        scraper = FEBWebScraper()
        source_col = get_collection_name(competition_label, season_label, group_label)

        job["status"] = "discovering"
        _, session = scraper.get_page_content(year)
        match_codes = scraper.get_matches(
            season_value, group_value, year, session, url=competition_url
        )
        job["total"] = job.get("total", 0) + len(match_codes)
        job["status"] = "running"

        scraped_at = datetime.utcnow()
        for code in match_codes:
            job["current_match"] = code
            try:
                doc = scraper.fetch_boxscore(code, session)
                if not doc:
                    job["errors"].append(f"No data for match {code}")
                    continue
                hdocs = normalize_feb_match(
                    doc,
                    season=normalized_season,
                    competition=competition_label,
                    group=group_label,
                    source_collection=source_col,
                    scraped_at=scraped_at,
                )
                for hdoc in hdocs:
                    self._repo.upsert_match_team(hdoc)
            except Exception as exc:
                job["errors"].append(f"Match {code}: {exc}")
            finally:
                job["done"] = job.get("done", 0) + 1

    def ingest_feb_competition(
        self,
        job: Dict[str, Any],
        competition_url: str,
        competition_label: str,
        year: str,
        seasons: List[Dict[str, str]],
    ) -> None:
        """Download all groups for each selected season into HISTORICAL.

        For every season in *seasons*, auto-discovers the available groups via
        :meth:`FEBWebScraper.get_groups_for_season` and then delegates to
        :meth:`ingest_feb_season` for each discovered group.

        Args:
            job:               Mutable job-state dict (keys: status, total, done, …).
            competition_url:   FEB competition calendar URL.
            competition_label: Human-readable label, e.g. ``"LF2"``.
            year:              Year hint for the FEB scraper session init (e.g. ``"2025"``).
            seasons:           List of ``{season_value, season_label}`` dicts.
        """
        from src.scraper import FEBWebScraper

        _season_re = re.compile(r"\d{4}-\d{2}")
        scraper = FEBWebScraper()

        for season_info in seasons:
            season_value = season_info["season_value"]
            season_label = season_info["season_label"]
            m = _season_re.search(season_label)
            normalized = m.group(0) if m else season_label

            job["current_season"] = normalized
            job["status"] = "discovering"

            groups = scraper.get_groups_for_season(competition_url, season_value)
            if not groups:
                job["errors"].append(
                    f"No se encontraron grupos para {normalized}. "
                    "La temporada puede estar vacía o no disponible."
                )
                continue

            for group_label, group_value in groups:
                self.ingest_feb_season(
                    job=job,
                    competition_url=competition_url,
                    season_value=season_value,
                    group_value=group_value,
                    year=year,
                    competition_label=competition_label,
                    season_label=season_label,
                    group_label=group_label,
                    normalized_season=normalized,
                )

    def ingest_fbcyl_season(
        self,
        job: Dict[str, Any],
        competition_id: str,
        season: str,
        gender: str,
        territory: str,
        category: str,
        competition_label: str,
        normalized_season: str,
    ) -> None:
        """Download every FBCYL match for one season and upsert into HISTORICAL.

        Args:
            job:                Mutable job-state dict.
            competition_id:     FBCYL competition identifier.
            season:             Season identifier used by the FBCYL scraper.
            gender:             Gender string, e.g. ``"F"`` or ``""``.
            territory:          Territory identifier.
            category:           Category identifier.
            competition_label:  Human-readable competition name.
            normalized_season:  Normalised season string, e.g. ``"2024-25"``.
        """
        from src.scraper.fbcyl_scraper import FBCYLWebScraper
        from src.scraper.web_client import WebClient
        from src.database import get_collection_name

        scraper = FBCYLWebScraper(WebClient())
        league_ctx = {
            "gender": gender,
            "territory": territory,
            "category": category,
            "competition_id": competition_id,
            "season": season,
        }
        source_col = get_collection_name(
            f"FBCYL_{competition_label}", season, ""
        )

        job["status"] = "discovering"
        match_uuids = scraper.get_matches(competition_id)
        job["total"] = job.get("total", 0) + len(match_uuids)
        job["status"] = "running"

        scraped_at = datetime.utcnow()
        gender_char = "F" if "f" in gender.lower() else "M" if gender else None

        for uuid in match_uuids:
            job["current_match"] = uuid
            try:
                doc = scraper.get_match_complete_data(uuid, league_ctx=league_ctx)
                if not doc:
                    job["errors"].append(f"No data for match {uuid}")
                    continue
                hdocs = normalize_fbcyl_match(
                    doc,
                    season=normalized_season,
                    competition=competition_label,
                    group="",
                    gender=gender_char,
                    source_collection=source_col,
                    scraped_at=scraped_at,
                )
                for hdoc in hdocs:
                    self._repo.upsert_match_team(hdoc)
            except Exception as exc:
                job["errors"].append(f"Match {uuid}: {exc}")
            finally:
                job["done"] = job.get("done", 0) + 1
