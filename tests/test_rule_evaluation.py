"""The rule evaluator end to end (issue #238): packages without leakage, "as live" replay from both sides, labels,
configurations to compare, recordings and the staff's feedback."""
import json
from pathlib import Path

import pytest

from src.live_core.recorded_feed import RecordedFeed
from src.live_prep.rule_evaluation import ConfigSpec, attach_feedback, evaluate, validate_config

A, B, C = "982047", "981204", "900003"
RECORDINGS = Path(__file__).parent / "recordings"
VALID_LABELS = {None, "seguida", "anticipada", "tarde", "no"}


def remap(doc, mapping):
    text = json.dumps(doc)
    for old, new in mapping.items():
        text = text.replace(f'"{old}"', f'"{new}"')
    return json.loads(text)


def dated(doc, code, start):
    out = json.loads(json.dumps(doc))
    out["_id"] = code
    out["HEADER"]["starttime"] = start
    return out


@pytest.fixture(scope="module")
def season(feb_game_doc):
    """A-B on 1/10 and 5/10, then A-C on 10/10 (B's side of the sample renamed to C)."""
    return [dated(feb_game_doc, "G0", "01-10-2025 - 12:00"), dated(feb_game_doc, "G1", "05-10-2025 - 12:30"),
            dated(remap(feb_game_doc, {B: C}), "G2", "10-10-2025 - 12:00")]


@pytest.fixture(scope="module")
def two_configs(season):
    configs = [ConfigSpec("base"), ConfigSpec("sin_faltas", {"rules_off": ["foul_trouble", "rival_foul_trouble"]})]
    return evaluate(season, configs=configs)


# --- who is evaluated and with what -------------------------------------------------------

def test_every_game_is_evaluated_from_both_sides_in_date_order(two_configs):
    assert [(g["game"], g["team"]) for g in two_configs.team_games] == [
        ("G0", A), ("G0", B), ("G1", A), ("G1", B), ("G2", A), ("G2", C)]


def test_a_package_only_has_the_games_played_before(two_configs):
    prior = {(g["game"], g["team"]): g["prior"] for g in two_configs.team_games}
    assert prior == {("G0", A): 0, ("G0", B): 0, ("G1", A): 1, ("G1", B): 1, ("G2", A): 2, ("G2", C): 0}


def test_games_that_start_together_do_not_see_each_other(feb_game_doc):
    twin = [dated(feb_game_doc, "T1", "05-10-2025 - 12:30"), dated(remap(feb_game_doc, {B: C}), "T2", "05-10-2025 - 12:30")]
    ev = evaluate(twin)
    assert {(g["game"], g["team"]): g["prior"] for g in ev.team_games}[("T2", A)] == 0


def test_the_minimum_of_prior_games_leaves_out_the_perspectives_with_little_history(season):
    ev = evaluate(season[:2], min_prior_games=1)
    assert [(g["game"], g["team"]) for g in ev.team_games] == [("G1", A), ("G1", B)]


def test_one_team_can_be_picked_but_the_season_is_still_learned_from_everybody(season):
    ev = evaluate(season, team=A)
    assert [(g["game"], g["prior"]) for g in ev.team_games] == [("G0", 0), ("G1", 1), ("G2", 2)]


def test_each_team_game_says_how_long_it_lasted_how_it_was_timed_and_its_timeouts(two_configs):
    g = two_configs.team_games[0]
    assert g["duration_s"] == 2400 and g["timing"] == "game_clock" and g["polls"] > 100
    assert g["timeouts"] == sorted(g["timeouts"]) and g["rival"] == B


def test_the_run_rule_is_simulated_with_other_thresholds_on_every_game(two_configs):
    assert [row["spec"] for row in two_configs.simulation][:2] == ["8 sin respuesta en 150 s", "6 netos en 150 s"]
    assert len(two_configs.simulation) == 6 and all("fires" in row for row in two_configs.simulation)


# --- the alerts ---------------------------------------------------------------------------

def test_alerts_are_rows_with_their_labels_and_outcome(two_configs):
    rows = two_configs.rows
    assert rows and {r["config"] for r in rows} == {"base", "sin_faltas"}
    for r in rows:
        assert r["elapsed"] <= r["shown"], "an alert cannot be on screen before the engine produced it"
        assert r["label"] in VALID_LABELS
        assert {"net_before", "net_after", "net_delta", "measure"} <= set(r["outcome"])
        assert r["severity"] in ("critical", "warning", "info") and r["message"]
    labelled = {r["id"] for r in rows if r["label"] is not None}
    assert labelled <= {"foul_trouble", "fatigue_high", "rival_run", "turnover_streak", "four_factors_lever"}


