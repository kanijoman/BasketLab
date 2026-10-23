"""Illegal lineup: at least ``formation_min_on_court`` "formación" players on court (issue #272).

The roster of the package (``tables.roster``, #271) says who is a formación player. The alert is critical, fires only
with 5 on court and after ``formation_confirm_polls`` consecutive evaluations (the feed shows substitutions ~40 s late
and a substitution is two lines), and only when the lineup is DEFINITELY wrong: a player the roster does not know
counts as formación. The recommender never proposes a change that would break the minimum; there the doubt goes the
other way, an unknown player does not count.
"""
import pytest

from live_helpers import OWN as H_OWN, RIVAL as H_RIVAL, TABLE, snap as h_snap
from src.live_core.advice import Advice, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from src.live_core.recommender import Recommender
from tests.builders import OWN, RIVAL, _player, snap

YES, NO, UNKNOWN = True, False, None


def entry(mark, team=OWN):
    return {"team_id": team, "name": "x", "formacion": mark, "birth": None, "nationality": None,
            "position": None, "dorsal": None, "height": None}


def board(on_court, bench=(), elapsed=1500, period=3):
    """A snapshot with own players p1.. (on court first, then the bench) and the roster with their marks."""
    players, roster = {}, {}
    for i, mark in enumerate(list(on_court) + list(bench), 1):
        players[f"p{i}"] = _player(f"Jug {i}", OWN, on_court=i <= len(on_court))
        roster[f"p{i}"] = entry(mark)
    return snap(elapsed=elapsed, period=period, players=players), roster


def engine(roster, **cfg):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, roster=roster, config=RuleConfig(**cfg))


def formation_alerts(eng, snapshot):
    return [a for a in eng.evaluate(snapshot) if a.id == "formation_lineup"]


def at(snapshot, seconds):
    return {**snapshot, "elapsed": snapshot["elapsed"] + seconds}


# --- the rule -----------------------------------------------------------------------------

def test_it_is_a_registered_rule():
    assert "formation_lineup" in RULE_IDS


def test_one_formacion_player_on_court_is_an_illegal_lineup_after_two_evaluations():
    s, roster = board([YES, NO, NO, NO, NO])
    eng = engine(roster)
    assert formation_alerts(eng, s) == []        # first time: it could be the middle of a substitution
    [a] = formation_alerts(eng, s)               # the same lineup on the next evaluation
    assert a.severity == "critical" and a.category == "alineacion"
    assert a.evidence["on_court_formation"] == 1 and a.evidence["minimum"] == 2
    assert "formación" in a.message and "1" in a.message and "2" in a.message
    assert "Alineación indebida de " + OWN in a.message     # it names the team (the app is not only for one club, #322)


def test_the_alert_names_the_team_from_the_snapshot():
    s, roster = board([YES, NO, NO, NO, NO])
    s["teams"][OWN]["name"] = "RECOLETAS ZAMORA"
    eng = engine(roster)
    eng.evaluate(s)
    [a] = formation_alerts(eng, s)
    assert a.message.startswith("Alineación indebida de RECOLETAS ZAMORA: solo 1 de formación")


@pytest.mark.parametrize("marks", [[YES, YES, NO, NO, NO], [YES, YES, YES, NO, NO], [YES] * 5])
def test_the_minimum_or_more_is_legal(marks):
    s, roster = board(marks)
    eng = engine(roster)
    assert formation_alerts(eng, s) == [] and formation_alerts(eng, s) == []


def test_fewer_than_five_on_court_is_a_substitution_in_progress_not_a_violation():
    s, roster = board([NO, NO, NO, NO])          # the 5th has not entered yet
    eng = engine(roster)
    assert formation_alerts(eng, s) == [] and formation_alerts(eng, s) == []


def test_a_gap_in_between_resets_the_confirmation():
    bad, roster = board([YES, NO, NO, NO, NO])
    mid, _ = board([YES, NO, NO, NO])
    eng = engine(roster)
    assert formation_alerts(eng, bad) == [] and formation_alerts(eng, mid) == [] and formation_alerts(eng, bad) == []
    assert len(formation_alerts(eng, bad)) == 1  # only now two in a row


