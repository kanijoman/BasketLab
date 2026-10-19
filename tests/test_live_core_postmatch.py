"""Post-match analysis (issue #409): evolution of the game, runs and what explains them, lineups, what went well and what could be
better, and the alerts of the match with their context. Pure standard-library code that runs on the tablet (Pyodide)."""
import json
from pathlib import Path

import pytest

from src.live_core.postmatch import REPORT_VERSION, build_report, enrich_alerts, evolution, find_runs
from src.live_core.recorded_feed import RecordedFeed

RECORDINGS = Path(__file__).parent / "recordings"
OWN, RIVAL = "T1", "T2"


def score(t, team, value=2):
    return (t, team, value)


# --- runs: unanswered scoring ------------------------------------------------------------------------------------------------

def test_a_run_is_a_streak_of_unanswered_points_of_at_least_the_minimum():
    scores = [score(10, OWN), score(50, RIVAL), score(100, OWN, 3), score(130, OWN), score(160, OWN, 3), score(200, OWN), score(240, RIVAL)]
    [run] = find_runs(scores, OWN, RIVAL, min_pts=8)
    assert (run["team"], run["start"], run["end"], run["pts"]) == (OWN, 100, 200, 10)
    assert run["score_before"] == [2, 2] and run["score_after"] == [12, 2]


def test_shorter_streaks_and_alternating_scoring_are_not_runs():
    assert find_runs([score(10, OWN), score(20, OWN), score(30, RIVAL), score(40, RIVAL)], OWN, RIVAL, min_pts=8) == []
    assert find_runs([score(i * 10, OWN if i % 2 else RIVAL) for i in range(20)], OWN, RIVAL, min_pts=8) == []


def test_runs_of_both_teams_come_in_game_order_and_free_throws_count_as_points():
    scores = [score(10, RIVAL, 3), score(20, RIVAL), score(30, RIVAL, 3), score(40, OWN, 1), score(50, OWN, 1)]
    scores += [score(60 + 10 * i, OWN) for i in range(5)]
    runs = find_runs(scores, OWN, RIVAL, min_pts=8)
    assert [(r["team"], r["pts"]) for r in runs] == [(RIVAL, 8), (OWN, 12)]


# --- evolution -----------------------------------------------------------------------------------------------------------------

def test_the_evolution_counts_lead_changes_ties_and_the_biggest_lead_and_deficit():
    scores = [score(60, OWN), score(120, RIVAL), score(180, RIVAL), score(240, OWN, 3), score(300, OWN, 3), score(360, RIVAL, 3)]
    evo = evolution(scores, OWN, RIVAL, end=600)
    assert evo["lead_changes"] == 2 and evo["ties"] == 1            # own ahead, tie, rival ahead, own ahead again
    assert evo["max_lead"] == {"margin": 4, "elapsed": 300}
    assert evo["max_deficit"] == {"margin": 2, "elapsed": 180}
    assert evo["timeline"][0] == [0, 0] and evo["timeline"][-1][0] == 600
    assert all(b[0] - a[0] <= 60 for a, b in zip(evo["timeline"], evo["timeline"][1:]))


def test_a_game_without_points_has_a_flat_evolution():
    evo = evolution([], OWN, RIVAL, end=120)
    assert evo["lead_changes"] == 0 and evo["max_lead"]["margin"] == 0 and evo["timeline"][-1] == [120, 0]


# --- the whole report on the recorded match (Zamora - Leon, Leon is the own team) -----------------------------------------------

@pytest.fixture(scope="module")
def doc():
    feed = RecordedFeed.loads((RECORDINGS / "2524470.rec.json.gz").read_bytes())
    return feed.document_at(feed.duration)


@pytest.fixture(scope="module")
def report(doc):
    return build_report(doc, "1008631")


def test_the_report_has_the_match_the_periods_and_the_result(report):
    assert report["version"] == REPORT_VERSION
    match = report["match"]
    assert match["own"]["name"].strip().startswith("MIPELLETYMAS") and match["rival"]["name"].strip().startswith("RECOLETAS")
    assert (match["score"]["own"], match["score"]["rival"]) == (38, 59) and match["result"] == "loss"
    assert [p["period"] for p in match["periods"]] == [1, 2, 3, 4]
    assert sum(p["own"] for p in match["periods"]) == 38 and sum(p["rival"] for p in match["periods"]) == 59
    assert all(p["net"] == p["own"] - p["rival"] for p in match["periods"])


