"""Shot-zone rules for our own team and the rival's defence (issue #247), on the zone families of ``rules_rival``.

* Z1 ``own_zone_hot`` and Z2 ``own_zone_cold`` / ``own_zone_selection`` (rule ``own_zones``): a zone where we score well above or well
  below what is expected (our season in the package shrunk to the league, ``rules_rival._expected``), or too many mid-range shots.
* Z3 ``rival_concedes_zone`` (``rival_defence_zones``): a zone the rival concedes in the season (``tables.zones.rival_conceded``, at
  least ``zone_concede_excess`` points per shot above the league, with enough season shots) and where we already score live.
* Z4 ``rival_player_zone`` (``rival_zone_player``): a rival player hot from one zone (shots per player: the SHOTCHART jersey numbers
  mapped by the box score, ``snapshot["zone_players"]``).
* Z5 ``paint_battle``: ``paint_diff`` points or more of difference in the paint (restricted area and the key).

Each is said once per family (and player / period). Thresholds are provisional, in ``RuleConfig``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .proposals import tactic_proposal
from .rules_rival import _MIN_REFERENCE_SHOTS, _ZONE_TEXT, _expected
from .zones import default_family_pps, family_totals, zone_family

PAINT_ZONES = ("restricted_area", "key_area")
SELECTION_FAMILY = "media distancia"


def _pps(cell: Dict[str, int]) -> float:
    return cell["pts"] / cell["a"] if cell["a"] else 0.0


def own_zone_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    live = family_totals((snap.get("zones") or {}).get(ctx.own_team_id) or {})
    total = sum(f["a"] for f in live.values())
    if not total:
        return []
    cfg, league = ctx.config, family_totals(ctx.zone_ref.get("league", {}))
    own = family_totals(ctx.zone_ref.get("own", {}))
    out: List[Advice] = []
    for family, cell in sorted(live.items()):
        attempts, makes, pps = cell["a"], cell["m"], _pps(cell)
        expected_pps, expected_share = _expected(family, ctx, league, own)
        label = _ZONE_TEXT[family][0]
        base = {"family": family, "attempts": attempts, "makes": makes, "pps": round(pps, 3), "expected_pps": round(expected_pps, 3)}
        if attempts >= cfg.zone_min_attempts and makes >= cfg.zone_min_makes and pps - expected_pps >= cfg.zone_pps_excess:
            out.append(Advice(
                key=f"zone_own:{family}:hot", id="own_zone_hot", severity="info", category="four_factors",
                message=f"Desde {label} anotamos {makes}/{attempts} ({pps:.2f} puntos por tiro; lo habitual {expected_pps:.2f}).",
                evidence=base, proposal=[tactic_proposal(f"Insistir por {label}")]))
        elif attempts >= cfg.zone_min_attempts and expected_pps - pps >= cfg.zone_pps_excess:
            out.append(Advice(
                key=f"zone_own:{family}:cold", id="own_zone_cold", severity="info", category="four_factors",
                message=f"Desde {label} solo {makes}/{attempts} ({pps:.2f} puntos por tiro; lo habitual {expected_pps:.2f}).",
                evidence=base, proposal=[tactic_proposal(f"Cambiar la selección de tiro: menos tiros desde {label}")]))
        share = attempts / total
        if (family == SELECTION_FAMILY and attempts >= cfg.zone_min_share_attempts and share >= cfg.zone_share
                and share - expected_share >= cfg.zone_share_excess):
            out.append(Advice(
                key=f"zone_own:{family}:selection", id="own_zone_selection", severity="info", category="four_factors",
                message=(f"Mala selección: {attempts} de {total} tiros ({share:.0%}) desde {label} (habitual {expected_share:.0%}). "
                         "Buscar tiros más cerca del aro o desde el triple."),
                evidence={**base, "total": total, "share": round(share, 3), "expected_share": round(expected_share, 3)},
                proposal=[tactic_proposal("Buscar tiros cerca del aro o desde el triple")]))
    return out


def rival_defence_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    conceded = family_totals(ctx.zone_ref.get("rival_conceded", {}))
    if not ctx.rival_team_id or not conceded:
        return []
    cfg, league = ctx.config, family_totals(ctx.zone_ref.get("league", {}))
    live = family_totals((snap.get("zones") or {}).get(ctx.own_team_id) or {})
    out: List[Advice] = []
    for family, season in sorted(conceded.items()):
        reference = league.get(family)
        league_pps = (_pps(reference) if reference and reference["a"] >= _MIN_REFERENCE_SHOTS else default_family_pps(family))
        if season["a"] < _MIN_REFERENCE_SHOTS:
            continue
        shrunk = (season["pts"] + cfg.zone_shrink_n0 * league_pps) / (season["a"] + cfg.zone_shrink_n0)
        mine = live.get(family)
        if shrunk - league_pps < cfg.zone_concede_excess or not mine or mine["a"] < cfg.zone_confirm_attempts or _pps(mine) < league_pps:
            continue
        label = _ZONE_TEXT[family][0]
        out.append(Advice(
            key=f"zone_concede:{family}", id="rival_concedes_zone", severity="info", category="rival",
            message=(f"El rival concede desde {label} ({shrunk:.2f} pts/tiro en la temporada frente a {league_pps:.2f} de la liga) y "
                     f"aquí ya llevamos {mine['m']}/{mine['a']}."),
            evidence={"family": family, "conceded_pps": round(shrunk, 3), "league_pps": round(league_pps, 3),
                      "attempts": mine["a"], "makes": mine["m"]},
            proposal=[tactic_proposal(f"Atacar desde {label}: el rival lo concede")]))
    return out


def rival_player_zone_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if not ctx.rival_team_id:
        return []
    cfg, out = ctx.config, []
    for pid, zones in sorted(((snap.get("zone_players") or {}).get(ctx.rival_team_id) or {}).items()):
        player = snap["players"].get(pid)
        if not player:
            continue
        for family, cell in sorted(family_totals(zones).items()):
            if cell["a"] < cfg.zone_player_min_attempts or cell["m"] < cfg.zone_player_min_makes or _pps(cell) < cfg.zone_player_pps:
                continue
            name, label = player["name"].strip(), _ZONE_TEXT[family][0]
            out.append(Advice(
                key=f"zone_player:{pid}:{family}", id="rival_player_zone", severity="warning", category="rival",
                message=f"Rival {name}: {cell['m']}/{cell['a']} desde {label}.",
                evidence={"player_id": pid, "team_id": ctx.rival_team_id, "family": family, "attempts": cell["a"], "makes": cell["m"]},
                proposal=[tactic_proposal(f"Negarle {label} a {name}: ayudas y no dejarle recibir ahí", pid, name)]))
    return out


def paint_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    zones, rival = snap.get("zones") or {}, ctx.rival_team_id
    if not rival:
        return []
    own = sum((zones.get(ctx.own_team_id) or {}).get(z, {}).get("pts", 0) for z in PAINT_ZONES)
    theirs = sum((zones.get(rival) or {}).get(z, {}).get("pts", 0) for z in PAINT_ZONES)
    diff = own - theirs
    if abs(diff) < ctx.config.paint_diff:
        return []
    behind = diff < 0
    return [Advice(
        key=f"paint:{'behind' if behind else 'ahead'}:{snap['period']}", id="paint_battle", severity="warning" if behind else "info",
        category="four_factors",
        message=f"Pintura: {own}-{theirs} ({diff:+d}).",
        evidence={"own": own, "rival": theirs, "diff": diff},
        proposal=[tactic_proposal("Cerrar la zona: ayudas y rebote" if behind else "Seguir atacando dentro")])]