@pytest.mark.parametrize("marks", [
    [YES, UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN],   # 1 + 4 unknown
    [NO, NO, NO, YES, UNKNOWN],                  # 1 + 1 unknown
    [NO, NO, UNKNOWN, UNKNOWN, NO],              # 0 + 2 unknown
])
def test_players_the_roster_does_not_know_get_the_benefit_of_the_doubt(marks):
    s, roster = board(marks)
    eng = engine(roster)
    assert formation_alerts(eng, s) == [] and formation_alerts(eng, s) == []


def test_it_fires_when_even_the_unknown_players_could_not_reach_the_minimum():
    s, roster = board([NO, NO, NO, NO, UNKNOWN])
    eng = engine(roster)
    formation_alerts(eng, s)
    [a] = formation_alerts(eng, s)
    assert a.evidence["on_court_formation"] == 0 and a.evidence["unknown"] == 1


def test_a_player_missing_from_the_roster_is_unknown_too():
    s, roster = board([YES, NO, NO, NO, NO])
    for pid in ("p2", "p3", "p4", "p5"):
        del roster[pid]
    eng = engine(roster)
    assert formation_alerts(eng, s) == [] and formation_alerts(eng, s) == []


def test_without_the_roster_of_our_team_the_rule_is_off():
    s, _ = board([NO] * 5)
    for roster in (None, {}, {"zz": entry(NO, team="OTHER")}):
        eng = engine(roster)
        assert formation_alerts(eng, s) == [] and formation_alerts(eng, s) == []


def test_the_minimum_is_configurable_and_zero_switches_it_off():
    s, roster = board([YES, YES, NO, NO, NO])
    off, strict = engine(roster, formation_min_on_court=0), engine(roster, formation_min_on_court=3)
    assert formation_alerts(off, s) == [] and formation_alerts(off, s) == []
    formation_alerts(strict, s)
    assert formation_alerts(strict, s)[0].evidence["minimum"] == 3


def test_the_confirmation_polls_are_configurable():
    s, roster = board([NO] * 5)
    assert len(formation_alerts(engine(roster, formation_confirm_polls=1), s)) == 1


def test_the_rival_roster_entries_do_not_count():
    s, roster = board([YES, YES, NO, NO, NO])
    roster["r1"] = entry(NO, team=RIVAL)
    s["players"]["r1"] = _player("Rival", RIVAL, on_court=True)
    eng = engine(roster)
    assert formation_alerts(eng, s) == [] and formation_alerts(eng, s) == []


def test_the_same_lineup_is_said_again_only_after_the_rearm_interval():
    s, roster = board([NO] * 5)
    eng = engine(roster)
    formation_alerts(eng, s)
    [first] = formation_alerts(eng, s)
    assert first.key == "formation:p1-p2-p3-p4-p5"
    assert formation_alerts(eng, at(s, 60)) == []             # a minute later: it was said
    [again] = formation_alerts(eng, at(s, 200))               # the staff has not fixed it
    assert again.key == "formation:p1-p2-p3-p4-p5#2"


def test_a_different_illegal_lineup_is_a_new_alert():
    s, roster = board([NO] * 5, bench=[NO])
    eng = engine(roster)
    formation_alerts(eng, s)
    assert len(formation_alerts(eng, s)) == 1
    other = {**s, "players": {**s["players"], "p5": {**s["players"]["p5"], "on_court": False},
                              "p6": {**s["players"]["p6"], "on_court": True}}}
    formation_alerts(eng, other)
    [a] = formation_alerts(eng, other)
    assert a.key == "formation:p1-p2-p3-p4-p6"


def test_the_game_phase_does_not_change_it():
    s, roster = board([NO] * 5, elapsed=2300, period=4)
    s["remaining"], s["score"] = 100, {OWN: 80, RIVAL: 40}     # a decided game
    [a] = formation_alerts(engine(roster, formation_confirm_polls=1), s)
    assert a.severity == "critical"


# --- generic confirmation in the engine -----------------------------------------------------

def test_an_alert_that_asks_for_confirmation_needs_that_many_consecutive_evaluations(monkeypatch):
    rule = lambda snapshot, ctx: [Advice(key="k", id="fake", severity="info", category="rival", message="m", confirm=3)]  # noqa: E731
    monkeypatch.setattr("src.live_core.advice.RULES", [("fake", rule)])
    eng = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    s = snap()
    assert [eng.evaluate(s), eng.evaluate(s)] == [[], []]
    assert [a.key for a in eng.evaluate(s)] == ["k"]
    assert eng.evaluate(s) == []                               # said once


