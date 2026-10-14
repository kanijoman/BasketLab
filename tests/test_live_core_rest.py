"""Rest for the key players in a decided game (issue #273).

Phase ``decided`` (|margin| >= 20 with less than 8:00 left of the 4th): the important players (many minutes on average
and today) are proposed to rest, and the players with the lowest profile (fewest minutes today, then on average) come in.
Winning: a warning. Losing: the same proposal as information, with another text. One alert per important player.
"""
import pytest

from live_helpers import OWN, RIVAL, TABLE, snap
from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig

MIN = 60


def decided(margin=22, minutes=None, overrides=None, period=4, remaining=300):
    """A decided game: on court g1, w1, w2, b1, g3 with the given minutes (seconds) played today."""
    s = snap(period=period, elapsed=2300, overrides=overrides)
    s["remaining"] = remaining
    s["score"] = {OWN: 80 + max(margin, 0), RIVAL: 80 + max(-margin, 0)}
    for pid, seconds in {"g1": 28 * MIN, "w1": 26 * MIN, "w2": 12 * MIN, "b1": 27 * MIN, "g3": 14 * MIN,
                         **(minutes or {})}.items():
        s["players"][pid]["minutes"] = seconds
    return s


def engine(roster=None, config=None):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, roster=roster, config=config)


def rest(advices):
    return [a for a in advices if a.id == "rest_starters"]


def test_the_rule_is_registered_and_can_be_switched_off():
    assert "rest_starters" in RULE_IDS and "rest_starters" in [rid for rid, _ in RULES]
    assert rest(engine(config=RuleConfig(rules_off=("rest_starters",))).evaluate(decided())) == []


@pytest.mark.parametrize("margin, remaining, period", [(15, 300, 4), (22, 600, 4), (22, 300, 3), (3, 100, 4)])
def test_nothing_is_proposed_unless_the_game_is_decided(margin, remaining, period):
    assert rest(engine().evaluate(decided(margin=margin, remaining=remaining, period=period))) == []


def test_it_needs_the_game_context():
    cfg = RuleConfig(rules_off=("game_context",))
    assert rest(engine(config=cfg).evaluate(decided())) == []


def test_winning_proposes_resting_each_important_player_and_giving_minutes_to_the_lowest_profiles():
    alerts = rest(engine().evaluate(decided()))
    assert sorted(a.evidence["player_id"] for a in alerts) == ["b1", "g1", "w1"]   # avg >= 20 min and >= 10 min today
    assert all(a.severity == "warning" and a.category == "descanso" for a in alerts)
    first = next(a for a in alerts if a.evidence["player_id"] == "g1")             # the one with most minutes today
    assert first.proposal[0]["type"] == "sub" and first.proposal[0]["out_id"] == "g1"
    assert first.proposal[0]["in_id"] in ("g2", "b2", "b3")
    assert "Guard Uno" in first.message and "+22" in first.message
    assert "descansa" in first.message.lower() and first.proposal[0]["in_name"] in first.message


def test_the_players_who_come_in_are_different_for_each_alert():
    alerts = rest(engine().evaluate(decided()))
    ins = [a.proposal[0]["in_id"] for a in alerts]
    assert len(ins) == len(set(ins)) == 3


def test_whoever_has_not_played_comes_in_first_then_the_one_with_fewest_minutes_then_the_lowest_average():
    s = decided(overrides={"g2": {"minutes": 0}, "b2": {"minutes": 0}, "b3": {"minutes": 3 * MIN}})
    alerts = rest(engine().evaluate(s))
    by_out = {a.evidence["player_id"]: a for a in alerts}
    # most minutes today first: g1 gets the first pick among the two who have not played; the lowest average (b2, 1000) before g2 (1200)
    assert by_out["g1"].proposal[0]["in_id"] == "b2"
    assert by_out["b1"].proposal[0]["in_id"] == "g2"
    assert by_out["w1"].proposal[0]["in_id"] == "b3"


def test_someone_with_few_minutes_today_is_not_important_however_much_he_plays_on_average():
    s = decided(minutes={"w1": 4 * MIN})
    assert "w1" not in [a.evidence["player_id"] for a in rest(engine().evaluate(s))]


def test_someone_with_a_low_average_is_not_important_however_much_he_has_played_today():
    s = decided(minutes={"w2": 30 * MIN})   # avg 15 min
    assert "w2" not in [a.evidence["player_id"] for a in rest(engine().evaluate(s))]


def test_only_a_player_who_has_played_less_and_averages_less_comes_in():
    s = decided(minutes={"b2": 40 * MIN})   # more minutes today than any of the important players
    ins = [p["in_id"] for a in rest(engine().evaluate(s)) for p in a.proposal]
    assert "b2" not in ins


def test_players_in_foul_trouble_or_fouled_out_do_not_come_in():
    s = decided(overrides={"g2": {"pf": 5}, "b2": {"pf": 4}})
    ins = [p["in_id"] for a in rest(engine().evaluate(s)) for p in a.proposal]
    assert "g2" not in ins and "b2" not in ins and "b3" in ins


def test_without_anyone_available_to_come_in_nothing_is_proposed():
    s = decided(overrides={pid: {"pf": 5} for pid in ("g2", "b2", "b3")})
    assert rest(engine().evaluate(s)) == []


def test_losing_it_is_information_with_another_text_and_the_same_proposal():
    win = {a.evidence["player_id"]: a for a in rest(engine().evaluate(decided(margin=22)))}
    lose = {a.evidence["player_id"]: a for a in rest(engine().evaluate(decided(margin=-22)))}
    assert set(lose) == set(win)
    for pid, alert in lose.items():
        assert alert.severity == "info" and alert.category == "descanso"
        assert alert.message != win[pid].message and "-22" in alert.message
        assert alert.proposal == win[pid].proposal


def test_each_important_player_is_said_once_per_game():
    e = engine()
    assert len(rest(e.evaluate(decided()))) == 3
    assert rest(e.evaluate(decided(minutes={"g1": 29 * MIN}))) == []


def test_without_baselines_there_is_nobody_to_propose():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    assert rest(e.evaluate(decided())) == []


def test_it_does_not_leave_fewer_formation_players_on_court_than_the_minimum():
    roster = {pid: {"team_id": OWN, "formacion": pid in ("g1", "w1", "g2")} for pid in TABLE}
    alerts = {a.evidence["player_id"]: a for a in rest(engine(roster=roster).evaluate(decided()))}
    # g1 and w1 are the only formación players on court and the minimum is 2: they may only be replaced by one (g2)
    assert [p["in_id"] for p in alerts["g1"].proposal] == ["g2"]
    assert "w1" not in alerts                       # g2 is already taken by g1 and nobody else of formación is left
    assert alerts["b1"].proposal[0]["in_id"] in ("b2", "b3")


def test_the_alert_is_json_serialisable_and_survives_the_phase_adjustment():
    import json
    [alert, *_] = rest(engine().evaluate(decided()))
    assert json.loads(json.dumps(alert.proposal)) == alert.proposal
    assert "~" not in alert.key and alert.key.startswith("rest:")
