"""Live collection → HISTORICAL-schema adapter (Opción B, FASE 5 extension).

Reads game documents from a live FEB or FBCYL collection and converts them
to the same record schema produced by ``normalize_feb_match`` /
``normalize_fbcyl_match``, so ``MonteCarloService`` can operate on the current
season without ingesting it into HISTORICAL (which would contaminate elasticity
training data).

Usage::

    adapter = LiveHistoryAdapter(connection)
    records = adapter.get_team_history(
        collection_name="FBCYL_Femenino_FBCYL_1ª_DIVISION_FEMENINA_Temporada_20252026",
        team_name="BALONCESTO ARELSA",
        is_fbcyl=True,
    )
    # records → [{net_rtg, efg_pct, tov_rate, oreb_pct, ortg, drtg, date, ...}, ...]
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from services.historical_ingestion_service import (
    normalize_feb_match,
    normalize_fbcyl_match,
)

_SEASON_RE = re.compile(r"Temporada_(\d{4})(\d{4})")


def _derive_season(collection_name: str) -> str:
    """Derive a normalised season string from a collection name.

    Example: ``"FBCYL_..._Temporada_20252026"`` → ``"2025-26"``
    Falls back to the raw collection name if the pattern is not found.
    """
    m = _SEASON_RE.search(collection_name)
    if m:
        y1, y2 = m.group(1), m.group(2)
        return f"{y1}-{y2[2:]}"
    return collection_name


class LiveHistoryAdapter:
    """Convert live FEB/FBCYL partition documents to HISTORICAL-compatible records.

    One call to ``get_team_history`` fetches all matches for a team from a live
    collection and normalises them on-the-fly, returning the same field set that
    ``HistoricalRepository.get_team_history`` would return.  No writes to the DB.
    """

    def __init__(self, connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_team_history(
        self,
        collection_name: str,
        team_name: str,
        is_fbcyl: bool,
    ) -> List[Dict[str, Any]]:
        """Return per-game records for a team from a live collection.

        Args:
            collection_name: MongoDB collection name (e.g. ``"FBCYL_..."``)
            team_name:       Exact team name as stored in the collection.
            is_fbcyl:        True for FBCYL format, False for FEB format.

        Returns:
            List of HISTORICAL-schema dicts sorted chronologically, or ``[]``
            on connection error / no data.
        """
        if not self._conn.is_connected():
            return []

        season = _derive_season(collection_name)

        if is_fbcyl:
            return self._load_fbcyl(collection_name, team_name, season)
        return self._load_feb(collection_name, team_name, season)

    # ------------------------------------------------------------------
    # Internal loaders
    # ------------------------------------------------------------------

    def _load_fbcyl(
        self,
        collection_name: str,
        team_name: str,
        season: str,
    ) -> List[Dict[str, Any]]:
        col = self._conn.get_collection(collection_name)
        try:
            raw_docs = list(col.find({"stats.teams.name": team_name}, {"_id": 0}))
        except Exception:
            return []

        records: List[Dict[str, Any]] = []
        for doc in raw_docs:
            try:
                hdocs = normalize_fbcyl_match(
                    doc,
                    season=season,
                    competition=collection_name,
                    group="",
                    gender=None,
                    source_collection=collection_name,
                )
                for r in hdocs:
                    if r.get("team_name") == team_name:
                        records.append(r)
                        break
            except Exception:
                continue

        records.sort(key=lambda r: r.get("date") or datetime.min)
        return records

    def _load_feb(
        self,
        collection_name: str,
        team_name: str,
        season: str,
    ) -> List[Dict[str, Any]]:
        col = self._conn.get_collection(collection_name)
        try:
            raw_docs = list(
                col.find(
                    {"BOXSCORE.TEAM": {"$elemMatch": {"name": team_name}}},
                    {"_id": 0},
                )
            )
        except Exception:
            return []

        records: List[Dict[str, Any]] = []
        for doc in raw_docs:
            try:
                hdocs = normalize_feb_match(
                    doc,
                    season=season,
                    competition=collection_name,
                    group="",
                    source_collection=collection_name,
                )
                for r in hdocs:
                    if r.get("team_name") == team_name:
                        records.append(r)
                        break
            except Exception:
                continue

        records.sort(key=lambda r: r.get("date") or datetime.min)
        return records
