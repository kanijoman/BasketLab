"""Sanctions and fouls in the finish (issue #245): F1, F4 and V2.

* F1 ``disqualification``: a player with one unsportsmanlike or one technical foul is one sanction away from being disqualified
  (FIBA: two unsportsmanlike, two technical, or one of each). For an own player it is a warning (defend without risk); for a
  rival it is information (he can be provoked). The counters come from ``state`` (``unsportsmanlike`` and ``technical`` of each
  player). A coach's technical foul is not identified by the feed text, so it is not counted (see docs/LIVE.md).
* F4 ``key_fouls_close``: a key own player (``rest_important_avg_min_s`` of average minutes) with four fouls in a close finish:
  defend without risk. The closing phase raises it one level (``game_context``).
* V2 ``rival_foul_pair``: two rival players with ``rival_pair_pf`` or more fouls on court: attack them.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .game_context import game_phase
from .proposals import tactic_proposal
from .rules_fouls import CRITICAL_PF, game_end_quiet


def _name(p: Dict[str, Any]) -> str:
    return p["name"].strip()


def disqualification_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    out = []
    for pid, p in snap["players"].items():
        unsports, technical = p.get("unsportsmanlike", 0), p.get("technical", 0)
        if unsports + technical != 1 or p["team_id"] not in (ctx.own_team_id, ctx.rival_team_id):
            continue
        own = p["team_id"] == ctx.own_team_id
        kind = "antideportiva" if unsports else "técnica"
        evidence = {"player_id": pid, "team_id": p["team_id"], "unsportsmanlike": unsports, "technical": technical}
        if own:
            message = f"{_name(p)}: tiene una falta {kind}: otra más y queda descalificada. Defender sin riesgo."
            proposal = [tactic_proposal(f"Evitar la falta de {_name(p)}: defender sin riesgo", pid, _name(p))]
        else:
            message = f"Rival {_name(p)} tiene una falta {kind}: otra más y queda descalificada. Atacarle."
            proposal = [tactic_proposal(f"Atacar a {_name(p)}: una sanción más y se va", pid, _name(p))]
        out.append(Advice(
            key=f"sanction:{pid}:{unsports}{technical}", id="disqualification_risk", severity="warning" if own else "info",
            category="faltas", message=message, evidence=evidence, proposal=proposal))
    return out


def key_fouls_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg = ctx.config
    if not cfg.enabled("game_context") or game_phase(snap, ctx.own_team_id, ctx.rival_team_id, cfg)["phase"] != "close_late":
        return []
    out = []
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.own_team_id or not p["on_court"] or p["pf"] != CRITICAL_PF:
            continue
        if ((ctx.baselines.get(pid) or {}).get("avg_min") or 0) < cfg.rest_important_avg_min_s:
            continue
        out.append(Advice(
            key=f"key_fouls:{pid}", id="key_fouls_close", severity="warning", category="faltas",
            message=f"{_name(p)} (clave) con 4 faltas en el cierre igualado: defensa sin riesgo, evitar la falta.",
            evidence={"player_id": pid, "team_id": p["team_id"], "pf": p["pf"]},
            proposal=[tactic_proposal(f"Defender sin riesgo con {_name(p)}: sin faltas innecesarias", pid, _name(p))]))
    return out


def rival_pair_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if not ctx.rival_team_id or game_end_quiet(snap, ctx.config.foul_quiet_last_s):
        return []        # #403: no foul alert with this little game left
    pair = sorted((pid, p) for pid, p in snap["players"].items()
                  if p["team_id"] == ctx.rival_team_id and p["on_court"] and p["pf"] >= ctx.config.rival_pair_pf)
    if len(pair) < 2:
        return []
    names = ", ".join(_name(p) for _, p in pair)
    return [Advice(
        key="rival_pair:" + ":".join(pid for pid, _ in pair), id="rival_foul_pair", severity="warning", category="faltas",
        message=f"Dos rivales con {ctx.config.rival_pair_pf} o más faltas en pista ({names}): atacarles.",
        evidence={"player_ids": [pid for pid, _ in pair], "team_id": ctx.rival_team_id},
        proposal=[tactic_proposal(f"Atacar a {names}, que acumulan faltas")])]
