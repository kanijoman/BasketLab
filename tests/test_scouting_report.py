"""The rival scouting report built from what the engine collected (issue #299): the findings, in Spanish, with their sample.

Pure functions over plain dicts; the team is whatever the data says (nothing here knows a team).
"""

import json

import pytest

from src.live_prep.scouting_report import build_scouting_report


def collected(**over):
    base = {
        "team": {"id": "T1", "name": "EQUIPO DEL INFORME"}, "sample_games": 6,
        "games": [{"code": str(i), "date": f"2026-10-{10 + i:02d}", "opponent_id": "X", "opponent": f"RIVAL {i}", "home": i % 2 == 0,
                   "score_for": f, "score_against": a, "margin": f - a}
                  for i, (f, a) in enumerate([(70, 60), (55, 65), (80, 70), (60, 66), (75, 70), (62, 64)])],
        "factors": {"own": {"efg": 0.50, "tov": 0.16, "orb": 0.30, "ftr": 0.30}, "rival": {"efg": 0.48, "tov": 0.17, "orb": 0.28, "ftr": 0.28}},
        "pace": 72.4,
        "players": [
            {"id": "p1", "name": "A. ESCOLTA", "games": 6, "minutes": 150.0, "pts": 120, "fga": 100, "pts_per_game": 20.0, "share": 0.31,
             "clutch": {"fga": 12, "fta": 8, "ftm": 6, "tov": 1, "pts": 18, "sec": 600}},
            {"id": "p2", "name": "B. PIVOT", "games": 6, "minutes": 140.0, "pts": 72, "fga": 60, "pts_per_game": 12.0, "share": 0.19,
             "clutch": {"fga": 4, "fta": 2, "ftm": 1, "tov": 0, "pts": 5, "sec": 500}}],
        "lineups": [{"players": ["A", "B", "C", "D", "E"], "seconds": 3000, "pts_for": 80, "pts_against": 60, "games": 6, "net40": 13.3},
                    {"players": ["A", "B", "C", "D", "F"], "seconds": 1500, "pts_for": 30, "pts_against": 50, "games": 5, "net40": -21.3}],
        "zones": {"own": {"restricted_area": {"a": 80, "m": 44, "pts": 88}, "center_three": {"a": 60, "m": 18, "pts": 54}},
                  "conceded": {"restricted_area": {"a": 70, "m": 45, "pts": 90}, "center_three": {"a": 50, "m": 14, "pts": 42}},
                  "league": {"restricted_area": {"a": 1000, "m": 540, "pts": 1080}, "center_three": {"a": 800, "m": 280, "pts": 840}}},
        "quarters": {"1": {"for": 17.0, "against": 16.0, "margin": 1.0}, "2": {"for": 17.0, "against": 16.0, "margin": 1.0},
                     "3": {"for": 14.0, "against": 18.0, "margin": -4.0}, "4": {"for": 17.0, "against": 16.0, "margin": 1.0}},
        "edges": {"start": {"1": 0.5, "2": 0.2, "3": -2.5, "4": 0.1}, "close": {"1": 0.0, "2": 0.3, "3": -0.4, "4": -1.0}},
        "timeouts": {"per_game": 2.5, "first_half": 1.2, "second_half": 1.3, "after_n": 15, "after_for": 2.0, "after_against": 3.5},
        "alerts": [{"id": "scoring_drought", "category": "gestion", "count": 12, "games": 5, "per_game": 2.0, "avg_minute": 22.5,
                    "severity": "warning", "message": "x"},
                   {"id": "turnover_streak", "category": "balon", "count": 6, "games": 4, "per_game": 1.0, "avg_minute": 15.0,
                    "severity": "warning", "message": "y"}],
    }
    base.update(over)
    return base


def texts(report):
    return " ".join(k["text"] for k in report["keys"])


def test_record_and_averages():
    r = build_scouting_report(collected())
    assert r["team"]["name"] == "EQUIPO DEL INFORME" and r["sample_games"] == 6
    assert (r["record"]["wins"], r["record"]["losses"]) == (3, 3)
    assert r["record"]["avg_for"] == pytest.approx(67.0) and r["record"]["avg_margin"] == pytest.approx(7 / 6)


def test_few_games_are_said_and_nothing_is_concluded_from_small_samples():
    r = build_scouting_report(collected(sample_games=2, games=collected()["games"][:2]))
    assert r["low_sample"] is True
    assert any("2 partidos" in n for n in r["notices"])
    tiny = collected(zones={"own": {"center_three": {"a": 4, "m": 0, "pts": 0}}, "conceded": {"center_three": {"a": 4, "m": 4, "pts": 12}},
                            "league": {"center_three": {"a": 800, "m": 280, "pts": 840}}})
    assert "centro" not in texts(build_scouting_report(tiny)).lower()


def test_a_team_that_depends_on_one_scorer():
    r = build_scouting_report(collected())
    assert "A. ESCOLTA" in texts(r) and "31 %" in texts(r)
    r2 = build_scouting_report(collected(players=[{**collected()["players"][0], "share": 0.15}]))
    assert "depende" not in texts(r2).lower()


def test_the_weak_quarter_and_the_bad_start_of_a_quarter():
    text = texts(build_scouting_report(collected()))
    assert "3.er cuarto" in text and "-4,0" in text
    assert "empieza" in text.lower()     # the first three minutes of the third quarter: -2.5


