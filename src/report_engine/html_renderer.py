"""Report dict -> simple HTML (tags supported by fpdf2 ``write_html``; Latin-1 safe)."""
from html import escape
from typing import Any, Dict, List

TITLES = {
    "own": dict(
        h1="Análisis de equipo", strengths="Puntos fuertes clave", weaknesses="Debilidades críticas",
        tactics="Recomendaciones tácticas", training="Enfoque de entrenamiento",
        training_intro="Prioridades de mejora, de mayor a menor diferencia con la liga:",
    ),
    "rival": dict(
        h1="Scouting rival", strengths="Peligros a neutralizar", weaknesses="Debilidades a explotar",
        tactics="Claves tácticas del partido", training="Plan de partido",
        training_intro="Acciones prioritarias: neutralizar sus fortalezas y explotar sus debilidades:",
    ),
}
LOW_SAMPLE_NOTICE = (
    "<p><b>Aviso: muestra pequeña ({n} partidos).</b> Los resultados son orientativos y pueden "
    "cambiar mucho en las próximas jornadas.</p>"
)
KIND = {"improve": "Mejorar", "leverage": "Potenciar", "neutralize": "Neutralizar", "exploit": "Explotar"}


def _items(rows: List[str]) -> str:
    return "<ul>" + "".join(f"<li>{r}</li>" for r in rows) + "</ul>" if rows else "<p>Sin datos destacados.</p>"


def _finding(f: Dict[str, Any]) -> str:
    d = f.get("diff_pct")
    diff = f" ({d:+.1f}% vs mediana de la liga)" if d is not None else ""
    return f"<b>{escape(f['label'])}</b>: {escape(f['formatted'])}{diff}. {escape(f['text'])}"


def _differential(x: Dict[str, Any]) -> str:
    tag = "VENTAJA" if x["advantage"] else "DESVENTAJA"
    return f"<b>[{tag}]</b> {escape(x['label'])}: {escape(x['formatted'])} ({x['diff_pct']:+.1f}% vs mediana)"


def _consistency(x: Dict[str, Any]) -> str:
    tag = "INCONSISTENTE" if x["status"] == "inconsistent" else "CONSISTENTE"
    return f"<b>[{tag}]</b> {escape(x['label'])} (CV {x['cv']:.0f}%). {escape(x['text'])}"


def _zone(z: Dict[str, Any]) -> str:
    tag = "CALIENTE" if z["kind"] == "hot" else "FRIA"
    note = " (muestra pequeña)" if z.get("low_sample") else ""
    return (f"<b>[{tag}]</b> {escape(str(z['label']))}: {z['fg_pct']:.0f}% en {z['fga']} tiros, "
            f"liga {z['league_pct']:.0f}% ({z['delta_pp']:+.1f} pp){note}. {escape(z['text'])}")


def _action(x: Dict[str, Any]) -> str:
    return f"<b>{KIND[x['kind']]}</b> - {escape(x['label'])}: {escape(x['text'])}"


def _tactics(rows: List[Dict[str, Any]]) -> str:
    out = []
    for area in ("ofensiva", "defensiva"):
        sel = [_action(x) for x in rows if x["area"] == area]
        if sel:
            out.append(f"<h3>{area.capitalize()}</h3>{_items(sel)}")
    return "".join(out) or "<p>Sin recomendaciones destacadas.</p>"


def render_report_html(report: Dict[str, Any]) -> str:
    t = TITLES[report["mode"]]
    team = escape(report["team"])
    parts = [
        f"<h1>{t['h1']}: {team}</h1>",
        f"<p>Partidos analizados: {report['games_played']}. Comparado con los cuartiles de la competición.</p>",
        LOW_SAMPLE_NOTICE.format(n=report["games_played"]) if report.get("low_sample") else "",
        f"<h2>Perfil de equipo</h2>{_items([escape(p) for p in report['profile']])}",
        f"<h2>{t['strengths']}</h2>{_items([_finding(f) for f in report['strengths']])}",
        f"<h2>{t['weaknesses']}</h2>{_items([_finding(f) for f in report['weaknesses']])}",
        f"<h2>Análisis diferencial vs liga</h2>{_items([_differential(x) for x in report['differentials']])}",
        f"<h2>Zonas de tiro</h2>{_items([_zone(z) for z in report.get('zones', [])])}",
        f"<h2>Consistencia partido a partido</h2>{_items([_consistency(x) for x in report['consistency']])}",
        f"<h2>{t['tactics']}</h2>{_tactics(report['tactics'])}",
        f"<h2>{t['training']}</h2><p>{t['training_intro']}</p>",
        "<ol>" + "".join(f"<li>{_action(x)}</li>" for x in report["training"]) + "</ol>"
        if report["training"] else "<p>Sin prioridades destacadas.</p>",
    ]
    return "\n".join(parts)