def test_the_sample_game_gets_foul_alerts_for_its_own_team_in_the_base_configuration(two_configs):
    base = [r for r in two_configs.rows if r["config"] == "base" and r["game"] == "G1" and r["team"] == A]
    assert any(r["id"] == "foul_trouble" and r["severity"] == "critical" for r in base)


def test_a_configuration_with_rules_off_is_compared_on_the_very_same_games(two_configs):
    ids = lambda name: {r["id"] for r in two_configs.rows if r["config"] == name}  # noqa: E731
    assert {"foul_trouble", "rival_foul_trouble"} <= ids("base")
    assert not ({"foul_trouble", "rival_foul_trouble"} & ids("sin_faltas"))
    assert ids("sin_faltas") <= ids("base")
    count = lambda name: sum(1 for r in two_configs.rows if r["config"] == name and r["id"] == "fatigue_high")  # noqa: E731
    assert count("sin_faltas") == count("base")


def test_two_runs_give_the_same_rows(season):
    first, second = evaluate(season[:2], team=A), evaluate(season[:2], team=A)
    assert first.rows == second.rows and first.team_games == second.team_games


# --- coach behaviour and configuration ---------------------------------------------------

def test_coach_behaviour_is_collected_from_every_game_even_those_not_evaluated(season):
    ev = evaluate(season[:2], min_prior_games=1)
    assert len(ev.coach) == 2 and {"timeouts", "stints", "foul_cases", "droughts"} <= set(ev.coach[0])


def test_unknown_rules_or_settings_are_rejected_before_replaying_anything():
    with pytest.raises(ValueError, match="no_such_rule"):
        validate_config(ConfigSpec("typo", {"rules_off": ["rival_run", "no_such_rule"]}))
    with pytest.raises(ValueError, match="run_pointz"):
        validate_config(ConfigSpec("typo", {"run_pointz": 6}))
    validate_config(ConfigSpec("fine", {"rules_off": ["rival_run"], "run_points": 6}))
    with pytest.raises(ValueError):
        evaluate([], configs=[ConfigSpec("typo", {"rules_off": ["nope"]})])


def test_a_game_that_is_not_between_two_teams_is_skipped(season):
    broken = json.loads(json.dumps(season[0]))
    broken["HEADER"]["TEAM"] = broken["HEADER"]["TEAM"][:1]
    ev = evaluate([broken])
    assert ev.team_games == [] and ev.rows == []


# --- recordings ---------------------------------------------------------------------------

def test_a_recording_is_replayed_as_it_was_served_with_the_clock_of_the_feed():
    feed = RecordedFeed.load(RECORDINGS / "2524470.rec.json.gz")
    ev = evaluate([], recordings={"2524470": feed}, poll_s=60)
    assert {(g["game"], g["timing"]) for g in ev.team_games} == {("2524470", "recording")}
    assert {g["team"] for g in ev.team_games} == {"1008631", "1008898"}
    assert ev.rows and all(r["shown"] == r["elapsed"] for r in ev.rows)
    leon = [r for r in ev.rows if r["team"] == "1008631"]
    assert any(r["id"] == "foul_trouble" for r in leon)


# --- the staff's feedback ----------------------------------------------------------------

def feedback_export(code, entries):
    return {"v": 1, "kind": "basketlab-live-feedback", "context": f"live:{code}", "package_id": "p", "entries": entries}


def test_feedback_is_joined_to_the_alerts_of_the_baseline_by_match_and_key():
    rows = [{"game": "G1", "config": "base", "key": "a"}, {"game": "G1", "config": "base", "key": "b"},
            {"game": "G1", "config": "other", "key": "a"}, {"game": "G2", "config": "base", "key": "a"}]
    export = feedback_export("G1", [{"key": "a", "verdict": "seguida"}, {"key": "b", "verdict": None},
                                    {"key": "zzz", "verdict": "descartada"}])
    unmatched = attach_feedback(rows, [export], baseline="base")
    assert [(r.get("feedback"), r.get("verdict")) for r in rows] == [(True, "seguida"), (True, None), (None, None), (None, None)]
    assert unmatched == 1


def test_feedback_without_a_match_context_is_ignored():
    rows = [{"game": "G1", "config": "base", "key": "a"}]
    assert attach_feedback(rows, [{"context": "garbage", "entries": []}, {}], baseline="base") == 0
    assert "feedback" not in rows[0]