def test_a_gap_resets_the_count_and_a_default_alert_is_not_delayed(monkeypatch):
    present = {"on": True}
    slow = lambda snapshot, ctx: ([Advice(key="slow", id="slow", severity="info", category="rival", message="m", confirm=2)]  # noqa: E731
                                  if present["on"] else [])
    fast = lambda snapshot, ctx: [Advice(key="fast", id="fast", severity="info", category="rival", message="m")]  # noqa: E731
    monkeypatch.setattr("src.live_core.advice.RULES", [("slow", slow), ("fast", fast)])
    eng = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    s = snap()
    assert [a.key for a in eng.evaluate(s)] == ["fast"]        # confirm = 1 by default: immediate
    present["on"] = False
    eng.evaluate(s)
    present["on"] = True
    assert eng.evaluate(s) == [] and [a.key for a in eng.evaluate(s)] == ["slow"]


# --- the recommender ---------------------------------------------------------------------

def rec_snap():
    return h_snap(period=2, elapsed=900)          # on court: g1, w1, w2, b1, g3


def rec_roster(**marks):
    return {pid: entry(marks.get(pid, NO), team=H_OWN) for pid in TABLE}


def recommender(roster, **cfg):
    return Recommender(H_OWN, TABLE, RuleConfig(**cfg), roster=roster)


def ins(proposals):
    return [p["in_id"] for p in proposals]


def test_without_a_roster_the_proposals_are_what_they_were_and_carry_no_formation_data():
    plain = Recommender(H_OWN, TABLE).suggest_swaps(rec_snap(), "g1")
    assert plain and all("formation_after" not in p for p in plain)
    assert ins(recommender(None).suggest_swaps(rec_snap(), "g1")) == ins(plain)


def test_a_swap_that_would_leave_fewer_than_the_minimum_is_never_proposed():
    roster = rec_roster(g1=YES, w1=YES)           # exactly two on court (g1, w1); the bench guard g2 is not formación
    assert "g2" in ins(Recommender(H_OWN, TABLE).suggest_swaps(rec_snap(), "g1")), "it is a candidate without the rule"
    assert "g2" not in ins(recommender(roster).suggest_swaps(rec_snap(), "g1"))


def test_a_formacion_replacement_keeps_the_lineup_legal_and_says_how_many_remain():
    roster = rec_roster(g1=YES, w1=YES, g2=YES)
    [first, *_] = recommender(roster).suggest_swaps(rec_snap(), "g1")
    assert first["in_id"] == "g2" and first["formation_after"] == 2 and first["formation_ok"] is True
    assert "2 de formación" in first["message"] and "mínimo" in first["message"]


def test_swapping_a_player_who_is_not_formacion_is_free():
    roster = rec_roster(g1=YES, w1=YES)
    props = recommender(roster).suggest_swaps(rec_snap(), "b1")
    assert props and all(p["formation_after"] == 2 for p in props)


def test_a_lineup_that_is_already_illegal_may_stay_as_it_is_or_improve_never_get_worse():
    roster = rec_roster(g1=YES, g2=YES)           # one formación player on court (g1): already below two
    from_formacion = recommender(roster).suggest_swaps(rec_snap(), "g1")
    assert "g2" in ins(from_formacion) and set(ins(from_formacion)) <= {"g2"}   # any non-formación would leave 0
    assert all(p["formation_after"] == 1 and p["formation_ok"] is False for p in from_formacion)
    from_other = recommender(roster).suggest_swaps(rec_snap(), "b1")
    assert from_other and all(p["formation_after"] >= 1 for p in from_other)


def test_for_the_constraint_a_player_the_roster_does_not_know_does_not_count():
    roster = rec_roster(g1=YES, w1=YES, g2=UNKNOWN)
    assert "g2" not in ins(recommender(roster).suggest_swaps(rec_snap(), "g1"))


def test_the_constraint_follows_the_configured_minimum_and_zero_disables_it():
    roster = rec_roster(g1=YES, w1=YES)
    assert "g2" in ins(recommender(roster, formation_min_on_court=0).suggest_swaps(rec_snap(), "g1"))
    assert "g2" not in ins(recommender(roster, formation_min_on_court=2).suggest_swaps(rec_snap(), "g1"))
    assert "g2" in ins(recommender(roster, formation_min_on_court=1).suggest_swaps(rec_snap(), "g1"))


