"""What the coach did about an alert, from the finished game (issue #238).

E = game-second of the snapshot that produced the alert, S = game-second on screen when it was shown (S >= E).
The expected action depends on the rule: the named player leaves the court, the team calls a timeout, or one of the
proposed players comes in. An action counts from E - lookback (the feed delays the lines the engine saw) and is
"anticipada" if it happened by S, "seguida" within the follow window after S, "tarde" within the late window, else "no".
"""
import pytest

from src.live_core.events import Event
from src.live_prep.eval_labels import ACTION_FOR, Actions, LabelConfig, label_alert, outcome_of

OWN, RIVAL = "T1", "T2"


def ev(elapsed, kind, team=OWN, player=None, made=None, points=0, pf=None, num=None):
    return Event(num=num or int(elapsed * 10) + 1, period=1, remaining=0, elapsed=elapsed, kind=kind, team_id=team,
                 player_id=player, made=made, points=points, pf_count=pf)


def row(rule="fatigue_high", e=100, s=130, **extra):
    base = {"id": rule, "team": OWN, "elapsed": e, "shown": s, "evidence": {"player_id": "p1"}, "proposal": []}
    return {**base, **extra}


CFG = LabelConfig()


def label(rule, events, **kw):
    return label_alert(row(rule, **kw), Actions(events), CFG)


# --- player leaves the court -------------------------------------------------------------

def test_a_substitution_after_the_alert_was_shown_is_followed_with_its_delay():
    got = label("fatigue_high", [ev(180, "sub_out", player="p1")])
    assert got == {"label": "seguida", "action_at": 180, "delay": 50}


def test_a_substitution_that_happened_before_the_alert_was_on_screen_is_anticipated():
    assert label("fatigue_high", [ev(120, "sub_out", player="p1")])["label"] == "anticipada"   # E < 120 <= S
    assert label("fatigue_high", [ev(130, "sub_out", player="p1")])["label"] == "anticipada"   # exactly when shown
    assert label("foul_trouble", [ev(70, "sub_out", player="p1")])["label"] == "anticipada"    # within the lookback of E


def test_an_action_long_before_the_condition_is_not_an_answer_to_it():
    got = label("fatigue_high", [ev(30, "sub_out", player="p1")])
    assert got["label"] == "no" and got["action_at"] is None


def test_late_and_never_are_told_apart_by_the_late_window():
    assert label("fatigue_high", [ev(130 + 200, "sub_out", player="p1")])["label"] == "tarde"
    assert label("fatigue_high", [ev(130 + 400, "sub_out", player="p1")])["label"] == "no"
    assert label("fatigue_high", [])["label"] == "no"


def test_only_the_named_player_counts_and_the_first_matching_action_wins():
    events = [ev(150, "sub_out", player="p2"), ev(160, "sub_out", player="p1"), ev(300, "sub_out", player="p1")]
    assert label("foul_trouble", events) == {"label": "seguida", "action_at": 160, "delay": 30}


def test_a_substitution_forced_by_the_fifth_foul_is_not_a_decision():
    events = [ev(150, "foul", player="p1", pf=5), ev(150, "sub_out", player="p1"), ev(210, "sub_out", player="p1")]
    assert label("foul_trouble", events)["action_at"] == 210
    assert label("foul_trouble", events[:2])["label"] == "no"


# --- timeouts ----------------------------------------------------------------------------

def test_own_timeouts_answer_runs_and_turnovers_but_the_rivals_do_not():
    assert label("rival_run", [ev(150, "timeout")])["label"] == "seguida"
    assert label("turnover_streak", [ev(150, "timeout", team=RIVAL)])["label"] == "no"
    assert label("turnover_streak", [ev(110, "timeout")])["label"] == "anticipada"


# --- proposed substitutions --------------------------------------------------------------

def test_the_lever_alert_is_followed_when_one_of_the_proposed_players_comes_in():
    proposal = [{"type": "sub", "out_id": "p1", "in_id": "p8"}, {"type": "sub", "out_id": "p2", "in_id": "p9"}]
    assert label("four_factors_lever", [ev(160, "sub_in", player="p9")], proposal=proposal)["label"] == "seguida"
    assert label("four_factors_lever", [ev(160, "sub_in", player="p3")], proposal=proposal)["label"] == "no"
    assert label("four_factors_lever", [ev(160, "sub_in", player="p9", team=RIVAL)], proposal=proposal)["label"] == "no"
    assert label("four_factors_lever", [ev(160, "sub_in", player="p9")], proposal=[])["label"] == "no"


