"""Service for single-match analysis and team comparison.

Provides:
- ``get_match_list``   — lightweight catalogue of all matches in a collection
- ``get_match_analysis`` — full head-to-head stats comparison for one match

Supports both FEB and FBCYL document schemas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Stats where a lower value is better (e.g. turnovers, fouls)
_LOWER_IS_BETTER: frozenset = frozenset({"tov", "tov_pct", "pf", "der"})

# Section groupings for the comparison table
_SECTION_MAP: Dict[str, str] = {
    "pts": "General",
    "reb": "General", "orb": "General", "drb": "General",
    "ast": "General", "stl": "General", "blk": "General",
    "tov": "General", "pf": "General",
    "fg_pct": "Tiro", "two_pct": "Tiro", "three_pct": "Tiro", "ft_pct": "Tiro",
    "efg_pct": "Cuatro Factores", "tov_pct": "Cuatro Factores",
    "orb_pct": "Cuatro Factores", "ftr": "Cuatro Factores",
    "possessions": "Posesiones",
    "oer": "Avanzadas", "der": "Avanzadas", "net_rtg": "Avanzadas",
}

# Human-readable labels
_LABELS: Dict[str, str] = {
    "pts": "Puntos",
    "reb": "Rebotes totales", "orb": "Rebotes ofensivos", "drb": "Rebotes defensivos",
    "ast": "Asistencias", "stl": "Robos", "blk": "Tapones",
    "tov": "Pérdidas", "pf": "Faltas personales",
    "fg_pct": "FG%", "two_pct": "2P%", "three_pct": "3P%", "ft_pct": "FT%",
    "efg_pct": "eFG%", "tov_pct": "TOV%", "orb_pct": "ORB%", "ftr": "FTr",
    "possessions": "Posesiones estimadas",
    "oer": "Rating ofensivo", "der": "Rating defensivo", "net_rtg": "Net rating",
}


class MatchAnalysisService:
    """Analyse a single match document, comparing both teams' stats."""

    def __init__(self, db: Any, collection: str) -> None:
        self._db = db
        self._collection = collection

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_match_list(self, is_fbcyl: bool) -> List[Dict]:
        """Return a lightweight list of all matches in the collection."""
        col = self._db.connection.get_collection(self._collection)
        docs = list(col.find({}))
        if is_fbcyl:
            return [self._summary_fbcyl(d) for d in docs]
        return [self._summary_feb(d) for d in docs]

    def get_match_analysis(
        self, match_id: Any, is_fbcyl: bool
    ) -> Optional[Dict]:
        """Return full comparison dict for *match_id*, or ``None`` if not found."""
        col = self._db.connection.get_collection(self._collection)
        doc = col.find_one({"_id": match_id})
        if doc is None:
            return None
        if is_fbcyl:
            return self._analyse_fbcyl(doc)
        return self._analyse_feb(doc)

    # ------------------------------------------------------------------
    # FEB helpers
    # ------------------------------------------------------------------

    def _summary_feb(self, doc: Dict) -> Dict:
        header = doc.get("HEADER", {})
        teams = header.get("TEAM", [{}, {}])
        return {
            "match_id": doc["_id"],
            "date": header.get("starttime", ""),
            "round": header.get("round", ""),
            "venue": header.get("place", ""),
            "home_team": teams[0].get("name", "") if teams else "",
            "away_team": teams[1].get("name", "") if len(teams) > 1 else "",
            "home_score": _safe_int(teams[0].get("pts")) if teams else 0,
            "away_score": _safe_int(teams[1].get("pts")) if len(teams) > 1 else 0,
        }

    def _analyse_feb(self, doc: Dict) -> Dict:
        teams = doc.get("BOXSCORE", {}).get("TEAM", [{}, {}])
        home_raw = self._stats_feb(teams[0] if teams else {})
        away_raw = self._stats_feb(teams[1] if len(teams) > 1 else {})
        home_adv = _compute_advanced(home_raw, away_raw)
        away_adv = _compute_advanced(away_raw, home_raw)
        home = {**home_raw, **home_adv}
        away = {**away_raw, **away_adv}
        return {
            "home": {"team_name": teams[0].get("name", "") if teams else "", **home},
            "away": {"team_name": teams[1].get("name", "") if len(teams) > 1 else "", **away},
            "comparison": _build_comparison(home, away),
        }

    def _stats_feb(self, team: Dict) -> Dict:
        """Extract stats for one FEB TEAM block, preferring TOTAL over player sum.

        Real FEB documents store authoritative aggregates in the TOTAL sub-dict
        (used by historical_ingestion_service, evolution_service, etc.).
        Player-level rows may be incomplete, so we only fall back to summing
        them when TOTAL is absent.
        """
        total = team.get("TOTAL")
        if total:
            return _aggregate_feb_total(total)
        players = [p for p in team.get("PLAYER", []) if _safe_int(p.get("inn")) == 1]
        return _aggregate_feb_players(team, players)

    # ------------------------------------------------------------------
    # FBCYL helpers
    # ------------------------------------------------------------------

    def _summary_fbcyl(self, doc: Dict) -> Dict:
        stats = doc.get("stats", {})
        teams = stats.get("teams", [{}, {}])
        scores = stats.get("score", [{}])
        last = scores[-1] if scores else {}
        return {
            "match_id": doc["_id"],
            "date": stats.get("time", ""),
            "round": "",
            "venue": "",
            "home_team": teams[0].get("name", "") if teams else "",
            "away_team": teams[1].get("name", "") if len(teams) > 1 else "",
            "home_score": last.get("local", 0),
            "away_score": last.get("visit", 0),
        }

    def _analyse_fbcyl(self, doc: Dict) -> Dict:
        teams = doc.get("stats", {}).get("teams", [{}, {}])
        home_raw = _stats_fbcyl(teams[0] if teams else {})
        away_raw = _stats_fbcyl(teams[1] if len(teams) > 1 else {})
        home_adv = _compute_advanced(home_raw, away_raw)
        away_adv = _compute_advanced(away_raw, home_raw)
        home = {**home_raw, **home_adv}
        away = {**away_raw, **away_adv}
        return {
            "home": {"team_name": teams[0].get("name", "") if teams else "", **home},
            "away": {"team_name": teams[1].get("name", "") if len(teams) > 1 else "", **away},
            "comparison": _build_comparison(home, away),
        }


