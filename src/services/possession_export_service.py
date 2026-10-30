"""Per-possession CSV export service for possession analysis."""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, Iterator, List, Optional

from src.pbp.possession_core import (
    extract_possession_rows,
    is_controversial_possession,
    is_tab_evaluated_possession,
)


class PossessionExportService:
    """Extracts per-possession rows ready for CSV export from a single game document."""

    CSV_COLUMNS = [
        "ID_Partido", "Equipo", "Equipo_ID", "Rival", "Rival_ID",
        "Local_Visitante", "Cuarto", "Tiempo_de_juego",
        "Diferencia_marcador", "Origen_posesion", "Duracion_posesion",
        "Tipo_finalizacion", "Puntos_obtenidos", "Tiene_rebote_ofensivo",
        "Controversial_Possession",
    ]

    @staticmethod
    def is_controversial_possession(duration: int, points: int) -> bool:
        """Mark possessions that merit manual review in the raw export.

        Real but ambiguous possessions (e.g. 0-second scores, long durations) are kept
        and flagged here; rows the possessions tab itself excludes (ownership-correction
        artifacts, implausible durations) are dropped entirely instead (see
        extract_possessions / is_tab_evaluated_possession).
        """
        return is_controversial_possession(duration, points)

    @staticmethod
    def game_id_of(game_doc: Dict) -> str:
        """The id of a game document as text (an extended-JSON id keeps its inner value)."""
        raw_id = game_doc.get("_id", "")
        if isinstance(raw_id, dict):
            raw_id = raw_id.get("$numberInt") or raw_id.get("$oid") or str(raw_id)
        return str(raw_id)

    @classmethod
    def csv_chunks(cls, db_handler: Any, collection_name: str, team_id: Optional[str] = None) -> Iterator[str]:
        """The text of the per-possession CSV of a collection, game by game: the header once, in the first chunk, and no BOM (the file takes it once, at its start)."""
        is_fbcyl = "FBCYL" in collection_name.upper()
        header_sent = False
        for game_doc in cls.iter_collection(db_handler, collection_name, team_id):
            rows = cls(game_doc, is_fbcyl, cls.game_id_of(game_doc)).extract_possessions()
            if not rows:
                continue
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=cls.CSV_COLUMNS, extrasaction="ignore")
            if not header_sent:
                writer.writeheader()
                header_sent = True
            writer.writerows(rows)
            yield buf.getvalue()

    def __init__(self, game_data: Dict, is_fbcyl: bool, game_id: str):
        self.game_data = game_data
        self.is_fbcyl = is_fbcyl
        self.game_id = game_id
        if is_fbcyl:
            self.moves: List[Dict] = game_data.get("moves", [])
        else:
            pbp = game_data.get("PLAYBYPLAY", {})
            self.moves = pbp.get("LINES", [])
        self.team_info: Dict[str, Dict] = self._build_team_info()

    # ------------------------------------------------------------------
    # Team metadata
    # ------------------------------------------------------------------

    def _build_team_info(self) -> Dict[str, Dict]:
        result: Dict[str, Dict] = {}
        if self.is_fbcyl:
            teams = self.game_data.get("stats", {}).get("teams", [])
            for idx, team in enumerate(teams[:2]):
                tid = str(team.get("teamIdIntern") or team.get("teamIdExtern") or "")
                result[tid] = {
                    "name": team.get("name") or team.get("shortName") or tid,
                    "home_away": "Local" if idx == 0 else "Visitante",
                }
        else:
            for idx, team in enumerate(self.game_data.get("HEADER", {}).get("TEAM", [])[:2]):
                tid = str(team.get("id") or "")
                result[tid] = {
                    "name": team.get("name") or tid,
                    "home_away": "Local" if idx == 0 else "Visitante",
                }
        return result

    # ------------------------------------------------------------------
    # Core extraction
    # ------------------------------------------------------------------

    def extract_possessions(self) -> List[Dict]:
        """Return one dict per possession with all CSV columns populated.

        Filtered to exactly the possessions the possessions tab evaluates for its
        OER/pace stats, so the export and the tab are always in sync.
        """
        rows = extract_possession_rows(
            game_data=self.game_data,
            is_fbcyl=self.is_fbcyl,
            game_id=self.game_id,
            team_info=self.team_info,
        )
        return [row for row in rows if is_tab_evaluated_possession(row)]

    # ------------------------------------------------------------------
    # CSV rendering
    # ------------------------------------------------------------------

    def to_csv_bytes(self) -> bytes:
        rows = self.extract_possessions()
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=self.CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8-sig")

    # ------------------------------------------------------------------
    # Collection iteration helper
    # ------------------------------------------------------------------

    @staticmethod
    def iter_collection(
        db_handler: Any,
        collection_name: str,
        team_id: Optional[str] = None,
    ) -> Iterator[Dict]:
        """Yield raw game documents from *collection_name* that contain play-by-play."""
        repo = db_handler.repository
        is_fbcyl = "FBCYL" in collection_name.upper()

        pbp_filter: Dict = {}
        if is_fbcyl:
            pbp_filter = {"moves": {"$exists": True, "$not": {"$size": 0}}}
            if team_id:
                pbp_filter["stats.teams.teamIdIntern"] = team_id
        else:
            pbp_filter = {"PLAYBYPLAY.LINES": {"$exists": True, "$not": {"$size": 0}}}
            if team_id:
                pbp_filter["$or"] = [
                    {"HEADER.TEAM.0.id": team_id},
                    {"HEADER.TEAM.1.id": team_id},
                ]

        try:
            col = repo.connection.get_collection(collection_name)
            yield from col.find(pbp_filter)
        except Exception:
            return