def test_what_happens_after_its_timeouts():
    text = texts(build_scouting_report(collected()))
    assert "tiempo muerto" in text.lower() and "3,5" in text and "2,0" in text


def test_a_zone_it_defends_badly_with_enough_shots():
    bad = {"restricted_area": {"a": 70, "m": 50, "pts": 100}, "center_three": {"a": 50, "m": 14, "pts": 42}}
    r = build_scouting_report(collected(zones={**collected()["zones"], "conceded": bad}))
    assert any(k["area"] == "defensa" and "Área Restringida" in k["text"] for k in r["keys"])


def test_zones_rows_with_the_rating_against_the_league():
    rows = build_scouting_report(collected())["zones"]
    assert [z["zone"] for z in rows] == ["restricted_area", "center_three"]         # most shots first
    z = rows[0]
    assert z["label"] == "Área Restringida" and z["own_fga"] == 80
    assert z["own_fg_pct"] == pytest.approx(55.0) and z["league_fg_pct"] == pytest.approx(54.0)
    assert z["own_delta_pp"] == pytest.approx(1.0) and z["conceded_fg_pct"] == pytest.approx(45 / 70 * 100)


def test_alerts_in_words_with_how_often_and_when():
    rows = build_scouting_report(collected())["alerts"]
    assert [a["id"] for a in rows] == ["scoring_drought", "turnover_streak"]
    assert "sequías" in rows[0]["text"].lower() and "2,0" in rows[0]["text"] and "22" in rows[0]["text"]


def test_best_and_worst_quintet_with_enough_minutes():
    text = " ".join(line["text"] for line in build_scouting_report(collected())["lineups"])
    assert "13,3" in text and "-21,3" in text


def test_the_plan_comes_from_the_team_report_when_there_is_one():
    team_report = {"training": [{"kind": "neutralize", "text": "Frenar el rebote ofensivo", "priority": 1},
                                {"kind": "exploit", "text": "Atacar su rebote defensivo", "priority": 2}], "profile": ["Ritmo alto."],
                   "strengths": [], "weaknesses": []}
    r = build_scouting_report(collected(), team_report=team_report)
    assert "Frenar el rebote ofensivo" in [p["text"] for p in r["plan"]["neutralize"]]
    assert "Atacar su rebote defensivo" in [p["text"] for p in r["plan"]["exploit"]]
    assert "Ritmo alto." in r["profile"]


def test_the_plan_without_a_team_report_is_built_from_the_findings():
    r = build_scouting_report(collected())
    assert r["plan"]["exploit"] and r["plan"]["neutralize"]


def test_comparison_with_our_team_is_carried_when_given():
    comparison = [{"key": "pace", "label": "Ritmo", "own": 70.0, "rival": 74.0, "own_text": "70,0", "rival_text": "74,0", "advantage": "rival"}]
    assert build_scouting_report(collected(), comparison=comparison)["comparison"] == comparison
    assert build_scouting_report(collected())["comparison"] == []


def test_it_is_plain_json_and_the_keys_are_limited_and_ordered():
    r = build_scouting_report(collected())
    json.dumps(r)
    assert 1 <= len(r["keys"]) <= 8
    assert all(k["area"] and k["text"] for k in r["keys"])


def test_every_alert_the_engine_can_raise_about_a_team_has_its_words():
    """A new rule must be given a label here (or be about the rivals): the PDF must not show a raw rule id."""
    import re
    from pathlib import Path

    from src.live_prep.scouting_collect import _about_the_team
    from src.live_prep.scouting_report import ALERTS

    ids = set()
    for path in Path("src/live_core").glob("rules_*.py"):
        ids |= set(re.findall(r'\bid="([a-z0-9_]+)"', path.read_text(encoding="utf-8")))
    ids |= set(re.findall(r'\bid="([a-z0-9_]+)"', Path("src/live_core/advice.py").read_text(encoding="utf-8")))
    missing = sorted(i for i in ids if _about_the_team(i) and i not in ALERTS)
    assert not missing, f"alert ids without a label in scouting_report.ALERTS: {missing}"


def test_with_a_small_sample_every_finding_carries_how_few_games_are_behind_it():
    small = build_scouting_report(collected(sample_games=2, games=collected()["games"][:2]))
    assert small["keys"] and all(k["text"].endswith("(solo 2 partidos)") for k in small["keys"])
    assert all("solo" not in k["text"].split("(")[-1] for k in build_scouting_report(collected())["keys"])
    assert all("(solo 2 partidos)" in p["text"] for p in small["plan"]["exploit"] + small["plan"]["neutralize"] if p["source"] == "motor")


def test_the_plan_takes_only_the_main_findings_of_the_engine_so_it_does_not_repeat_the_whole_list():
    many = collected(alerts=[{"id": i, "category": "x", "count": 9, "games": 5, "per_game": 2.0, "avg_minute": 20.0, "severity": "warning", "message": "m"}
                             for i in ("own_drought", "turnover_streak", "cold_fg_streak", "paint_battle", "team_fouls_bonus", "rival_run")])
    plan = build_scouting_report(many)["plan"]
    for side in ("neutralize", "exploit"):
        assert sum(1 for p in plan[side] if p["source"] == "motor") <= 3
