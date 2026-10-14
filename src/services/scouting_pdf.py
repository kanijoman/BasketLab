"""The rival scouting report as a PDF (issue #299): ``render_scouting_pdf(report)``.

The report is the dict of ``live_prep.scouting_report.build_scouting_report``; this module only lays it out: summary, tactical
keys, game plan, players, quintets, zones (chart and table), quarters, the engine's alerts, the matchup with our team and the
games behind it. Sections without data are left out, a small sample is said on the first page.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.live_prep.scouting_report import fmt

from .scouting_pdf_parts import GREEN, MUTED, RED, ScoutingPDF, zones_chart

AREA_TAG = {"ataque": "[Ataque]", "defensa": "[Defensa]", "jugadoras": "[Jugadoras]", "ritmo": "[Ritmo]", "cierres": "[Cierres]", "gestión": "[Gestión]"}
COMPARISON_ROWS = 14


def _pct(value: Optional[float], sign: bool = False) -> str:
    return "-" if value is None else fmt(value, 0, sign) + " %"


def _summary(pdf: ScoutingPDF, report: Dict[str, Any]) -> None:
    rec, team = report["record"], report["team"]["name"]
    pdf.h1(team)
    pdf.para(f"{report['sample_games']} partidos analizados con el motor del directo | Balance {rec['wins']}-{rec['losses']} | "
             f"{fmt(rec['avg_for'])} a favor, {fmt(rec['avg_against'])} en contra ({fmt(rec['avg_margin'], 1, True)} de media)", 9, color=MUTED)
    for notice in report["notices"]:
        pdf.ln(1)
        pdf.para(notice, 9, bold=True, color=RED)
    if report["profile"]:
        pdf.h2("Perfil")
        for line in report["profile"]:
            pdf.bullet(line)


def _keys_and_plan(pdf: ScoutingPDF, report: Dict[str, Any]) -> None:
    if report["keys"]:
        pdf.h2("Claves tácticas")
        for key in report["keys"]:
            pdf.bullet(key["text"], AREA_TAG.get(key["area"], f"[{key['area']}]"))
    plan = report["plan"]
    if plan["neutralize"] or plan["exploit"]:
        pdf.h2("Plan de partido")
        for title, items in (("Peligros a neutralizar", plan["neutralize"]), ("Debilidades a explotar", plan["exploit"])):
            if items:
                pdf.para(title, 10, bold=True, color=GREEN if title.startswith("Deb") else RED)
                for item in items:
                    pdf.bullet(item["text"])


def _people(pdf: ScoutingPDF, report: Dict[str, Any]) -> None:
    if report["players"]:
        pdf.h2("Jugadoras clave")
        rows = [[p["name"], p["games"], fmt(p["minutes"] / p["games"]), fmt(p["pts_per_game"]), f"{p['share'] * 100:.0f} %",
                 p["clutch"]["pts"], p["clutch"]["fga"]] for p in report["players"]]
        pdf.table(["Jugadora", "PJ", "Min/p", "Pts/p", "% puntos", "Pts cierre", "TC cierre"], rows, [62, 14, 20, 20, 24, 24, 22])
    if report["lineups"]:
        pdf.h2("Quintetos más usados")
        for line in report["lineups"][:5]:
            pdf.bullet(line["text"])


def _zones(pdf: ScoutingPDF, report: Dict[str, Any]) -> None:
    if not report["zones"]:
        return
    chart = zones_chart(report["zones"], report["team"]["name"])
    pdf.h2("Zonas de tiro", keep_with=120 if chart else 35)     # the heading travels with the chart
    if chart:
        pdf.image_bytes(chart, 175)
    rows = [[z["label"], z["own_fga"], _pct(z["own_fg_pct"]), _pct(z["league_fg_pct"]), _pct(z["own_delta_pp"], True),
             z["conceded_fga"], _pct(z["conceded_fg_pct"]), _pct(z["conceded_delta_pp"], True)] for z in report["zones"]]
    pdf.table(["Zona", "Tiros", "% propio", "% liga", "Dif.", "Concede", "% concede", "Dif."], rows, [38, 16, 22, 20, 18, 20, 24, 18],
              colors=_row_colors(report["zones"]))


def _delta_color(delta: Optional[float], good_high: bool) -> Optional[tuple]:
    if delta is None or abs(delta) < 4:
        return None
    return GREEN if (delta > 0) == good_high else RED


def _row_colors(zones: List[Dict[str, Any]]) -> List[List[Optional[tuple]]]:
    return [[None, None, None, None, _delta_color(z["own_delta_pp"], True), None, None, _delta_color(z["conceded_delta_pp"], False)] for z in zones]


def _patterns(pdf: ScoutingPDF, report: Dict[str, Any]) -> None:
    quarters, edges, timeouts = report["quarters"], report["edges"], report["timeouts"]
    if quarters:
        pdf.h2("Cuartos")
        rows = [[f"Cuarto {p}", fmt(q["for"]), fmt(q["against"]), fmt(q["margin"], 1, True),
                 fmt(edges.get("start", {}).get(p, 0.0), 1, True), fmt(edges.get("close", {}).get(p, 0.0), 1, True)]
                for p, q in sorted(quarters.items())]
        pdf.table(["", "A favor", "En contra", "Margen", "Inicio (3')", "Cierre (3')"], rows, [34, 28, 28, 28, 32, 32])
    if timeouts and timeouts.get("per_game"):
        pdf.ln(2)
        pdf.para(f"Tiempos muertos: {fmt(timeouts['per_game'])} por partido ({fmt(timeouts['first_half'])} en la 1.a parte, {fmt(timeouts['second_half'])} en la 2.a). "
                 f"En los 2 minutos siguientes anotan {fmt(timeouts['after_for'])} y reciben {fmt(timeouts['after_against'])} de media.", 9)


def _alerts_and_matchup(pdf: ScoutingPDF, report: Dict[str, Any], own_name: str) -> None:
    if report["alerts"]:
        pdf.h2("Alertas del motor sobre este equipo")
        pdf.para("Lo que el motor del directo avisaría en sus partidos (por partido y minuto medio).", 8, color=MUTED)
        for alert in report["alerts"]:
            pdf.bullet(alert["text"], size=9)
    if report["comparison"]:
        pdf.h2(f"Comparativa: {own_name} frente a {report['team']['name']}")
        shown = [c for c in report["comparison"] if c["advantage"] != "neutral"][:COMPARISON_ROWS]
        rows = [[c["label"], c["own_text"], c["rival_text"], {"own": own_name, "rival": report["team"]["name"], "even": "Igualado"}[c["advantage"]]] for c in shown]
        colors = [[None, None, None, GREEN if c["advantage"] == "own" else RED if c["advantage"] == "rival" else None] for c in shown]
        pdf.table(["Estadística", own_name, report["team"]["name"], "Ventaja"], rows, [66, 32, 32, 56], ["L", "R", "R", "L"], colors)


def _games(pdf: ScoutingPDF, report: Dict[str, Any]) -> None:
    pdf.h2("Partidos analizados")
    rows = [[g["date"][:10], g["opponent"], "Local" if g["home"] else "Visitante", f"{g['score_for']}-{g['score_against']}",
             "V" if g["margin"] > 0 else "D"] for g in report["games"]]
    pdf.table(["Fecha", "Rival", "Cancha", "Resultado", ""], rows, [26, 84, 26, 30, 10], ["L", "L", "L", "R", "C"])


def render_scouting_pdf(report: Dict[str, Any], subtitle: str = "", own_name: str = "Nuestro equipo", compress: bool = True) -> bytes:
    """The PDF of a scouting report; ``subtitle`` (e.g. the competition) goes to the footer, ``own_name`` to the matchup."""
    pdf = ScoutingPDF("Scouting rival", subtitle)
    pdf.set_compression(compress)
    pdf.add_page()
    _summary(pdf, report)
    _keys_and_plan(pdf, report)
    _people(pdf, report)
    _zones(pdf, report)
    _patterns(pdf, report)
    _alerts_and_matchup(pdf, report, own_name)
    _games(pdf, report)
    return bytes(pdf.output())
