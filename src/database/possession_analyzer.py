"""Possession analyzer — aggregated duration/efficiency stats from play-by-play."""
from __future__ import annotations

from typing import Any, Dict, List

from src.pbp.possession_core import extract_possession_rows, is_tab_evaluated_possession


class PossessionAnalyzer:
    """Aggregated pace/OER stats per team from play-by-play data."""

    def __init__(self, game_data: Dict, is_fbcyl: bool = False):
        self.game_data = game_data
        self.is_fbcyl = is_fbcyl
        if is_fbcyl:
            self.moves = game_data.get("moves", [])
        else:
            pbp = game_data.get("PLAYBYPLAY", {})
            self.moves = pbp.get("LINES", [])
        self.team_mapping = self._get_team_mapping()

    def _get_team_mapping(self) -> Dict[str, str]:
        if self.is_fbcyl:
            stats = self.game_data.get("stats", {})
            teams = stats.get("teams", [])
            if len(teams) >= 2:
                t1 = teams[0].get("teamIdIntern") or teams[0].get("teamIdExtern")
                t2 = teams[1].get("teamIdIntern") or teams[1].get("teamIdExtern")
                return {t1: "team1", t2: "team2"}
        else:
            teams = self.game_data.get("HEADER", {}).get("TEAM", [])
            if len(teams) >= 2:
                return {teams[0].get("id"): "team1", teams[1].get("id"): "team2"}
        return {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_possessions(self, team_id: str) -> Dict[str, Any]:
        """Return aggregated possession stats: total, avg duration, per-bucket OER."""
        team_id_str = str(team_id)
        possessions = self._run_possession_state_machine(
            self.moves,
            team_id_str,
            orebs=set(),
            sfouls=set(),
            and1s=set(),
        )
        return self._aggregate_possession_stats(possessions)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _run_possession_state_machine(
        self,
        moves: List[Dict],
        team_id_str: str,
        orebs: set,
        sfouls: set,
        and1s: set,
    ) -> List[Dict]:
        del moves, orebs, sfouls, and1s
        team_info = self._core_team_info()
        rows = extract_possession_rows(
            game_data=self.game_data,
            is_fbcyl=self.is_fbcyl,
            game_id="ANALYZER",
            team_info=team_info,
        )
        possessions: List[Dict] = []
        for row in rows:
            if str(row.get("Equipo_ID") or "") != team_id_str:
                continue
            if not is_tab_evaluated_possession(row):
                continue
            possessions.append({
                "duration": int(row.get("Duracion_posesion") or 0),
                "points": int(row.get("Puntos_obtenidos") or 0),
                "start_time": 0,
                "end_time": 0,
            })
        return possessions

    def _core_team_info(self) -> Dict[str, Dict]:
        """Build minimal team metadata required by the shared possession core."""
        result: Dict[str, Dict] = {}
        if self.is_fbcyl:
            teams = self.game_data.get("stats", {}).get("teams", [])
            for idx, team in enumerate(teams[:2]):
                tid = str(team.get("teamIdIntern") or team.get("teamIdExtern") or "")
                result[tid] = {
                    "name": team.get("name") or team.get("shortName") or tid,
                    "home_away": "Local" if idx == 0 else "Visitante",
                }
            return result

        teams = self.game_data.get("HEADER", {}).get("TEAM", [])
        for idx, team in enumerate(teams[:2]):
            tid = str(team.get("id") or "")
            result[tid] = {
                "name": team.get("name") or tid,
                "home_away": "Local" if idx == 0 else "Visitante",
            }
        return result

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate_possession_stats(self, possessions: List[Dict]) -> Dict[str, Any]:
        if not possessions:
            return {
                "total_possessions": 0,
                "avg_duration": 0.0,
                "possessions_by_duration": {
                    "<=8s":  {"count": 0, "percentage": 0.0, "total_points": 0, "oer": 0.0},
                    "8-16s": {"count": 0, "percentage": 0.0, "total_points": 0, "oer": 0.0},
                    ">16s":  {"count": 0, "percentage": 0.0, "total_points": 0, "oer": 0.0},
                },
            }

        short = [p for p in possessions if p["duration"] <= 8]
        med   = [p for p in possessions if 8 < p["duration"] <= 16]
        long_ = [p for p in possessions if p["duration"] > 16]
        total = len(possessions)
        avg   = sum(p["duration"] for p in possessions) / total

        def _bucket(lst):
            cnt = len(lst)
            pts = sum(p["points"] for p in lst)
            return {
                "count": cnt,
                "percentage": round(cnt / total * 100, 1),
                "total_points": pts,
                "oer": round(pts / cnt * 100, 2) if cnt else 0.0,
            }

        return {
            "total_possessions": total,
            "avg_duration": round(avg, 2),
            "possessions_by_duration": {
                "<=8s":  _bucket(short),
                "8-16s": _bucket(med),
                ">16s":  _bucket(long_),
            },
        }
