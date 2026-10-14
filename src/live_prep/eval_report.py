"""The rule evaluator's report: machine-readable data and Spanish tables (Markdown) for the staff and the docs."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .eval_coach import summarize_coach
from .eval_metrics import rule_metrics


def _num(value: Optional[float], digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}".replace(".", ",")


def _pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:.0%}"


def _mmss(seconds: Optional[float]) -> str:
    return "—" if seconds is None else f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> List[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    return out + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _severity(sev: Dict[str, int]) -> str:
    return f"{sev['critical']}/{sev['warning']}/{sev['info']}"


def _rule_rows(metrics: Dict[str, Dict[str, Any]]) -> List[List[Any]]:
    rows = []
    for rule, m in sorted(((r, m) for r, m in metrics.items() if r != "all"), key=lambda kv: -kv[1]["alerts"]):
        a = m["actions"]
        rows.append([f"`{rule}`", m["alerts"], _num(m["per_team_game"]), _num(m["per_10min"], 2),
                     _severity(m["severity"]), m["duplicates"],
                     *([a["seguida"], a["anticipada"], a["tarde"], a["no"]] if a else ["—"] * 4),
                     _pct((m["followed"] or {}).get("120")), _pct(m["coverage"]), _num(m["net_delta"])])
    t = metrics["all"]
    rows.append(["**Total**", t["alerts"], _num(t["per_team_game"]), _num(t["per_10min"], 2),
                 _severity(t["severity"]), t["duplicates"], "", "", "", "", "", "", ""])
    return rows


_RULE_HEADERS = ["Regla", "Alertas", "Por equipo-partido", "Por 10 min", "Crít./Aviso/Info", "Duplicados",
                 "Seguida", "Anticipada", "Tarde", "No", "Seguida ≤ 120 s", "Cobertura de tiempos muertos", "Δ neto 5 min"]


def _baseline_section(name: str, metrics: Dict[str, Dict[str, Any]]) -> List[str]:
    out = [f"## Configuración «{name}» (línea base)", ""]
    if metrics["all"]["alerts"] == 0:
        return out + ["Sin alertas en esta configuración.", ""]
    out += _table(_RULE_HEADERS, _rule_rows(metrics)) + [""]
    measured = [(r, m["measure"]) for r, m in metrics.items() if r != "all" and m.get("measure")]
    if measured:
        out += ["### Lo que cada regla quería mover (5 min antes → 5 min después)", ""]
        out += _table(["Regla", "Medida", "Antes", "Después", "n"],
                      [[f"`{r}`", f"`{m['name']}`", _num(m["before"], 2), _num(m["after"], 2), m["n"]] for r, m in measured]) + [""]
    judged = [(r, m["verdicts"]) for r, m in metrics.items() if r != "all" and m.get("verdicts")]
    if judged:
        out += ["### Respuesta del staff (feedback de la app)", ""]
        out += _table(["Regla", "Seguida", "Descartada", "Ya hecho", "Sin respuesta", "Obediencia"],
                      [[f"`{r}`", v["seguida"], v["descartada"], v["ya_hecho"], v["sin_respuesta"], _pct(v["obediencia"])]
                       for r, v in judged]) + [""]
    return out


def _comparison_sections(names: Sequence[str], metrics: Dict[str, Dict[str, Dict[str, Any]]]) -> List[str]:
    if len(names) < 2:
        return []
    base = metrics[names[0]]
    out = ["## Comparación con la línea base", ""]
    for name in names[1:]:
        other = metrics[name]
        rows = []
        for r in sorted((set(base) | set(other)) - {"all"}) + ["all"]:
            b, o = base.get(r, {}), other.get(r, {})
            rows.append([f"`{r}`" if r != "all" else "**Total**", b.get("alerts", 0), o.get("alerts", 0),
                         f"{o.get('alerts', 0) - b.get('alerts', 0):+d}", b.get("duplicates", 0), o.get("duplicates", 0),
                         _pct((b.get("followed") or {}).get("120")), _pct((o.get("followed") or {}).get("120"))])
        out += [f"### «{name}» frente a «{names[0]}»", ""]
        out += _table(["Regla", "Alertas base", "Alertas", "Δ", "Duplicados base", "Duplicados",
                       "Seguida ≤ 120 s base", "Seguida ≤ 120 s"], rows) + [""]
    return out


def formation_summary(ev: Any) -> Optional[Dict[str, Dict[str, Any]]]:
    """Per configuration: the minimum of "formación" players on court, the illegal-lineup alerts and the sides that had one (None
    without a roster: the rule is then off in the evaluator's packages)."""
    if not ev.params.get("roster"):
        return None
    minimum = ev.params.get("formation_min") or {}
    out = {}
    for name in ev.configs:
        rows = [r for r in ev.rows if r["config"] == name and r["id"] == "formation_lineup"]
        out[name] = {"min_on_court": minimum.get(name), "alerts": len(rows), "sides": len({(r["game"], r["team"]) for r in rows})}
    return out


def _formation_section(ev: Any, summary: Optional[Dict[str, Dict[str, Any]]]) -> List[str]:
    out = ["## Alineación indebida (#272)", ""]
    if summary is None:
        return out + ["Sin plantilla: la regla no actúa en estos paquetes y no se miden sus falsos positivos. "
                      "Use `--roster` (pide a FEB la plantilla de cada equipo una vez) o `--roster-file`.", ""]
    roster = ev.params["roster"]
    out += [f"La plantilla es la **plantilla actual** de FEB ({roster['players']} jugadoras de {roster['teams']} equipos): una "
            "aproximación válida para la temporada en curso. En una competición sin esta regla el mínimo es 0.", ""]
    out += _table(["Configuración", "Mínimo en pista", "Alertas", "Equipo-partidos con alerta"],
                  [[f"«{n}»", s["min_on_court"], s["alerts"], s["sides"]] for n, s in summary.items()])
    return out + [""]


def _coach_section(c: Dict[str, Any]) -> List[str]:
    t, s, d = c["timeouts"], c["stints"], c["droughts"]
    out = ["## Comportamiento de los entrenadores", "",
           f"- **Tiempos muertos**: {t['total']} ({_num(t['per_team_game'], 2)} por equipo y partido). "
           f"Tras 8 puntos rivales sin respuesta en 2:30: {_pct(t['after_rival_unanswered_8'])}; tras +6 neto: "
           f"{_pct(t['after_rival_net_run_6'])}; tras 4 pérdidas en 5 min: {_pct(t['after_four_turnovers'])}.",
           f"- **Relevos voluntarios**: {s['n']}; mediana {_mmss(s['median_s'])}, p75 {_mmss(s['p75_s'])}, "
           f"p90 {_mmss(s['p90_s'])}; más de 7:00 en pista: {_pct(s['share_over_420'])}.",
           f"- **Sequías de 4:00 o más**: {d['n']} ({_num(d['per_team_game'], 2)} por equipo y partido); "
           f"con tiempo muerto durante la sequía: {_pct(d['with_timeout'])}.", ""]
    if c["fouls"]:
        groups = ["H1", "Q3", "Q4", "OT"]
        rows = [[f"{pf}.ª falta", *[(f"{_pct(g[x]['subbed_120'])} (n={g[x]['n']})" if x in g else "—") for x in groups]]
                for pf, g in c["fouls"].items()]
        out += ["Retirado en ≤ 2 min tras la falta:", ""] + _table(["Falta", "1.º-2.º cuarto", "3.º", "4.º", "Prórroga"], rows) + [""]
    return out


def _simulation_section(simulation: Sequence[Dict[str, Any]]) -> List[str]:
    if not simulation:
        return []
    out = ["## Simulación del parcial rival (umbrales)", ""]
    out += _table(["Condición", "Avisos por equipo y partido", "Seguidos de tiempo muerto ≤ 2 min", "Tiempos muertos cubiertos"],
                  [[r["spec"], _num(r["per_team_game"]), _pct(r["followed"]), _pct(r["covered"])] for r in simulation])
    return out + [""]


def build_report(ev: Any) -> Tuple[Dict[str, Any], str]:
    """``(data, markdown)`` of an ``Evaluation``: metrics per configuration, coach behaviour and the run simulation."""
    follow = ev.params.get("follow_s", 120)
    by_config = {name: [r for r in ev.rows if r["config"] == name] for name in ev.configs}
    metrics = {name: rule_metrics(rows, ev.team_games, follow_s=follow) for name, rows in by_config.items()}
    coach = summarize_coach(ev.coach, team_games=2 * len(ev.coach))
    formation = formation_summary(ev)
    data = {"params": ev.params, "configs": ev.configs, "timing": dict(Counter(g["timing"] for g in ev.team_games)),
            "metrics": metrics, "coach": coach, "simulation": ev.simulation, "formation": formation}
    p = ev.params
    lines = ["# Evaluación de reglas del motor live", "",
             f"{_plural(p.get('games', 0), 'partido', 'partidos')} · "
             f"{_plural(len(ev.team_games), 'equipo-partido', 'equipo-partidos')} evaluados · "
             f"latencia {_num(p.get('latency_s', 40), 0)} s · sondeo {_num(p.get('poll_s', 10), 0)} s · "
             f"«seguida» = en ≤ {follow} s tras mostrarse la alerta · mínimo de partidos previos {p.get('min_prior_games', 0)}",
             "", "Temporización: " + (", ".join(f"{k}: {v}" for k, v in sorted(data["timing"].items())) or "—"), ""]
    if ev.configs:
        lines += _baseline_section(ev.configs[0], metrics[ev.configs[0]])
        lines += _comparison_sections(ev.configs, metrics)
    lines += _formation_section(ev, formation) + _coach_section(coach) + _simulation_section(ev.simulation)
    return data, "\n".join(lines).rstrip() + "\n"
