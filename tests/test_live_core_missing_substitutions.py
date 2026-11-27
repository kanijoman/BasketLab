"""Substitutions that the feed does not write (issue #1124, epic #1108).

FEB loses lines: a ``sub_out`` or a ``sub_in`` that never shows up leaves a team with 4 or 6 players on court. Three things went wrong silently:

* the seconds with no valid five were lost (``LineupTracker`` only credits a quintet when exactly five are on court) with nothing to say so: now each team counts them (``lineup_gap``);
* a player who had left and then acts (a shot, a rebound...) with no ``sub_in`` was never back on court, so his team stayed a man short for the rest of the match;
* the fatigue rule named players of a lineup it could not trust (6 on court after a lost ``sub_out``): it needs exactly five of the own team.
"""
from tests.builders import BASE, OWN, RIVAL, Match, _player, engine, snap

FIVE = ["a", "b", "c", "d", "e"]
RIVALS = ["v", "w", "x", "y", "z"]


def _match():
    m = Match()
    m.lineup(OWN, FIVE, at=0).lineup(RIVAL, RIVALS, at=0)
    return m


def _on_court(m, team=OWN):
    return {pid for pid, p in m.snapshot()["players"].items() if p["on_court"] and p["team_id"] == team}


def test_a_player_who_acts_after_leaving_with_no_sub_in_is_back_on_court_regression():
    """#1124: 'e' leaves at 300 s (f comes in) and scores at 600 s with no line that brings him back: he is on court again, with a stint that starts when he is first seen."""
    m = _match()
    m.substitution(OWN, "e", "f", at=300).score(OWN, 2, at=600, player="e")
    assert "e" in _on_court(m)
    player = m.snapshot()["players"]["e"]
    assert player["stint"] == 0 or player["stint"] <= 5, "the new stint starts at the line that shows him, not at the start of the game"


def test_a_late_line_of_a_player_who_already_left_does_not_bring_him_back():
    """A line logged late (earlier clock) names a player who had left by then: he was on court when it happened, and he stays out now."""
    m = _match()
    m.substitution(OWN, "e", "f", at=300).late("score", OWN, 2, at=200, player="e")
    assert "e" not in _on_court(m)


def test_an_action_a_second_after_the_sub_out_is_the_clock_of_the_substitution_not_a_lost_sub_in_regression():
    """Real game 2536311: a three-pointer 1 s after the ``sub_out`` of the shooter (the clock of a substitution is not exact) credited him the last points of the match: +7 against the
    official box score. A few seconds of grace; after them (the first test) he is back."""
    m = _match()
    m.substitution(OWN, "e", "f", at=300).score(OWN, 3, at=301, player="e")
    assert "e" not in _on_court(m)


def test_a_bench_foul_does_not_bring_a_player_on_court():
    """A foul (a technical one on the bench, for instance) says nothing about who is on court."""
    m = _match()
    m.substitution(OWN, "e", "f", at=300).foul(OWN, "e", at=400, kind="technical")
    assert "e" not in _on_court(m)


def test_the_seconds_with_no_valid_five_are_counted_per_team():
    """#1124: a ``sub_out`` with no ``sub_in`` leaves 4 on court for 120 s; the rival keeps its five."""
    m = _match()
    m._event("sub_out", OWN, 100, player_id="e")
    m.score(RIVAL, 2, at=220, player="v")
    gap = m.snapshot()["lineup_gap"]
    assert gap[OWN] == 120 and gap[RIVAL] == 0


def test_a_match_with_every_substitution_has_no_gap():
    m = _match()
    m.substitution(OWN, "e", "f", at=100).score(OWN, 2, at=300, player="f")
    assert m.snapshot()["lineup_gap"] == {OWN: 0, RIVAL: 0}


def _fatigue(on_court_own):
    players = {f"p{i}": _player(f"P{i}", OWN, stint=720 if i == 1 else 60, minutes=1100 if i == 1 else 300) for i in range(1, on_court_own + 1)}
    snapshot = snap(elapsed=1200, players=players, log=[])
    for pid in [k for k in snapshot["players"] if k.startswith("_fresh")]:      # ``snap`` completes a short five: here the number on court is the point
        del snapshot["players"][pid]
    return [a for a in engine(baselines=BASE).evaluate(snapshot) if a.id == "fatigue_high"]


def test_fatigue_needs_exactly_five_of_the_own_team_on_court_regression():
    """#1124: with six on court (a lost ``sub_out``) nobody can say who is tired; with five the alert is said as always."""
    assert len(_fatigue(5)) == 1
    assert _fatigue(6) == []


def _short_handed(bench):
    """Four own players on court (the first one tired) and ``bench``: (pf, unsportsmanlike, technical) of each own player on the bench."""
    players = {f"p{i}": _player(f"P{i}", OWN, stint=720 if i == 1 else 60, minutes=1100 if i == 1 else 300) for i in range(1, 5)}
    for i, (pf, unsports, technical) in enumerate(bench):
        players[f"b{i}"] = {**_player(f"B{i}", OWN, on_court=False, pf=pf), "unsportsmanlike": unsports, "technical": technical}
    snapshot = snap(elapsed=1200, players=players, log=[])
    for pid in [k for k in snapshot["players"] if k.startswith("_fresh")]:
        del snapshot["players"][pid]
    return [a for a in engine(baselines=BASE).evaluate(snapshot) if a.id == "fatigue_high"]


def test_a_team_that_can_only_field_four_is_still_told_who_is_tired_regression():
    """Eight inscribed and four of them out of the game (fifth foul, two technicals, one of each, ...): playing with four is legal and unusual, not a lost substitution. The
    guard of five would silence the fatigue of exactly the team that is most tired."""
    bench = [(5, 0, 0), (5, 0, 0), (2, 0, 2), (3, 1, 1)]
    assert len(_short_handed(bench)) == 1


def test_with_four_on_court_and_a_fifth_who_can_play_a_lost_substitution_is_assumed():
    assert _short_handed([(5, 0, 0), (5, 0, 0), (5, 0, 0), (4, 0, 0)]) == []      # the fourth one on the bench has four fouls: he can still play
    assert _short_handed([(5, 0, 0), (0, 0, 1)]) == []                              # one technical foul does not disqualify