# ---------------------------------------------------------------------------
# Module-level pure helpers (no class state needed)
# ---------------------------------------------------------------------------

def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _pct(num: float, den: float) -> float:
    return round(num / den * 100, 2) if den else 0.0


def _aggregate_feb_total(total: Dict) -> Dict:
    """Extract team stats from a FEB BOXSCORE.TEAM.TOTAL block.

    This is the authoritative source used by historical_ingestion_service and
    the aggregation pipelines.  fgm/fga are derived as p2m+p3m / p2a+p3a
    because the TOTAL dict does not always carry an aggregate fgm/fga field.
    """
    p2m = _safe_int(total.get("p2m"))
    p2a = _safe_int(total.get("p2a"))
    p3m = _safe_int(total.get("p3m"))
    p3a = _safe_int(total.get("p3a"))
    return _build_raw_stats(
        pts=_safe_int(total.get("pts")),
        fgm=p2m + p3m,
        fga=p2a + p3a,
        p2m=p2m, p2a=p2a, p3m=p3m, p3a=p3a,
        p1m=_safe_int(total.get("p1m")),
        p1a=_safe_int(total.get("p1a")),
        orb=_safe_int(total.get("ro")),
        drb=_safe_int(total.get("rd")),
        ast=_safe_int(total.get("assist")),
        stl=_safe_int(total.get("st")),
        tov=_safe_int(total.get("to")),
        blk=_safe_int(total.get("bs")),
        pf =_safe_int(total.get("pf")),
    )


def _aggregate_feb_players(team: Dict, players: List[Dict]) -> Dict:
    """Sum FEB player-level stats into team totals."""
    pts  = sum(_safe_int(p.get("pts"))    for p in players)
    fgm  = sum(_safe_int(p.get("fgm"))    for p in players)
    fga  = sum(_safe_int(p.get("fga"))    for p in players)
    p2m  = sum(_safe_int(p.get("p2m"))    for p in players)
    p2a  = sum(_safe_int(p.get("p2a"))    for p in players)
    p3m  = sum(_safe_int(p.get("p3m"))    for p in players)
    p3a  = sum(_safe_int(p.get("p3a"))    for p in players)
    p1m  = sum(_safe_int(p.get("p1m"))    for p in players)
    p1a  = sum(_safe_int(p.get("p1a"))    for p in players)
    orb  = sum(_safe_int(p.get("ro"))     for p in players)
    drb  = sum(_safe_int(p.get("rd"))     for p in players)
    ast  = sum(_safe_int(p.get("assist")) for p in players)
    stl  = sum(_safe_int(p.get("st"))     for p in players)
    tov  = sum(_safe_int(p.get("to"))     for p in players)
    blk  = sum(_safe_int(p.get("bs"))     for p in players)
    pf   = sum(_safe_int(p.get("pf"))     for p in players)
    return _build_raw_stats(pts, fgm, fga, p2m, p2a, p3m, p3a, p1m, p1a,
                            orb, drb, ast, stl, tov, blk, pf)