def test_the_runs_are_real_streaks_with_the_players_on_court_and_a_reason(report, doc):
    runs = report["runs"]
    assert runs and all(r["pts"] >= 8 and r["team"] in ("own", "rival") for r in runs)
    assert [r["start"] for r in runs] == sorted(r["start"] for r in runs)
    for run in runs:
        assert run["period"] >= 1 and run["clock"] and len(run["lineup"]) == 5 and run["explanation"]
        assert all(isinstance(name, str) and name for name in run["lineup"])
        assert run["score_after"][0] - run["score_before"][0] >= 0


def test_the_lineups_are_ranked_by_net_points_with_enough_minutes(report):
    lineups = report["lineups"]
    assert lineups["best"] and lineups["worst"]
    assert all(row["seconds"] >= 120 and len(row["players"]) == 5 for row in lineups["best"] + lineups["worst"])
    assert lineups["best"][0]["net"] >= lineups["worst"][0]["net"]


def test_it_says_what_went_well_and_what_could_be_better_with_numbers(report):
    assert report["went_well"] and report["to_improve"]
    assert all(isinstance(t, str) and t for t in report["went_well"] + report["to_improve"])
    assert report["four_factors"]["own"].keys() == {"efg", "tov", "orb", "ftr"}
    assert report["players"]["top"] and report["players"]["top"][0]["pm"] >= report["players"]["bottom"][0]["pm"]


def test_each_period_has_its_summary_keys(report):
    first = report["match"]["periods"][0]
    assert "keys" in first and "adjustments" in first


def test_the_report_is_json_serialisable_and_deterministic(doc, report):
    assert json.loads(json.dumps(report)) == report
    assert build_report(doc, "1008631") == report


def test_the_other_team_can_be_the_own_one(doc):
    other = build_report(doc, "1008898")
    assert other["match"]["result"] == "win" and other["match"]["score"] == {"own": 59, "rival": 38}


# --- alerts of the match with their context ----------------------------------------------------------------------------------

def test_the_alerts_are_listed_with_period_clock_and_the_score_at_that_moment(report):
    alerts = [
        {"alert": {"key": "k1", "id": "foul_trouble", "severity": "warning", "category": "faltas", "message": "Ana: 3 faltas", "proposal": []}, "at": "Q1 05:00"},
        {"alert": {"key": "k2", "id": "rival_run", "severity": "critical", "category": "rival", "message": "Parcial", "proposal": []}, "at": "Q4 01:30"},
    ]
    rows = enrich_alerts(alerts, report["timeline"])
    assert [r["key"] for r in rows] == ["k1", "k2"]
    assert rows[0]["period"] == 1 and rows[0]["clock"] == "05:00" and rows[0]["elapsed"] == 300
    assert rows[1]["period"] == 4 and rows[1]["elapsed"] == 2310
    assert rows[1]["score"] == [38, 59] or rows[1]["score"][1] > rows[1]["score"][0]
    assert rows[0]["severity"] == "warning" and rows[0]["message"] == "Ana: 3 faltas"


def test_an_overtime_label_and_an_unreadable_one_are_handled():
    rows = enrich_alerts([{"alert": {"key": "a", "id": "x", "severity": "info", "category": "c", "message": "m"}, "at": "PR1 02:00"},
                          {"alert": {"key": "b", "id": "x", "severity": "info", "category": "c", "message": "m"}, "at": "??"}], [[0, [0, 0]]])
    assert rows[0]["period"] == 5 and rows[0]["elapsed"] == 2400 + 180
    assert rows[1]["period"] is None and rows[1]["elapsed"] is None


# --- the session entry points the app calls -------------------------------------------------------------------------------------

def test_the_session_builds_the_report_for_its_own_team_from_json_text(doc):
    from src.live_core.session import LiveSession, report_json, start_json
    package = (RECORDINGS / "2524470.package.json").read_text(encoding="utf-8")
    alerts = [{"alert": {"key": "k", "id": "fatigue_high", "severity": "info", "category": "rotacion", "message": "m"}, "at": "Q2 03:00"}]
    direct = LiveSession(package).report(doc, alerts)
    start_json(package)
    via_json = json.loads(report_json(json.dumps(doc), json.dumps(alerts)))
    assert via_json == direct and via_json["match"]["own"]["id"] == "1008631"
    assert [a["key"] for a in via_json["alerts"]] == ["k"] and via_json["alerts"][0]["period"] == 2
    assert json.loads(report_json(json.dumps(doc)))["alerts"] == []