def test_without_the_roster_of_our_team_the_constraint_is_off():
    other = {"zz": entry(NO, team="OTHER")}
    assert ins(recommender(other).suggest_swaps(rec_snap(), "g1")) == ins(Recommender(H_OWN, TABLE).suggest_swaps(rec_snap(), "g1"))


# --- alerts that name a formacion player --------------------------------------------------

def foul_alert(roster, who):
    s = h_snap(period=2, elapsed=900, overrides={who: {"pf": 3}})
    eng = AdviceEngine(own_team_id=H_OWN, rival_team_id=H_RIVAL, baselines=TABLE, roster=roster)
    [alert] = [a for a in eng.evaluate(s) if a.id == "foul_trouble"]
    return alert


def test_an_alert_for_a_formacion_player_says_that_without_them_the_lineup_is_at_the_minimum():
    alert = foul_alert(rec_roster(g1=YES, w1=YES), "g1")
    assert "de formación" in alert.message and "mínimo" in alert.message
    assert alert.proposal == [], "every candidate would leave the lineup illegal"


def test_the_note_is_not_added_when_there_is_room_or_the_player_is_not_formacion():
    assert "mínimo" not in foul_alert(rec_roster(g1=YES, w1=YES, w2=YES), "g1").message
    assert "mínimo" not in foul_alert(rec_roster(g1=YES, w1=YES), "b1").message


# --- analysis for the app ----------------------------------------------------------------

def test_the_analysis_tells_the_app_how_many_formacion_players_are_on_court():
    s, roster = board([YES, NO, YES, NO, NO])
    assert engine(roster).analyze(s)["formation"] == {"min": 2, "known": True, "on_court": 2, "unknown": 0, "players": 5, "rival": {"known": False, "on_court": None, "unknown": 0, "players": 0}}


def test_the_analysis_says_when_the_roster_is_unknown_so_the_app_can_warn():
    s, _ = board([NO] * 5)
    assert engine(None).analyze(s)["formation"] == {"min": 2, "known": False, "on_court": None, "unknown": 0, "players": 5, "rival": {"known": False, "on_court": None, "unknown": 0, "players": 0}}


def test_the_analysis_has_nothing_to_say_when_the_rule_is_switched_off():
    s, roster = board([NO] * 5)
    assert "formation" not in engine(roster, formation_min_on_court=0).analyze(s)
    assert "formation" not in AdviceEngine(own_team_id=None).analyze(s)


# --- on the real match ---------------------------------------------------------------------

def _leon_alerts(tmp_rule_config=None):
    """Zamora - Leon replayed through the app's session, with Leon's FEB roster (the two players who are NOT formación)."""
    import dataclasses as dc
    from pathlib import Path

    from src.live_core.package import PreparationPackage
    from src.live_core.session import LiveSession

    recordings = Path(__file__).parent / "recordings"
    package = PreparationPackage.loads((recordings / "2524470.package.json").read_text(encoding="utf-8"))
    not_formacion = {"2651124", "2892632"}            # Boquete and Castro in the real roster of 13/10/2026
    own = package.team["id"]
    roster = {pid: entry(pid not in not_formacion, team=own) for pid in package.tables["players"]}
    package = dc.replace(package, tables={**package.tables, "roster": roster},
                         rule_config={**package.rule_config, **(tmp_rule_config or {})})
    session = LiveSession(package.dumps())
    session.load_recording((recordings / "2524470.rec.json.gz").read_bytes())
    alerts = []
    for t in range(0, 7200, 20):
        result = session.play(t)
        if result["output"]:
            alerts += [a for a in result["output"]["alerts"] if a["id"] == "formation_lineup"]
    return alerts, not_formacion


def test_the_real_match_gives_no_false_alarm_with_the_real_minimum():
    alerts, _ = _leon_alerts()
    assert alerts == [], "Leon always had at least 3 formación players on court"


def test_with_a_stricter_minimum_it_fires_only_when_both_players_who_are_not_formacion_are_on_court():
    alerts, not_formacion = _leon_alerts({"formation_min_on_court": 4})
    assert alerts, "with 4 required, the two of them together on court is a violation"
    for a in alerts:
        assert a["severity"] == "critical" and a["evidence"]["on_court_formation"] == 3
        assert not_formacion <= set(a["evidence"]["lineup"])


# --- the rival too (issue #322): the rule is about BOTH teams -------------------------------------------------------

