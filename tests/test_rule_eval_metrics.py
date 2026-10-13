"""Per-rule metrics of the rule evaluator (issue #238), over hand-made alert rows of ONE configuration."""
import pytest

from src.live_prep.eval_metrics import rule_metrics

OWN = "T1"


def alert(rule="fatigue_high", game="G1", e=100, s=130, severity="warning", key=None, label=None, delay=None,
          net=0, measure=None, evidence=None, **extra):
    return {"game": game, "team": OWN, "id": rule, "key": key or f"{rule}:{e}", "severity": severity,
            "elapsed": e, "shown": s, "label": label, "delay": delay, "action_at": None,
            "evidence": evidence if evidence is not None else {"player_id": "p1"},
            "outcome": {"net_before": 0, "net_after": net, "net_delta": net, "measure": measure}, **extra}


def team_game(game="G1", duration=2400, timeouts=()):
    return {"game": game, "team": OWN, "duration_s": duration, "timeouts": list(timeouts)}


def test_volume_per_team_game_and_per_ten_minutes():
    rows = [alert(e=100), alert(e=900, key="x"), alert("rival_run", severity="critical")]
    games = [team_game("G1"), team_game("G2")]            # 2 team-games, 80 minutes of play
    m = rule_metrics(rows, games)
    assert m["fatigue_high"]["alerts"] == 2
    assert m["fatigue_high"]["per_team_game"] == 1.0 and m["fatigue_high"]["per_10min"] == 0.25
    assert m["all"]["alerts"] == 3 and m["all"]["per_team_game"] == 1.5
    assert m["rival_run"]["severity"] == {"critical": 1, "warning": 0, "info": 0}


def test_visible_alerts_are_the_distinct_keys_of_the_game():
    rows = [alert(key="same"), alert(e=500, key="same"), alert(e=900, key="other")]
    m = rule_metrics(rows, [team_game()])
    assert m["fatigue_high"]["alerts"] == 3 and m["fatigue_high"]["visible"] == 2   # the app drops a repeated key


def test_a_repeated_alert_about_the_same_subject_within_ten_minutes_is_a_duplicate():
    rows = [alert(e=100), alert(e=400, key="b"), alert(e=1200, key="c")]            # 300 s apart, then 800 s
    assert rule_metrics(rows, [team_game()])["fatigue_high"]["duplicates"] == 1


def test_different_players_severities_or_games_are_not_duplicates():
    rows = [alert(e=100), alert(e=200, key="b", evidence={"player_id": "p2"}),
            alert(e=300, key="c", severity="info"), alert(e=400, key="d", game="G2")]
    assert rule_metrics(rows, [team_game("G1"), team_game("G2")])["fatigue_high"]["duplicates"] == 0


def test_the_number_of_fouls_makes_two_foul_alerts_different_information():
    rows = [alert("foul_trouble", e=100, evidence={"player_id": "p1", "pf": 3}),
            alert("foul_trouble", e=200, key="b", evidence={"player_id": "p1", "pf": 4})]
    assert rule_metrics(rows, [team_game()])["foul_trouble"]["duplicates"] == 0


def test_follow_up_counts_and_rates_by_window():
    rows = [alert(e=100, label="seguida", delay=50), alert(e=200, key="b", label="seguida", delay=150),
            alert(e=300, key="c", label="anticipada", delay=-5), alert(e=400, key="d", label="tarde", delay=250),
            alert(e=500, key="e", label="no")]
    m = rule_metrics(rows, [team_game()])["fatigue_high"]
    assert m["actions"] == {"seguida": 2, "anticipada": 1, "tarde": 1, "no": 1}
    assert m["followed"] == {"60": 0.2, "120": 0.2, "180": 0.4}
    assert m["anticipated"] == 0.2


def test_rules_without_an_action_have_no_follow_up_numbers():
    m = rule_metrics([alert("rival_zone")], [team_game()])["rival_zone"]
    assert m["actions"] is None and m["followed"] is None and m["coverage"] is None


def test_coverage_is_the_share_of_own_timeouts_with_a_recent_alert_of_the_rule():
    rows = [alert("rival_run", e=100, s=130, label="seguida", delay=20)]
    games = [team_game(timeouts=[150, 600, 130 + 121])]      # covered: 150 (20 s after); 251 is 121 s after: not
    m = rule_metrics(rows, games, follow_s=120)["rival_run"]
    assert m["coverage"] == pytest.approx(1 / 3)


def test_the_outcome_of_followed_and_unfollowed_alerts_is_compared():
    rows = [alert("rival_run", e=100, label="seguida", delay=10, net=6), alert("rival_run", e=200, key="b", label="seguida", delay=10, net=2),
            alert("rival_run", e=300, key="c", label="no", net=-4)]
    m = rule_metrics(rows, [team_game()])["rival_run"]
    assert m["net_delta"] == pytest.approx(4 / 3)
    assert m["net_delta_by_label"] == {"seguida": 4.0, "no": -4.0}


def test_the_measure_the_rule_wants_to_move_is_averaged_before_and_after():
    measure = lambda b, a: {"name": "own_tov", "before": b, "after": a}  # noqa: E731
    rows = [alert("turnover_streak", measure=measure(4, 2)), alert("turnover_streak", e=500, key="b", measure=measure(6, 3)),
            alert("turnover_streak", e=900, key="c", measure=measure(None, None))]
    m = rule_metrics(rows, [team_game()])["turnover_streak"]["measure"]
    assert m == {"name": "own_tov", "before": 5.0, "after": 2.5, "n": 2}


def test_staff_verdicts_count_only_games_with_feedback():
    rows = [alert(e=100, feedback=True, verdict="seguida"), alert(e=200, key="b", feedback=True, verdict="descartada"),
            alert(e=300, key="c", feedback=True, verdict=None), alert(e=400, key="d", feedback=True, verdict="seguida"),
            alert(e=500, key="e")]
    m = rule_metrics(rows, [team_game()])["fatigue_high"]["verdicts"]
    assert m == {"seguida": 2, "descartada": 1, "ya_hecho": 0, "sin_respuesta": 1, "obediencia": pytest.approx(2 / 3)}
    assert rule_metrics([alert()], [team_game()])["fatigue_high"]["verdicts"] is None


def test_no_rows_or_no_games_do_not_divide_by_zero():
    assert rule_metrics([], [])["all"]["alerts"] == 0 and rule_metrics([], [])["all"]["per_team_game"] == 0
    assert rule_metrics([alert()], [])["fatigue_high"]["per_10min"] == 0
