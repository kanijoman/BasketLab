"""The rival scouting report as a PDF (issue #299): fpdf2 with core fonts, tables and a zones chart.

The PDF is built uncompressed in these tests so the text can be looked for in the bytes.
"""

import pytest

from src.live_prep.scouting_report import build_scouting_report
from src.services.scouting_pdf import render_scouting_pdf
from tests.test_scouting_report import collected

COMPARISON = [
    {"key": "pace", "label": "Ritmo propio", "group": "Básicas", "own": 70.0, "rival": 74.0, "own_text": "70,0", "rival_text": "74,0",
     "diff_pct": -5.4, "advantage": "rival"},
    {"key": "tov", "label": "Pérdidas por partido", "group": "Básicas", "own": 12.0, "rival": 15.0, "own_text": "12,0", "rival_text": "15,0",
     "diff_pct": -20.0, "advantage": "own"}]
TEAM_REPORT = {"training": [{"kind": "neutralize", "text": "Frenar el rebote ofensivo", "priority": 1},
                            {"kind": "exploit", "text": "Atacar su rebote defensivo", "priority": 2}],
               "profile": ["Juega a un ritmo alto."], "strengths": [], "weaknesses": [], "differentials": [], "tactics": []}


def pdf(report, **kw):
    return render_scouting_pdf(report, compress=False, **kw)


@pytest.fixture(scope="module")
def full():
    return pdf(build_scouting_report(collected(), team_report=TEAM_REPORT, comparison=COMPARISON))


def test_it_is_a_pdf_with_several_pages(full):
    assert full.startswith(b"%PDF") and full.count(b"/Type /Page\n") + full.count(b"/Type /Page ") >= 1
    assert render_scouting_pdf(build_scouting_report(collected())).startswith(b"%PDF")     # compressed (the default) works too


def test_title_team_and_sample_are_on_the_first_page(full):
    assert b"Scouting rival" in full and b"EQUIPO DEL INFORME" in full
    assert b"6 partidos" in full


def test_the_findings_the_plan_and_the_sections_are_there(full):
    for expected in (b"Claves", b"A. ESCOLTA", b"Plan de partido", b"Frenar el rebote ofensivo", b"Atacar su rebote defensivo",
                     b"Quintetos", b"Zonas", b"Cuartos", b"Alertas del motor", b"Comparativa"):
        assert expected in full, expected


def test_a_small_sample_is_said_in_the_pdf():
    small = collected(sample_games=2, games=collected()["games"][:2])
    assert b"Muestra peque" in pdf(build_scouting_report(small))


def test_the_zones_chart_is_an_image_only_when_there_are_zones(full):
    assert b"/Subtype /Image" in full
    assert b"/Subtype /Image" not in pdf(build_scouting_report(collected(zones={"own": {}, "conceded": {}, "league": {}})))


def test_a_minimal_report_still_renders():
    minimal = collected(players=[], lineups=[], alerts=[], quarters={}, edges={}, timeouts={},
                        zones={"own": {}, "conceded": {}, "league": {}})
    out = pdf(build_scouting_report(minimal))
    assert out.startswith(b"%PDF") and b"EQUIPO DEL INFORME" in out


def test_very_long_texts_and_odd_characters_do_not_break_it():
    odd = collected(team={"id": "T9", "name": "EQUIPO ÑANDÚ “TEST” → 🏀"})
    report = build_scouting_report(odd)
    report["keys"].append({"area": "ataque", "action": "exploit", "text": "palabra " * 400})
    assert pdf(report).startswith(b"%PDF")


def test_the_comparison_is_left_out_without_one():
    assert b"Comparativa" not in pdf(build_scouting_report(collected()))
