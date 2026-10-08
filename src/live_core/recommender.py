"""Substitution recommender (own team), deterministic and O(bench x court).

The feed has no positions, so replacements are chosen by ROLE similarity inferred from
season z-profiles (see ``profiles``). A candidate must be available (not fouled out, not in
foul trouble, not overloaded with minutes), close enough in role, and must not unbalance
the resulting quintet (rebounding, creation, spacing, interior). When there is a lever
(the Four Factors weak spot) the candidate that improves it most is preferred.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import RuleConfig
from .profiles import role_distance
from .rules_fouls import FOUL_OUT, evaluate_player_fouls
from .rules_rotation import fatigue_index

# lever -> (profile metric, +1 if higher is better else -1, Spanish label)
LEVER_METRIC = {
    "tov": ("tov40", -1.0, "las pérdidas"),
    "orb": ("orb40", 1.0, "el rebote ofensivo"),
    "efg": ("efg", 1.0, "el acierto de tiro"),
    "ftr": ("ftr", 1.0, "los tiros libres"),
}

_CLAIM_GAIN = 0.2  # below this the lever gain is noise: do not mention it

# Quintet balance dimensions: name -> profile metrics whose z-scores are added over the five.
BALANCE_DIMS = {
    "rebote": ("orb40", "drb40"),
    "creación": ("ast40",),
    "espaciado": ("fg3a40",),
    "juego interior": ("fg2a40", "blk40"),
}


class Recommender:
    def __init__(self, own_team_id: str, players_table: Dict[str, Dict[str, Any]],
                 config: Optional[RuleConfig] = None) -> None:
        self._own = own_team_id
        self._table = players_table or {}
        self._cfg = config or RuleConfig()
        # Load for bench players ignores the stint: they are resting, only minutes count.
        self._bench_cfg = RuleConfig(**{**self._cfg.__dict__, "fatigue_weight_stint": 0.0})

    # -- helpers ----------------------------------------------------------------------

    def _z(self, pid: str) -> Optional[Dict[str, float]]:
        entry = self._table.get(pid)
        return entry.get("z") if entry else None

    def _available(self, snap: Dict[str, Any], pid: str, player: Dict[str, Any]) -> bool:
        if player["pf"] >= FOUL_OUT:
            return False
        if evaluate_player_fouls(pid, player["name"], player["pf"], snap["period"]) is not None:
            return False  # already in foul trouble
        load, _ = fatigue_index(0, player["minutes"], snap["elapsed"], self._table[pid], self._bench_cfg)
        return load < self._cfg.fatigue_alert_index

    def _quintet_balance(self, snap: Dict[str, Any], swap_out: str, swap_in: str) -> Dict[str, float]:
        """Change in each balance dimension if ``swap_in`` replaces ``swap_out`` on court."""
        on_court = [pid for pid, p in snap["players"].items() if p["on_court"] and p["team_id"] == self._own]
        after = [swap_in if pid == swap_out else pid for pid in on_court]

        def total(ids: List[str], metrics) -> float:
            return sum(self._z(pid)[m] for pid in ids if self._z(pid) for m in metrics)

        return {name: round(total(after, m) - total(on_court, m), 3) for name, m in BALANCE_DIMS.items()}

    # -- public -----------------------------------------------------------------------

    def suggest_swaps(self, snap: Dict[str, Any], out_pid: str, lever: Optional[str] = None,
                      max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Who should replace ``out_pid`` (an own player on court), best first."""
        players, z_out = snap["players"], self._z(out_pid)
        outgoing = players.get(out_pid)
        if not z_out or not outgoing or not outgoing["on_court"] or outgoing["team_id"] != self._own:
            return []

        out: List[Dict[str, Any]] = []
        for pid, p in players.items():
            z_in = self._z(pid)
            if (pid == out_pid or p["team_id"] != self._own or p["on_court"] or not z_in
                    or not self._available(snap, pid, p)):
                continue
            distance = role_distance(z_out, z_in)
            if distance > self._cfg.rec_max_role_distance:
                continue
            out.append(self._candidate(snap, out_pid, outgoing, pid, p, z_out, z_in, distance, lever))

        out.sort(key=lambda c: (not c["balance_ok"], -c["score"], c["in_id"]))
        return out[: max_results or self._cfg.rec_max_results]

    def suggest_for_lever(self, snap: Dict[str, Any], lever: str,
                          max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Best (out, in) pairs to improve ``lever``: balanced, positive gain, one per incoming player."""
        best: Dict[str, Dict[str, Any]] = {}
        for pid, p in snap["players"].items():
            if p["on_court"] and p["team_id"] == self._own:
                for cand in self.suggest_swaps(snap, pid, lever=lever, max_results=len(snap["players"])):
                    if cand["balance_ok"] and cand["lever_gain"] >= self._cfg.rec_min_lever_gain:
                        if cand["in_id"] not in best or cand["score"] > best[cand["in_id"]]["score"]:
                            best[cand["in_id"]] = cand
        ranked = sorted(best.values(), key=lambda c: (-c["score"], c["in_id"]))
        return ranked[: max_results or self._cfg.rec_max_results]

    # -- building one recommendation --------------------------------------------------

    def _candidate(self, snap, out_pid, outgoing, in_pid, incoming, z_out, z_in, distance, lever):
        gain, label = None, None
        if lever in LEVER_METRIC:
            metric, sign, label = LEVER_METRIC[lever]
            gain = sign * (z_in[metric] - z_out[metric])
            base = gain
        else:  # no lever: prefer efficient, careful players among the role-similar ones
            base = 0.5 * z_in["efg"] - 0.5 * z_in["tov40"]
        balance = self._quintet_balance(snap, out_pid, in_pid)
        weak = [name for name, delta in balance.items() if delta < -self._cfg.rec_balance_tolerance]

        in_name, out_name = incoming["name"].strip(), outgoing["name"].strip()
        message = f"Entra {in_name} por {out_name}"
        if gain is not None and gain >= _CLAIM_GAIN:
            message += f" y mejora {label} ({gain:+.1f} σ)"
        elif gain is not None and gain <= -_CLAIM_GAIN:
            message += f" (cede algo en {label}: {gain:+.1f} σ)"
        message += f". Rol similar (distancia {distance:.1f})"
        if weak:
            message += f". Ojo: descompensa el quinteto ({', '.join(weak)})"
        return {
            "type": "sub", "out_id": out_pid, "out_name": out_name,
            "in_id": in_pid, "in_name": in_name,
            "score": round(base - self._cfg.rec_distance_weight * distance, 3),
            "role_distance": round(distance, 3),
            "lever": lever if gain is not None else None,
            "lever_gain": round(gain, 3) if gain is not None else 0.0,
            "balance_ok": not weak, "balance_delta": balance, "message": message,
        }
