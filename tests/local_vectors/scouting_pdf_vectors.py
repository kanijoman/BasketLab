"""The vectors of the PDF of the rival scouting in the browser (#715): what the layout of the server asks of the page for a report, call by call, the reference of
``frontend/src/lib/scoutingPdf.test.ts``.

``scouting_pdf.lay_out`` is the real layout; it is run over a recorder that writes down every call (heading, paragraph, bullet, table with its widths and colours, spacing, the chart) instead
of drawing it. The web must ask for the same things, in the same order, with the same texts: what jsPDF then draws is the browser's. The chart of the zones is an image on the server
(matplotlib): here it is only noted that there is one.
"""
from typing import Any, Dict, List
from unittest.mock import patch

from tests.test_scouting_report import collected

from src.live_prep.scouting_report import build_scouting_report
from src.services import scouting_pdf
from src.services.scouting_pdf_parts import safe, zones_chart as real_zones_chart

COMPARISON = [
    {"key": "pace", "label": "Ritmo propio", "group": "Básicas", "own": 70.0, "rival": 74.0, "own_text": "70,0", "rival_text": "74,0", "diff_pct": -5.4, "advantage": "rival"},
    {"key": "tov", "label": "Pérdidas por partido", "group": "Básicas", "own": 12.0, "rival": 15.0, "own_text": "12,0", "rival_text": "15,0", "diff_pct": -20.0, "advantage": "own"},
    {"key": "orb", "label": "Rebote ofensivo", "group": "Básicas", "own": 10.0, "rival": 10.0, "own_text": "10,0", "rival_text": "10,0", "diff_pct": 0.0, "advantage": "even"},
    {"key": "x", "label": "Sin ventaja", "group": "Básicas", "own": 1.0, "rival": 1.0, "own_text": "1", "rival_text": "1", "diff_pct": 0.0, "advantage": "neutral"},
]
TEAM_REPORT = {"training": [{"kind": "neutralize", "text": "Frenar el rebote ofensivo", "priority": 1}, {"kind": "exploit", "text": "Atacar su rebote defensivo", "priority": 2}],
               "profile": ["Juega a un ritmo alto."], "strengths": [], "weaknesses": [], "differentials": [], "tactics": []}
ORIGIN = {"own": {"fast_break": 12.0, "second_chance": 9.5, "off_turnovers": 14.0, "paint": 38.0, "bench_pct": 31.5},
          "conceded": {"fast_break": 9.0, "second_chance": 11.0, "off_turnovers": 12.5, "paint": 40.0, "bench_pct": 28.0},
          "league": {"fast_break": 10.0, "second_chance": 10.0, "off_turnovers": 13.0, "paint": 36.0, "bench_pct": 30.0}}
EMPTY_ZONES = {"own": {}, "conceded": {}, "league": {}}
ODD_NAME = "EQUIPO “ÑANDÚ” — 日本 ✅"


class Recorder:
    """The methods of ``ScoutingPDF`` that the layout calls, writing down what they are asked for."""

    def __init__(self) -> None:
        self.calls: List[List[Any]] = []

    def h1(self, text): self.calls.append(["h1", text])

    def h2(self, text, keep_with=35): self.calls.append(["h2", text, keep_with])

    def para(self, text, size=10, bold=False, color=(30, 30, 30)): self.calls.append(["para", text, size, bold, list(color)])

    def bullet(self, text, tag="", size=10): self.calls.append(["bullet", text, tag, size])

    def ln(self, h=None): self.calls.append(["ln", h])

    def image_bytes(self, png, width=180): self.calls.append(["image", width])

    def table(self, headers, rows, widths, aligns=None, colors=None):
        self.calls.append(["table", list(headers), [list(r) for r in rows], list(widths), list(aligns) if aligns else None,
                           [[list(c) if c else None for c in row] for row in colors] if colors else None])


def _calls(report: Dict[str, Any], own_name: str) -> List[List[Any]]:
    recorder = Recorder()
    with patch.object(scouting_pdf, "zones_chart", lambda rows, team: b"chart" if real_zones_chart(rows, team) else None):
        scouting_pdf.lay_out(recorder, report, own_name)
    return recorder.calls


def build() -> Dict[str, Any]:
    small = collected(sample_games=2, games=collected()["games"][:2])
    minimal = collected(players=[], lineups=[], alerts=[], quarters={}, edges={}, timeouts={}, zones=EMPTY_ZONES)
    long_names = collected(players=[{**collected()["players"][0], "name": "UN NOMBRE MUY LARGO DE JUGADOR QUE NO CABE EN LA COLUMNA DE LA TABLA"}])
    cases = [
        ("full, with the team report, the comparison and the origin of the points", build_scouting_report(collected(origin=ORIGIN), team_report=TEAM_REPORT, comparison=COMPARISON), "Nuestro equipo"),
        ("full, in a women's competition", build_scouting_report(collected(origin=ORIGIN), team_report=TEAM_REPORT, comparison=COMPARISON, gender="F"), "MI CLUB & Co"),
        ("a small sample says it on the first page", build_scouting_report(small), "Nuestro equipo"),
        ("a minimal report: no players, lineups, alerts, quarters or zones", build_scouting_report(minimal), "Nuestro equipo"),
        ("without comparison nor origin", build_scouting_report(collected(origin=None)), "Nuestro equipo"),
        ("a name too long for its column", build_scouting_report(long_names), "Nuestro equipo"),
        ("characters beyond Latin-1", build_scouting_report(collected(team={"id": "T1", "name": ODD_NAME})), "Nuestro equipo"),
    ]
    odd = ["plain", "a — b … c → d − 1", "“quoted” ‘x’", "Ñandú ª º ç", "emoji ✅ and 🔥", "日本", "", 42]
    return {"cases": [{"name": name, "own_name": own, "report": report, "calls": _calls(report, own)} for name, report, own in cases],
            "safe": [[value, safe(value)] for value in odd]}
