"""PBP quality scoring from play-by-play and official boxscore data."""
from __future__ import annotations

import csv
import io
from typing import Dict, List

from src.services.possession_core import count_quality_pbp_metrics


class PBPQualityService:
    """Compute a global PBP quality score for a single game document."""

    CSV_COLUMNS: List[str] = [
        "ID_Partido", "Coleccion", "Equipo_Local", "Equipo_Rival", "Quality_Score",
    ] + [
        f"{team}_{source}_{metric}"
        for team in ("Local", "Rival")
        for metric in ("T2M", "T2A", "T3M", "T3A", "T1M", "T1A", "RebO", "RebD", "TOV")
        for source in ("PBP", "BS")
    ]

    _QUALITY_METRICS = [
        "T2M", "T2A", "T3M", "T3A", "T1M", "T1A",
        "RebO", "RebD", "TOV",
    ]

    def __init__(
        self,
        game_data: Dict,
        is_fbcyl: bool,
        collection: str,
        game_id: str,
    ):
        self.game_data = game_data
        self.is_fbcyl = is_fbcyl
        self.collection = collection
        self.game_id = game_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self) -> List[Dict]:
        """Return one global quality score row for the game."""
        teams = self._extract_teams()
        if not teams:
            return []

        pbp_counts = self._count_pbp(teams)
        accuracies = self._quality_accuracies(teams, pbp_counts)
        score = sum(accuracies) / len(accuracies) if accuracies else 0.0
        team_rows = list(teams.items())
        local_id, local_info = team_rows[0]
        rival_id, rival_info = team_rows[1] if len(team_rows) > 1 else ("", {"name": "", "boxscore": {}})
        row = {
            "ID_Partido": self.game_id,
            "Coleccion": self.collection,
            "Equipo_Local": local_info["name"],
            "Equipo_Rival": rival_info["name"],
            "Quality_Score": f"{score:.2f}%",
        }
        row.update(self._team_audit_values("Local", local_info, pbp_counts.get(local_id, {})))
        row.update(self._team_audit_values("Rival", rival_info, pbp_counts.get(rival_id, {})))
        return [row]

    def _team_audit_values(
        self,
        team_label: str,
        team_info: Dict,
        pbp_counts: Dict[str, int],
    ) -> Dict[str, int]:
        boxscore = team_info["boxscore"]
        return {
            f"{team_label}_{source}_{metric}": values.get(metric, 0)
            for metric in self._QUALITY_METRICS
            for source, values in (("PBP", pbp_counts), ("BS", boxscore))
        }

    def _quality_accuracies(
        self,
        teams: Dict[str, Dict],
        pbp_counts: Dict[str, Dict[str, int]],
    ) -> List[float]:
        accuracies: List[float] = []
        for tid, info in teams.items():
            boxscore = info["boxscore"]
            pbp = pbp_counts.get(tid, {})
            accuracies.extend(
                self._accuracy(pbp.get(metric, 0), boxscore.get(metric, 0))
                for metric in self._QUALITY_METRICS
            )
        return accuracies

    def to_csv_bytes(self) -> bytes:
        rows = self.compute()
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=self.CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8-sig")

    # ------------------------------------------------------------------
    # Accuracy formula
    # ------------------------------------------------------------------

    @staticmethod
    def _accuracy(pbp: int, bs: int) -> float:
        return max(0.0, 1.0 - abs(pbp - bs) / max(bs, 1)) * 100.0

    # ------------------------------------------------------------------
    # Team metadata + boxscore extraction
    # ------------------------------------------------------------------

    def _extract_teams(self) -> Dict[str, Dict]:
        """Return {team_id: {name, boxscore}} ordered Local first."""
        result: Dict[str, Dict] = {}
        if self.is_fbcyl:
            for team in self.game_data.get("stats", {}).get("teams", [])[:2]:
                tid = str(team.get("teamIdIntern") or team.get("teamIdExtern") or "")
                result[tid] = {
                    "name": team.get("name") or team.get("shortName") or tid,
                    "boxscore": self._fbcyl_boxscore(team),
                }
        else:
            header_teams = self.game_data.get("HEADER", {}).get("TEAM", [])
            header_names = {
                str(team.get("id") or ""): team.get("name")
                for team in header_teams
            }
            for team in self.game_data.get("BOXSCORE", {}).get("TEAM", [])[:2]:
                tid = str(team.get("id") or "")
                result[tid] = {
                    "name": team.get("name") or header_names.get(tid) or tid,
                    "boxscore": self._feb_boxscore(team),
                }
        return result

    @staticmethod
    def _feb_boxscore(team: Dict) -> Dict[str, int]:
        tot = team.get("TOTAL", {})
        return {
            "T2M": int(tot.get("p2m") or 0),
            "T2A": int(tot.get("p2a") or 0),
            "T3M": int(tot.get("p3m") or 0),
            "T3A": int(tot.get("p3a") or 0),
            "T1M": int(tot.get("p1m") or 0),
            "T1A": int(tot.get("p1a") or 0),
            "RebO": int(tot.get("ro") or 0),
            "RebD": int(tot.get("rd") or 0),
            "AST": int(tot.get("assist") or 0),
            "ST": int(tot.get("st") or 0),
            "TOV": int(tot.get("to") or 0),
        }

    @staticmethod
    def _fbcyl_boxscore(team: Dict) -> Dict[str, int]:
        data = team.get("data", {})
        # Offensive/defensive rebounds come from player-level data (team data has total only)
        players = team.get("players", [])
        orebs = sum(int(p.get("data", {}).get("offensiveRebound") or 0) for p in players)
        drebs = sum(int(p.get("data", {}).get("defensiveRebound") or 0) for p in players)
        return {
            "T2M": int(data.get("shotsOfTwoSuccessful") or 0),
            "T2A": int(data.get("shotsOfTwoAttempted") or 0),
            "T3M": int(data.get("shotsOfThreeSuccessful") or 0),
            "T3A": int(data.get("shotsOfThreeAttempted") or 0),
            "T1M": int(data.get("shotsOfOneSuccessful") or 0),
            "T1A": int(data.get("shotsOfOneAttempted") or 0),
            "RebO": orebs,
            "RebD": drebs,
            "AST": int(data.get("assists") or 0),
            "ST":  int(data.get("steals") or 0),
            "TOV": int(data.get("lost") or 0),
        }

    # ------------------------------------------------------------------
    # PBP counting
    # ------------------------------------------------------------------

    def _count_pbp(self, teams: Dict) -> Dict[str, Dict[str, int]]:
        """Count PBP-derived stats per team using shared possession-core logic."""
        team_ids = list(teams.keys())
        return count_quality_pbp_metrics(self.game_data, self.is_fbcyl, team_ids)
