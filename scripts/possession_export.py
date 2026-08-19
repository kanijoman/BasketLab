#!/usr/bin/env python3
"""
Exportador de posesiones individuales a CSV desde MongoDB (o JSON local).

Dada una colección MongoDB (o un fichero JSON de partido), genera un CSV
con una fila por cada posesión de cada encuentro.

Soporta formatos FEB (PLAYBYPLAY) y FBCYL (moves).

Uso MongoDB:
    python possession_export.py NOMBRE_COLECCION -o posesiones.csv
    python possession_export.py NOMBRE_COLECCION --team-id 982047 -o posesiones.csv

Uso fichero local (pruebas):
    python possession_export.py --json /ruta/partido.json -o posesiones.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is on sys.path so src.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.database.db_config import get_mongodb_connection_string as _get_uri
    _DEFAULT_URI = _get_uri()
except Exception:
    _DEFAULT_URI = os.environ.get("MONGODB_CONNECTION_STRING") or os.environ.get("MONGO_URI", "mongodb://localhost:27017")

# pymongo solo necesario para modo MongoDB
try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def is_fbcyl(collection_name: str) -> bool:
    name = collection_name.lower()
    return any(k in name for k in ("fbcyl", "cyl", "castilla", "leon"))


def unwrap_mongo_extjson(obj: Any) -> Any:
    """Convierte Extended JSON ({'$numberInt': '1'}) a tipos nativos."""
    if isinstance(obj, dict):
        if len(obj) == 1:
            k = next(iter(obj))
            if k == "$numberInt":
                return int(obj[k])
            if k == "$numberLong":
                return int(obj[k])
            if k == "$numberDouble":
                return float(obj[k])
            if k == "$oid":
                return str(obj[k])
            if k == "$date":
                return obj[k]
        return {kk: unwrap_mongo_extjson(vv) for kk, vv in obj.items()}
    if isinstance(obj, list):
        return [unwrap_mongo_extjson(x) for x in obj]
    return obj


def game_id_from_doc(game: Dict) -> str:
    for key in ("id", "gameId", "game_code"):
        v = game.get(key)
        if v is not None:
            return str(v)
    header = game.get("HEADER") or {}
    for key in ("id", "GAME_ID", "game_code"):
        v = header.get(key)
        if v is not None:
            return str(v)
    stats = game.get("stats") or {}
    if stats.get("gameId") is not None:
        return str(stats["gameId"])
    if game.get("_id") is not None:
        return str(game["_id"])
    return "unknown"


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------

def fetch_games(
    client: "MongoClient",
    db_name: str,
    collection_name: str,
    team_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> List[Dict]:
    db = client[db_name]
    col = db[collection_name]
    fbcyl = is_fbcyl(collection_name)

    if fbcyl:
        projection = {
            "moves.move": 1, "moves.period": 1, "moves.min": 1, "moves.sec": 1,
            "moves.idTeam": 1, "stats.teams": 1, "stats.gameId": 1,
            "id": 1, "gameId": 1, "date": 1, "fecha": 1, "_id": 1,
        }
        query: Dict[str, Any] = {"moves": {"$exists": True, "$ne": []}}
        if team_id:
            tid = str(team_id)
            or_c: List[Dict] = [
                {"stats.teams.teamIdIntern": tid},
                {"stats.teams.teamIdExtern": tid},
            ]
            if tid.isdigit():
                or_c += [
                    {"stats.teams.teamIdIntern": int(tid)},
                    {"stats.teams.teamIdExtern": int(tid)},
                ]
            query["$or"] = or_c
    else:
        projection = {
            "PLAYBYPLAY.LINES.text": 1, "PLAYBYPLAY.LINES.quarter": 1,
            "PLAYBYPLAY.LINES.time": 1, "PLAYBYPLAY.LINES.action": 1,
            "PLAYBYPLAY.LINES.idTeam": 1, "HEADER.TEAM": 1,
            "HEADER.id": 1, "HEADER.GAME_ID": 1, "HEADER.game_code": 1,
            "id": 1, "gameId": 1, "game_code": 1, "date": 1, "fecha": 1, "_id": 1,
        }
        query = {"PLAYBYPLAY.LINES": {"$exists": True, "$ne": []}}
        if team_id:
            tid = str(team_id)
            or_c = [{"HEADER.TEAM.id": tid}]
            if tid.isdigit():
                or_c.append({"HEADER.TEAM.id": int(tid)})
            query["$or"] = or_c

    if date_from or date_to:
        date_clauses = []
        for field in ("date", "fecha", "HEADER.date", "HEADER.fecha"):
            d: Dict[str, Any] = {}
            if date_from:
                d["$gte"] = date_from
            if date_to:
                d["$lte"] = date_to
            date_clauses.append({field: d})
        query = {"$and": [query, {"$or": date_clauses}]}

    cursor = col.find(query, projection)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


# ---------------------------------------------------------------------------
# Analizador detallado
# ---------------------------------------------------------------------------

class DetailedPossessionAnalyzer:
    """Extrae posesiones individuales con los campos del CSV."""

    def __init__(self, game_data: Dict, is_fbcyl_fmt: bool, game_id: str):
        self.game_data = game_data
        self.is_fbcyl = is_fbcyl_fmt
        self.game_id = game_id

        if is_fbcyl_fmt:
            self.moves = list(game_data.get("moves") or [])
        else:
            pbp = game_data.get("PLAYBYPLAY") or {}
            self.moves = list(pbp.get("LINES") or [])

        self.team_info = self._build_team_info()
        self.team_ids = list(self.team_info.keys())

    # -- equipos ----------------------------------------------------------

    def _build_team_info(self) -> Dict[str, Dict[str, str]]:
        info: Dict[str, Dict[str, str]] = {}
        if self.is_fbcyl:
            teams = (self.game_data.get("stats") or {}).get("teams") or []
            for i, t in enumerate(teams[:2]):
                tid = str(t.get("teamIdIntern") or t.get("teamIdExtern") or "")
                name = t.get("teamName") or t.get("name") or t.get("shortName") or f"Team{i+1}"
                home_away = "Local" if i == 0 else "Visitante"
                if t.get("isHome") is True:
                    home_away = "Local"
                elif t.get("isHome") is False:
                    home_away = "Visitante"
                if tid:
                    info[tid] = {"name": name, "home_away": home_away}
        else:
            teams = (self.game_data.get("HEADER") or {}).get("TEAM") or []
            for i, t in enumerate(teams[:2]):
                tid = str(t.get("id") or "")
                name = t.get("name") or t.get("n") or f"Team{i+1}"
                # En FEB el primer equipo del HEADER es el local
                home_away = "Local" if i == 0 else "Visitante"
                if t.get("home") is True or str(t.get("ha", "")).upper() in ("H", "HOME"):
                    home_away = "Local"
                elif t.get("home") is False or str(t.get("ha", "")).upper() in ("A", "AWAY"):
                    home_away = "Visitante"
                if tid:
                    info[tid] = {"name": name, "home_away": home_away}
        return info

    def _team_name(self, tid: str) -> str:
        return self.team_info.get(str(tid), {}).get("name", str(tid))

    def _home_away(self, tid: str) -> str:
        return self.team_info.get(str(tid), {}).get("home_away", "")

    def _opponent(self, tid: str) -> str:
        for other in self.team_ids:
            if other != str(tid):
                return other
        return ""

    # -- tiempo -----------------------------------------------------------

    def _get_timestamp(self, move: Dict) -> int:
        if self.is_fbcyl:
            period = int(move.get("period") or 1)
            min_val = int(move.get("min") or 0)
            sec_val = int(move.get("sec") or 0)
            return (period - 1) * 600 + min_val * 60 + sec_val
        try:
            q = int(move.get("quarter") or 1)
            parts = str(move.get("time") or "10:00").split(":")
            if len(parts) == 2:
                m, s = int(parts[0]), int(parts[1])
                elapsed = 600 - (m * 60 + s)
                return (q - 1) * 600 + max(0, elapsed)
        except (ValueError, TypeError):
            pass
        return 0

    def _get_quarter(self, move: Dict) -> int:
        if self.is_fbcyl:
            return int(move.get("period") or 1)
        try:
            return int(move.get("quarter") or 1)
        except (ValueError, TypeError):
            return 1

    def _format_game_clock(self, move: Dict) -> str:
        if self.is_fbcyl:
            m = int(move.get("min") or 0)
            s = int(move.get("sec") or 0)
            return f"{m:02d}:{s:02d}"
        return str(move.get("time") or "10:00")

    def _running_score(self, moves: List[Dict], up_to: int) -> Dict[str, int]:
        score = {tid: 0 for tid in self.team_ids}
        for i in range(min(up_to, len(moves))):
            pts = self._points_from_move(moves[i])
            if pts:
                tid = str(moves[i].get("idTeam") or "")
                if tid in score:
                    score[tid] += pts
        return score

    # -- texto / acción ---------------------------------------------------

    def _move_text(self, move: Dict) -> str:
        if self.is_fbcyl:
            return str(move.get("move") or "")
        return str(move.get("text") or "")

    def _move_text_upper(self, move: Dict) -> str:
        return self._move_text(move).upper()

    def _action_type(self, move: Dict) -> str:
        if self.is_fbcyl:
            return ""
        return str(move.get("action") or "").lower()

    # -- clasificación de eventos (ajustada a FEB real) -------------------

    def _points_from_move(self, move: Dict) -> int:
        """Puntos anotados en este evento (0 si no es canasta)."""
        text = self._move_text(move)
        text_u = text.upper()
        act = self._action_type(move)

        if self.is_fbcyl:
            if "Canasta de 2" in text:
                return 2
            if "Canasta de 3" in text:
                return 3
            if "Canasta de 1" in text or "Tiro libre anotado" in text:
                return 1
            return 0

        # FEB: "TIRO DE 2 ANOTADO", "TIRO DE 3 ANOTADO", "TIRO DE 1 ANOTADO"
        if "FALLADO" in text_u or "FALLA" in text_u:
            return 0
        if "ANOTADO" in text_u or act in ("shoot", "fthrow"):
            if "TIRO DE 3" in text_u or "TRIPLE" in text_u or "CANASTA DE 3" in text_u:
                return 3
            if "TIRO DE 2" in text_u or "CANASTA DE 2" in text_u:
                return 2
            if "TIRO DE 1" in text_u or "TIRO LIBRE" in text_u:
                return 1
        return 0

    def _is_made_fg(self, move: Dict) -> Tuple[bool, int]:
        pts = self._points_from_move(move)
        if pts in (2, 3):
            return True, pts
        return False, 0

    def _is_made_ft(self, move: Dict) -> bool:
        return self._points_from_move(move) == 1

    def _is_missed_fg(self, move: Dict) -> bool:
        text_u = self._move_text_upper(move)
        act = self._action_type(move)
        if self.is_fbcyl:
            text = self._move_text(move)
            return ("Intento fallado" in text or "fallado" in text.lower()) and "de 1" not in text.lower()
        # FEB: TIRO DE 2/3 FALLADO (no TIRO DE 1)
        if "FALLADO" in text_u or "FALLA" in text_u:
            if "TIRO DE 2" in text_u or "TIRO DE 3" in text_u or "TRIPLE" in text_u:
                return True
            if act == "shoot" and "TIRO DE 1" not in text_u:
                return True
        return False

    def _is_missed_ft(self, move: Dict) -> bool:
        text_u = self._move_text_upper(move)
        act = self._action_type(move)
        if self.is_fbcyl:
            text = self._move_text(move)
            return "Intento fallado de 1" in text or ("fallado" in text.lower() and "de 1" in text.lower())
        if ("TIRO DE 1" in text_u or "TIRO LIBRE" in text_u) and ("FALLADO" in text_u or "FALLA" in text_u):
            return True
        if act == "fthrow" and ("FALLADO" in text_u or "FALLA" in text_u):
            return True
        return False

    def _is_turnover(self, move: Dict) -> bool:
        text_u = self._move_text_upper(move)
        act = self._action_type(move)
        return (
            "PÉRDIDA" in text_u
            or "PERDIDA" in text_u
            or act in ("turnover", "lose")
        )

    def _is_rebound(self, move: Dict) -> bool:
        text_u = self._move_text_upper(move)
        act = self._action_type(move)
        return act == "rebound" or "REBOTE" in text_u

    def _is_steal(self, move: Dict) -> bool:
        text_u = self._move_text_upper(move)
        act = self._action_type(move)
        return (
            "ROBO" in text_u
            or "RECUPERA" in text_u
            or act in ("steal", "recovery")
        )

    def _is_last_free_throw(self, idx: int, moves: List[Dict]) -> bool:
        """True si no hay otro TL del mismo equipo inmediatamente después."""
        if idx >= len(moves) - 1:
            return True
        curr_team = str(moves[idx].get("idTeam") or "")
        # Buscar el siguiente evento de tiro libre / fthrow del mismo equipo
        for j in range(idx + 1, min(idx + 4, len(moves))):
            nxt = moves[j]
            nxt_team = str(nxt.get("idTeam") or "")
            nxt_u = self._move_text_upper(nxt)
            act = self._action_type(nxt)
            # Sustituciones / faltas intermedias no rompen la secuencia de TL
            if act in ("subst", "foul", "timeout", "assist"):
                continue
            if nxt_team != curr_team:
                return True
            if (
                "TIRO DE 1" in nxt_u
                or "TIRO LIBRE" in nxt_u
                or act == "fthrow"
                or (self.is_fbcyl and ("Canasta de 1" in self._move_text(nxt) or "Intento fallado de 1" in self._move_text(nxt)))
            ):
                return False
            # Cualquier otro evento del mismo equipo → ya no es secuencia de TL
            return True
        return True

    def _classify_ending(self, move: Dict, points: int) -> str:
        text_u = self._move_text_upper(move)
        if self._is_turnover(move):
            return "perdida"
        if points == 3 or "TIRO DE 3" in text_u or "TRIPLE" in text_u:
            return "triple"
        if points == 1 or "TIRO DE 1" in text_u or "TIRO LIBRE" in text_u:
            return "tiros_libres"
        if points == 2 or "TIRO DE 2" in text_u:
            if any(k in text_u for k in ("BANDEJA", "LAYUP", "ENTRADA")):
                return "bandeja"
            if any(k in text_u for k in ("MATE", "DUNK")):
                return "mate"
            return "tiro_2"
        if self._is_missed_fg(move) or self._is_missed_ft(move):
            return "tiro_fallado"
        if self._is_rebound(move):
            return "rebote_defensivo"
        if self._is_steal(move):
            return "recuperacion"
        return "otro"

    def _classify_origin(
        self,
        prev_ending: Optional[str],
        start_move: Optional[Dict],
        is_period_start: bool,
    ) -> str:
        if is_period_start:
            return "saque_inicial_periodo"
        if prev_ending is None:
            return "inicio_partido"
        mapping = {
            "triple": "saque_fondo",
            "tiro_2": "saque_fondo",
            "bandeja": "saque_fondo",
            "mate": "saque_fondo",
            "tiros_libres": "saque_fondo",
            "perdida": "recuperacion",
            "tiro_fallado": "rebote_defensivo",
            "rebote_defensivo": "rebote_defensivo",
            "recuperacion": "recuperacion",
        }
        origin = mapping.get(prev_ending or "", "otro")
        if start_move:
            if self._is_steal(start_move):
                return "recuperacion"
            if self._is_rebound(start_move):
                return origin if origin != "otro" else "rebote_defensivo"
        return origin

    # -- preprocesado -----------------------------------------------------

    def _detect_offensive_rebounds(self, moves: List[Dict]) -> Set[int]:
        """Índices de tiros fallados (campo o TL) seguidos de rebote ofensivo propio."""
        indices: Set[int] = set()
        for i, move in enumerate(moves):
            if not self._is_rebound(move):
                continue
            curr_team = str(move.get("idTeam") or "")
            for lookback in range(1, min(4, i + 1)):
                prev = moves[i - lookback]
                prev_team = str(prev.get("idTeam") or "")
                act = self._action_type(prev)
                if act in ("subst", "foul", "timeout", "assist"):
                    continue
                if self._is_missed_fg(prev) or self._is_missed_ft(prev):
                    if prev_team == curr_team:
                        indices.add(i - lookback)
                    break
                prev_u = self._move_text_upper(prev)
                if (("ANOTADO" in prev_u) and "FALLADO" not in prev_u) or "PÉRDIDA" in prev_u or "PERDIDA" in prev_u:
                    break
                if self._is_rebound(prev) or self._is_steal(prev):
                    break
        return indices

    def _detect_shooting_foul_indices(self, moves: List[Dict]) -> Set[int]:
        indices: Set[int] = set()
        for i, move in enumerate(moves):
            if not self._is_missed_fg(move):
                continue
            team = str(move.get("idTeam") or "")
            for j in range(i + 1, min(i + 5, len(moves))):
                nxt = moves[j]
                nxt_team = str(nxt.get("idTeam") or "")
                nxt_u = self._move_text_upper(nxt)
                act = self._action_type(nxt)
                if act in ("subst", "foul", "timeout"):
                    continue
                if nxt_team == team:
                    if (
                        "TIRO DE 1" in nxt_u
                        or "TIRO LIBRE" in nxt_u
                        or act == "fthrow"
                        or (self.is_fbcyl and ("Canasta de 1" in self._move_text(nxt) or "de 1" in self._move_text(nxt).lower()))
                    ):
                        indices.add(i)
                        break
                if self._is_rebound(nxt) or self._is_steal(nxt):
                    break
                if "ANOTADO" in nxt_u and "FALLADO" not in nxt_u:
                    break
                if "PÉRDIDA" in nxt_u or "PERDIDA" in nxt_u:
                    break
        return indices

    def _detect_and1_indices(self, moves: List[Dict]) -> Set[int]:
        """Índices de canastas de campo seguidas de TL del mismo equipo (and-1).

        En and-1 la posesión NO termina con la canasta: continúa con el tiro libre.
        """
        indices: Set[int] = set()
        for i, move in enumerate(moves):
            is_fg, _ = self._is_made_fg(move)
            if not is_fg:
                continue
            team = str(move.get("idTeam") or "")
            for j in range(i + 1, min(i + 8, len(moves))):
                nxt = moves[j]
                nxt_team = str(nxt.get("idTeam") or "")
                act = self._action_type(nxt)
                nxt_u = self._move_text_upper(nxt)
                # Ignorar sustituciones, asistencias, timeouts y la falta del defensor
                if act in ("subst", "assist", "timeout", "foul"):
                    continue
                # TL del mismo equipo → and-1 confirmado
                if nxt_team == team and (
                    act == "fthrow"
                    or "TIRO DE 1" in nxt_u
                    or "TIRO LIBRE" in nxt_u
                    or (self.is_fbcyl and ("Canasta de 1" in self._move_text(nxt) or "de 1" in self._move_text(nxt).lower()))
                ):
                    indices.add(i)
                    break
                # Cualquier otro evento de posesión rompe la búsqueda
                if (
                    act in ("shoot", "rebound", "lose", "recovery", "period")
                    or self._is_made_fg(nxt)[0]
                    or self._is_turnover(nxt)
                    or self._is_rebound(nxt)
                    or self._is_steal(nxt)
                ):
                    break
        return indices

    def _is_ft_event(self, move: Dict) -> bool:
        """True si el evento es un tiro libre (anotado o fallado)."""
        act = self._action_type(move)
        text_u = self._move_text_upper(move)
        if act == "fthrow":
            return True
        if "TIRO DE 1" in text_u or "TIRO LIBRE" in text_u:
            return True
        if self.is_fbcyl:
            t = self._move_text(move)
            if "Canasta de 1" in t or "Intento fallado de 1" in t or ("de 1" in t.lower() and ("fallado" in t.lower() or "Canasta" in t)):
                return True
        return False

    def _ft_sequence_info(self, idx: int, moves: List[Dict]) -> Tuple[bool, int]:
        """Para el TL en `idx`, devuelve (es_ultimo_de_secuencia, puntos_de_toda_la_secuencia).

        Recorre hacia atrás y adelante los TL consecutivos del mismo equipo
        (permitiendo subst/foul/timeout/assist en medio).
        """
        team = str(moves[idx].get("idTeam") or "")
        # Expandir hacia atrás
        start = idx
        for j in range(idx - 1, -1, -1):
            m = moves[j]
            act = self._action_type(m)
            if act in ("subst", "foul", "timeout", "assist"):
                continue
            if str(m.get("idTeam") or "") == team and self._is_ft_event(m):
                start = j
                continue
            break
        # Expandir hacia adelante
        end = idx
        for j in range(idx + 1, len(moves)):
            m = moves[j]
            act = self._action_type(m)
            if act in ("subst", "foul", "timeout", "assist"):
                continue
            if str(m.get("idTeam") or "") == team and self._is_ft_event(m):
                end = j
                continue
            break
        is_last = idx == end
        seq_pts = sum(self._points_from_move(moves[j]) for j in range(start, end + 1) if self._is_ft_event(moves[j]))
        return is_last, seq_pts

    # -- state machine ----------------------------------------------------

    def extract_possessions(self) -> List[Dict[str, Any]]:
        if not self.moves:
            return []

        moves = sorted(self.moves, key=lambda m: (self._get_timestamp(m), int(m.get("num") or 0)))
        orebs = self._detect_offensive_rebounds(moves)
        sfouls = self._detect_shooting_foul_indices(moves)
        and1s = self._detect_and1_indices(moves)

        possessions: List[Dict[str, Any]] = []
        current_team: Optional[str] = None
        start_time = 0
        start_idx = 0
        start_move: Optional[Dict] = None
        points = 0
        prev_ending: Optional[str] = None
        is_period_start = True

        def close_possession(end_ts: int, end_mv: Optional[Dict], ending_type: str) -> None:
            nonlocal current_team, start_time, start_idx, start_move, points, prev_ending, is_period_start
            if current_team is None:
                return
            duration = end_ts - start_time
            # Permitir duración 0 cuando hay puntos (secuencias de TL en el mismo segundo
            # del reloj). Descartar solo si no hay puntos o si es negativa / absurda.
            if duration < 0 or duration > 90:
                current_team = None
                points = 0
                return
            if duration == 0 and points == 0:
                current_team = None
                points = 0
                return
            # Normalizar duración mínima a 1s si hubo acción de tiro/canasta
            if duration == 0:
                duration = 1

            score = self._running_score(moves, start_idx)
            opp = self._opponent(current_team)
            diff = score.get(current_team, 0) - score.get(opp, 0)

            origin = self._classify_origin(prev_ending, start_move, is_period_start)
            finalizacion = ending_type
            if end_mv and finalizacion in ("", "otro"):
                finalizacion = self._classify_ending(end_mv, points)

            clock = self._format_game_clock(start_move) if start_move else ""
            quarter = self._get_quarter(start_move) if start_move else 1

            possessions.append({
                "ID_Partido": self.game_id,
                "Equipo": self._team_name(current_team),
                "Equipo_ID": current_team,
                "Rival": self._team_name(opp),
                "Rival_ID": opp,
                "Local_Visitante": self._home_away(current_team),
                "Cuarto": quarter,
                "Tiempo_de_juego": clock,
                "Timestamp_inicio": start_time,
                "Diferencia_marcador": diff,
                "Origen_posesion": origin,
                "Duracion_posesion": duration,
                "Tipo_finalizacion": finalizacion,
                "Puntos_obtenidos": points,
            })
            prev_ending = finalizacion
            is_period_start = False
            current_team = None
            points = 0

        for i, move in enumerate(moves):
            tid = str(move.get("idTeam") or "")
            ts = self._get_timestamp(move)
            act = self._action_type(move)

            # Eventos sin equipo (period, etc.)
            if act == "period" or not tid:
                if act == "period":
                    if current_team is not None:
                        close_possession(ts, move, "fin_periodo")
                    current_team = None
                    is_period_start = True
                continue

            # Cambio de cuarto
            period_change = False
            if self.is_fbcyl:
                if i > 0 and move.get("period") != moves[i - 1].get("period"):
                    period_change = True
            else:
                if i > 0 and str(move.get("quarter")) != str(moves[i - 1].get("quarter")):
                    period_change = True
            if period_change:
                if current_team is not None:
                    close_possession(ts, moves[i - 1], "fin_periodo")
                current_team = None
                is_period_start = True

            possession_change = False
            new_team: Optional[str] = None
            pts_scored = 0
            ending_type = "otro"

            # 1. Canasta de campo
            is_fg, fg_pts = self._is_made_fg(move)
            if is_fg:
                pts_scored = fg_pts
                if i in and1s:
                    # And-1: la posesión continúa con el/los TL; no cambiamos aún
                    ending_type = self._classify_ending(move, fg_pts)
                else:
                    possession_change = True
                    new_team = self._opponent(tid)
                    ending_type = self._classify_ending(move, fg_pts)

            # 2. Tiros libres (anotados o fallados) — tratar como secuencia
            elif self._is_ft_event(move):
                is_last, seq_pts = self._ft_sequence_info(i, moves)
                pts_scored = self._points_from_move(move)  # 0 o 1 de ESTE TL
                if is_last:
                    # Si el último TL está fallado y hay OReb → posesión continúa
                    if self._is_missed_ft(move) and i in orebs:
                        ending_type = "tiro_fallado"  # no cambiamos posesión
                    else:
                        possession_change = True
                        new_team = self._opponent(tid)
                        if seq_pts > 0:
                            ending_type = "tiros_libres"
                        else:
                            ending_type = "tiro_fallado"
                # si no es el último, solo acumulamos pts_scored y seguimos

            # 3. Pérdida
            if self._is_turnover(move):
                possession_change = True
                new_team = self._opponent(tid)
                ending_type = "perdida"

            # 4. Tiro de campo fallado (NO TL — los TL ya se manejaron arriba)
            is_miss = self._is_missed_fg(move)
            if is_miss:
                if i not in orebs and i not in sfouls:
                    possession_change = True
                    new_team = self._opponent(tid)
                    ending_type = "tiro_fallado"

            # 5. Rebote defensivo
            if self._is_rebound(move):
                for lb in range(1, min(3, i + 1)):
                    prev = moves[i - lb]
                    prev_team = str(prev.get("idTeam") or "")
                    if self._is_missed_fg(prev) or self._is_missed_ft(prev):
                        if prev_team != tid:
                            possession_change = True
                            new_team = tid
                            ending_type = "rebote_defensivo"
                        break
                    prev_u = self._move_text_upper(prev)
                    if ("ANOTADO" in prev_u and "FALLADO" not in prev_u) or "PÉRDIDA" in prev_u or "PERDIDA" in prev_u:
                        break
                    if self._is_rebound(prev) or self._is_steal(prev):
                        break

            # 6. Robo / recovery
            if self._is_steal(move):
                possession_change = True
                new_team = tid
                ending_type = "recuperacion"

            # Primer evento con equipo
            if i == 0 and current_team is None and tid:
                possession_change = True
                new_team = tid
                ending_type = "inicio"

            # Si el equipo del evento no coincide con current_team y hay puntos o
            # es un TL / canasta, transferir la posesión al equipo del evento.
            if tid and current_team != tid and (
                pts_scored > 0 or self._is_ft_event(move) or is_fg
            ):
                if current_team is not None:
                    close_possession(ts, move, "otro")
                current_team = tid
                start_time = ts
                start_idx = i
                start_move = move
                points = 0
                is_period_start = False

            # Acumular puntos de la posesión en curso
            if current_team == tid and pts_scored > 0:
                points += pts_scored

            if possession_change and new_team:
                if current_team is None or current_team != new_team:
                    if current_team is not None:
                        close_possession(ts, move, ending_type)
                    current_team = new_team
                    start_time = ts
                    start_idx = i
                    start_move = move
                    points = 0

        if current_team is not None and moves:
            close_possession(self._get_timestamp(moves[-1]), moves[-1], "fin_partido")

        return possessions


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "ID_Partido",
    "Equipo",
    "Rival",
    "Local_Visitante",
    "Cuarto",
    "Tiempo_de_juego",
    "Diferencia_marcador",
    "Origen_posesion",
    "Duracion_posesion",
    "Tipo_finalizacion",
    "Puntos_obtenidos",
]


def write_csv(rows: List[Dict[str, Any]], output_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})


def process_game(game: Dict, fbcyl: bool, team_id: Optional[str] = None) -> List[Dict]:
    gid = game_id_from_doc(game)
    analyzer = DetailedPossessionAnalyzer(game, fbcyl, gid)
    poss = analyzer.extract_possessions()
    if team_id:
        tid = str(team_id)
        poss = [p for p in poss if str(p.get("Equipo_ID")) == tid]
    return poss


def export_from_json(path: str, output_path: str, team_id: Optional[str] = None, verbose: bool = False) -> int:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_mongo_extjson(raw)
    # Detectar formato
    fbcyl = "moves" in data and isinstance(data.get("moves"), list)
    rows = process_game(data, fbcyl, team_id)
    if verbose:
        print(f"  {game_id_from_doc(data)}: {len(rows)} posesiones ({'FBCYL' if fbcyl else 'FEB'})")
    write_csv(rows, output_path)
    return len(rows)


def export_from_mongo(
    uri: str,
    db_name: str,
    collection_name: str,
    output_path: str,
    team_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: Optional[int] = None,
    verbose: bool = False,
) -> int:
    if not HAS_PYMONGO:
        print("Se requiere pymongo: pip install pymongo", file=sys.stderr)
        sys.exit(1)

    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"No se pudo conectar a MongoDB ({uri}): {exc}", file=sys.stderr)
        sys.exit(1)

    fbcyl = is_fbcyl(collection_name)
    if verbose:
        print(f"Formato: {'FBCYL' if fbcyl else 'FEB'} | DB={db_name} | col={collection_name}")

    try:
        games = fetch_games(client, db_name, collection_name, team_id, date_from, date_to, limit)
    except PyMongoError as exc:
        print(f"Error MongoDB: {exc}", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"Partidos: {len(games)}")

    all_rows: List[Dict[str, Any]] = []
    for game in games:
        gid = game_id_from_doc(game)
        try:
            rows = process_game(game, fbcyl, team_id)
            all_rows.extend(rows)
            if verbose:
                print(f"  {gid}: {len(rows)} posesiones")
        except Exception as exc:
            print(f"  ERROR {gid}: {exc}", file=sys.stderr)
            if verbose:
                import traceback
                traceback.print_exc()

    write_csv(all_rows, output_path)
    client.close()
    return len(all_rows)


def parse_date(s: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"Fecha no reconocida: {s}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta posesiones a CSV desde MongoDB o JSON local.")
    parser.add_argument("coleccion", nargs="?", default=None, help="Nombre de la colección MongoDB.")
    parser.add_argument("--json", dest="json_path", default=None, help="Fichero JSON local de un partido (modo prueba).")
    parser.add_argument("-o", "--output", default="posesiones.csv", help="CSV de salida.")
    parser.add_argument("--mongo-uri", default=_DEFAULT_URI)
    parser.add_argument("--db", default=(
        urllib.parse.urlparse(_DEFAULT_URI).path.lstrip("/") or os.environ.get("MONGO_DB", "basketball")
    ))
    parser.add_argument("--team-id", default=None)
    parser.add_argument("--from", dest="date_from", type=parse_date, default=None)
    parser.add_argument("--to", dest="date_to", type=parse_date, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.json_path:
        n = export_from_json(args.json_path, args.output, args.team_id, args.verbose)
    elif args.coleccion:
        n = export_from_mongo(
            args.mongo_uri, args.db, args.coleccion, args.output,
            args.team_id, args.date_from, args.date_to, args.limit, args.verbose,
        )
    else:
        parser.error("Indica una colección MongoDB o --json fichero.json")
        return

    print(f"Exportadas {n} posesiones → {args.output}")


if __name__ == "__main__":
    main()