def _stats_fbcyl(team: Dict) -> Dict:
    """Aggregate FBCYL player data entries into team totals."""
    players = team.get("players", [])
    data_list = [p.get("data", {}) for p in players]
    pts = sum(d.get("score", 0)                    for d in data_list)
    fgm = sum(d.get("shotsOfTwoSuccessful", 0) + d.get("shotsOfThreeSuccessful", 0) for d in data_list)
    fga = sum(d.get("shotsOfTwoAttempted", 0)  + d.get("shotsOfThreeAttempted", 0)  for d in data_list)
    p2m = sum(d.get("shotsOfTwoSuccessful", 0)     for d in data_list)
    p2a = sum(d.get("shotsOfTwoAttempted", 0)      for d in data_list)
    p3m = sum(d.get("shotsOfThreeSuccessful", 0)   for d in data_list)
    p3a = sum(d.get("shotsOfThreeAttempted", 0)    for d in data_list)
    p1m = sum(d.get("shotsOfOneSuccessful", 0)     for d in data_list)
    p1a = sum(d.get("shotsOfOneAttempted", 0)      for d in data_list)
    orb = sum(d.get("offensiveRebound", 0)         for d in data_list)
    drb = sum(d.get("defensiveRebound", 0)         for d in data_list)
    ast = sum(d.get("assists", 0)                  for d in data_list)
    stl = sum(d.get("steals", 0)                   for d in data_list)
    tov = sum(d.get("lost", 0)                     for d in data_list)
    blk = sum(d.get("block", 0)                    for d in data_list)
    pf  = sum(d.get("personal", 0)                 for d in data_list)
    return _build_raw_stats(pts, fgm, fga, p2m, p2a, p3m, p3a, p1m, p1a,
                            orb, drb, ast, stl, tov, blk, pf)


def _build_raw_stats(
    pts, fgm, fga, p2m, p2a, p3m, p3a, p1m, p1a,
    orb, drb, ast, stl, tov, blk, pf,
) -> Dict:
    """Assemble the raw + percentage stats dict from counting stats."""
    return {
        "pts": pts,
        "fgm": fgm, "fga": fga,
        "p2m": p2m, "p2a": p2a,
        "p3m": p3m, "p3a": p3a,
        "p1m": p1m, "p1a": p1a,
        "orb": orb, "drb": drb, "reb": orb + drb,
        "ast": ast, "stl": stl, "tov": tov, "blk": blk, "pf": pf,
        "fg_pct":    _pct(fgm, fga),
        "two_pct":   _pct(p2m, p2a),
        "three_pct": _pct(p3m, p3a),
        "ft_pct":    _pct(p1m, p1a),
    }


def _compute_advanced(stats: Dict, opp: Dict) -> Dict:
    """Compute Four Factors + possession-based ratings for one team."""
    fga, fgm  = stats["fga"], stats["fgm"]
    p3m, p3a  = stats["p3m"], stats["p3a"]
    p1a       = stats["p1a"]
    orb       = stats["orb"]
    opp_drb   = opp["drb"]
    tov       = stats["tov"]
    pts       = stats["pts"]

    poss = max(fga - orb + tov + 0.44 * p1a, 1.0)
    opp_poss = max(opp["fga"] - opp["orb"] + opp["tov"] + 0.44 * opp["p1a"], 1.0)

    efg_pct = round((fgm + 0.5 * p3m) / fga * 100, 2) if fga else 0.0
    tov_pct = round(tov / (fga + 0.44 * p1a + tov) * 100, 2) if (fga + 0.44 * p1a + tov) else 0.0
    orb_pct = round(orb / (orb + opp_drb) * 100, 2) if (orb + opp_drb) else 0.0
    ftr     = round(p1a / fga, 3) if fga else 0.0

    oer = round(pts / poss * 100, 2)
    der = round(opp["pts"] / opp_poss * 100, 2)

    return {
        "efg_pct": efg_pct,
        "tov_pct": tov_pct,
        "orb_pct": orb_pct,
        "ftr":     ftr,
        "possessions": round(poss, 1),
        "oer":     oer,
        "der":     der,
        "net_rtg": round(oer - der, 2),
    }


def _comparison_row(
    stat_key: str, home_val: float, away_val: float
) -> Dict:
    """Build one comparison row with winner, delta, and metadata."""
    lib = stat_key in _LOWER_IS_BETTER
    delta = round(home_val - away_val, 2)
    if abs(delta) < 0.001:
        winner = "tie"
    elif lib:
        winner = "home" if home_val < away_val else "away"
    else:
        winner = "home" if home_val > away_val else "away"
    return {
        "stat_key":       stat_key,
        "label":          _LABELS.get(stat_key, stat_key),
        "section":        _SECTION_MAP.get(stat_key, "General"),
        "home_value":     home_val,
        "away_value":     away_val,
        "delta":          delta,
        "winner":         winner,
        "lower_is_better": lib,
    }


def _build_comparison(home: Dict, away: Dict) -> List[Dict]:
    """Build the full ordered comparison list from two stats dicts."""
    keys = list(_LABELS.keys())
    return [
        _comparison_row(k, home.get(k, 0.0), away.get(k, 0.0))
        for k in keys
    ]