def rival_board(own_marks, rival_marks, elapsed=1500, period=3):
    """Both teams on court: own players p1.., rival players r1.., and a roster that has both."""
    players, roster = {}, {}
    for i, mark in enumerate(own_marks, 1):
        players[f"p{i}"] = _player(f"Jug {i}", OWN, on_court=True)
        roster[f"p{i}"] = entry(mark, OWN)
    for i, mark in enumerate(rival_marks, 1):
        players[f"r{i}"] = _player(f"Rival {i}", RIVAL, on_court=True)
        roster[f"r{i}"] = entry(mark, RIVAL)
    return snap(elapsed=elapsed, period=period, players=players), roster


def lineup_alerts(eng, snapshot):
    return [a for a in eng.evaluate(snapshot) if a.id in ("formation_lineup", "rival_formation_lineup")]


def test_the_rival_in_an_illegal_lineup_is_a_critical_alert_too():
    s, roster = rival_board([YES, YES, NO, NO, NO], [YES, NO, NO, NO, NO])
    eng = engine(roster)
    assert lineup_alerts(eng, s) == []                    # confirmed after two evaluations, like ours
    [a] = lineup_alerts(eng, s)
    assert a.id == "rival_formation_lineup" and a.severity == "critical" and a.category == "alineacion"
    assert "Alineación indebida de " + RIVAL in a.message and "1" in a.message and "2" in a.message
    assert "Valorar avisar a la mesa" in a.message         # what to do differs: it is not our lineup to fix
    assert a.evidence["team_id"] == RIVAL and a.evidence["on_court_formation"] == 1 and a.evidence["minimum"] == 2


def test_each_team_gets_its_own_alert_and_a_legal_team_none():
    s, roster = rival_board([YES, NO, NO, NO, NO], [YES, NO, NO, NO, NO])
    eng = engine(roster)
    lineup_alerts(eng, s)
    both = lineup_alerts(eng, s)
    assert sorted(a.id for a in both) == ["formation_lineup", "rival_formation_lineup"]
    own_only, roster2 = rival_board([YES, NO, NO, NO, NO], [YES, YES, NO, NO, NO])
    eng2 = engine(roster2)
    lineup_alerts(eng2, own_only)
    assert [a.id for a in lineup_alerts(eng2, own_only)] == ["formation_lineup"]


def test_the_rival_is_only_watched_when_the_roster_has_its_players():
    s, roster = rival_board([YES, YES, NO, NO, NO], [NO] * 5)
    own_roster_only = {k: v for k, v in roster.items() if v["team_id"] == OWN}
    eng = engine(own_roster_only)
    lineup_alerts(eng, s)
    assert lineup_alerts(eng, s) == []                    # no roster of the rival: nothing is said about it


def test_the_doubt_about_the_rival_also_goes_in_its_favour():
    s, roster = rival_board([YES, YES, NO, NO, NO], [YES, UNKNOWN, UNKNOWN, NO, NO])
    eng = engine(roster)
    lineup_alerts(eng, s)
    assert lineup_alerts(eng, s) == []                    # two players the roster does not settle count as formación


def test_the_rival_alert_has_its_own_key_and_does_not_hide_ours():
    s, roster = rival_board([YES, NO, NO, NO, NO], [YES, NO, NO, NO, NO])
    eng = engine(roster)
    lineup_alerts(eng, s)
    keys = [a.key for a in lineup_alerts(eng, s)]
    assert len(set(keys)) == 2 and any(k.startswith("rival_formation:") for k in keys)


def test_the_rival_alert_survives_a_decided_game():
    from src.live_core.game_context import kept_when_decided

    s, roster = rival_board([YES, YES, NO, NO, NO], [YES, NO, NO, NO, NO])
    eng = engine(roster)
    lineup_alerts(eng, s)
    [a] = lineup_alerts(eng, s)
    assert kept_when_decided(a)


def test_the_analysis_says_for_both_teams_whether_they_are_watched():
    s, roster = rival_board([YES, YES, NO, NO, NO], [NO] * 5)
    analysis = engine(roster).analyze(s)["formation"]
    assert analysis["known"] is True and analysis["rival"]["known"] is True
    assert analysis["rival"]["on_court"] == 0
    only_own = {k: v for k, v in roster.items() if v["team_id"] == OWN}
    assert engine(only_own).analyze(s)["formation"]["rival"]["known"] is False