# --- rules without an action -------------------------------------------------------------

@pytest.mark.parametrize("rule", ["rival_hot_player", "rival_zone", "team_fouls_bonus", "rival_foul_trouble", "brand_new_rule"])
def test_rules_without_an_expected_action_have_no_label(rule):
    assert label(rule, [ev(150, "timeout")]) == {"label": None, "action_at": None, "delay": None}


def test_the_expected_actions_are_declared_per_rule():
    assert ACTION_FOR["foul_trouble"] == ACTION_FOR["fatigue_high"] == "sub_out"
    assert ACTION_FOR["rival_run"] == ACTION_FOR["turnover_streak"] == "timeout"
    assert ACTION_FOR["four_factors_lever"] == "proposed_sub"


def test_the_new_rules_of_the_epic_are_labelled_too():
    """#241-#243, #273: the droughts and the long run ask for a timeout, the rest alert for one of the proposed players."""
    assert ACTION_FOR["own_drought"] == ACTION_FOR["long_run"] == "timeout"
    assert ACTION_FOR["rest_starters"] == "proposed_sub"


def test_the_windows_come_from_the_config():
    tight = LabelConfig(follow_s=20, late_s=40, lookback_s=0)
    assert label_alert(row(), Actions([ev(160, "sub_out", player="p1")]), tight)["label"] == "tarde"   # 30 s after S
    assert label_alert(row(), Actions([ev(180, "sub_out", player="p1")]), tight)["label"] == "no"      # 50 s: past late_s
    assert label_alert(row(), Actions([ev(60, "sub_out", player="p1")]), tight)["label"] == "no"


# --- outcome -----------------------------------------------------------------------------

def scoring(elapsed, team, points, kind="fg2"):
    return ev(elapsed, kind, team=team, made=True, points=points)


def test_outcome_compares_the_net_points_of_the_five_minutes_after_with_the_five_before():
    events = [scoring(10 + 30 * i, RIVAL, 2) for i in range(4)] + [scoring(140 + 30 * i, OWN, 2) for i in range(4)]
    out = outcome_of(row("rival_run", s=130), Actions(events))
    assert (out["net_before"], out["net_after"], out["net_delta"]) == (-8, 8, 16)


def test_outcome_window_does_not_include_the_moment_it_was_shown():
    events = [scoring(130, OWN, 3)]  # at S: already on screen, belongs to the "before"
    out = outcome_of(row(s=130), Actions(events))
    assert (out["net_before"], out["net_after"]) == (3, 0)


def test_each_rule_adds_the_measure_it_wanted_to_move():
    events = [ev(50, "turnover"), ev(60, "turnover"), ev(70, "turnover", team=RIVAL), ev(150, "turnover")]
    assert outcome_of(row("turnover_streak", s=130), Actions(events))["measure"] == {"name": "own_tov", "before": 2, "after": 1}
    fts = [ev(40, "ft", made=True, points=1), ev(200, "ft", made=False), ev(210, "ft", made=True, points=1)]
    assert outcome_of(row("rival_foul_trouble", s=130), Actions(fts))["measure"] == {"name": "own_fta", "before": 1, "after": 2}
    rival = [scoring(50, RIVAL, 3), scoring(200, RIVAL, 2), scoring(220, RIVAL, 2)]
    assert outcome_of(row("rival_hot_player", s=130), Actions(rival))["measure"] == {"name": "rival_pts", "before": 3, "after": 4}


def test_efg_is_the_measure_of_the_lever_and_is_none_without_shots():
    shots = [ev(50, "fg2", made=True, points=2), ev(60, "fg3", made=True, points=3), ev(200, "fg2", made=False)]
    m = outcome_of(row("four_factors_lever", s=130), Actions(shots))["measure"]
    assert m["name"] == "own_efg" and m["before"] == pytest.approx(1.25) and m["after"] == 0.0
    empty = outcome_of(row("four_factors_lever", s=130), Actions([]))["measure"]
    assert empty["before"] is None and empty["after"] is None


def test_unknown_rules_only_get_the_net_points():
    assert outcome_of(row("brand_new_rule"), Actions([]))["measure"] is None


def test_actions_ignore_deleted_lines_and_keep_game_order():
    deleted = Event(num=1, period=1, remaining=0, elapsed=150, kind="timeout", team_id=OWN, deleted=True)
    actions = Actions([ev(200, "timeout"), deleted, ev(100, "timeout")])
    assert actions.timeouts(OWN) == [100, 200]
