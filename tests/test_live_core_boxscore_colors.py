"""Colours of the Boxscore tab that were missing (#699, feedback 0.5.0): the totals of the team and the advanced columns.

* The totals row of a team is coloured against the RIVAL's (what a team has no season average in the package for): ``team_totals`` gives its deviation per team (``analysis.boxscore_teams``).
* The advanced columns with a good and a bad side and a reference in the package (TS% and FTr; the rest map onto the count deviations already there) get their deviation.
"""
import pytest

from src.live_core.boxscore import build, team_totals
from src.live_core.config import RuleConfig
from tests.builders import OWN, RIVAL, Match
from tests.test_live_core_boxscore import BASELINE, at_minute

CFG = RuleConfig()


def dominated():
    """OWN scores, rebounds and steals; RIVAL loses the ball and fouls. Through the real state machine."""
    m = Match().lineup(OWN, ["p1", "p2"], at=0).lineup(RIVAL, ["r1", "r2"], at=0)
    m.score(OWN, 3, at=60, player="p1").assist(OWN, at=60, player="p2").score(OWN, 2, at=120, player="p2")
    m.turnover(RIVAL, at=180, player="r1").steal(OWN, at=180, player="p1").score(OWN, 2, at=240, player="p1")
    m.miss(RIVAL, at=300, kind="fg2", player="r2").rebound(OWN, at=301, player="p2").foul(RIVAL, "r1", at=360, drawn_by="p1")
    m.score(RIVAL, 2, at=420, player="r2").turnover(RIVAL, at=480, player="r1")
    m.period_end(1)
    return m.snapshot()


class TestTotalsAgainstTheRival:
    def test_the_team_that_does_more_of_the_good_things_is_green_and_the_other_red(self):
        totals = team_totals(dominated(), CFG)
        own, rival = totals[OWN], totals[RIVAL]
        for column in ("pts", "ast", "stl", "drb"):
            assert own[column] > 0 > rival[column], column

    def test_turnovers_and_fouls_are_inverted(self):
        totals = team_totals(dominated(), CFG)
        assert totals[RIVAL]["tov"] < 0 < totals[OWN]["tov"]
        assert totals[RIVAL]["pf"] < 0 < totals[OWN]["pf"]

    def test_the_two_are_mirrored_and_a_tie_is_neutral(self):
        totals = team_totals(dominated(), CFG)
        own, rival = totals[OWN], totals[RIVAL]
        assert all(own[c] == pytest.approx(-rival[c]) for c in own if own[c] is not None)
        tied = Match().lineup(OWN, ["p1"], at=0).lineup(RIVAL, ["r1"], at=0).score(OWN, 2, at=60, player="p1").score(RIVAL, 2, at=90, player="r1")
        assert team_totals(tied.snapshot(), CFG)[OWN]["pts"] == 0

    def test_before_anything_happens_there_is_nothing_to_compare(self):
        assert team_totals(Match().lineup(OWN, ["p1"], at=0).lineup(RIVAL, ["r1"], at=0).snapshot(), CFG)[OWN] == {}

    def test_the_entries_of_the_players_stay_only_the_players(self):
        assert set(build(dominated(), {}, CFG)) == {"p1", "p2", "r1", "r2"}

    def test_a_snapshot_that_is_not_the_state_machines_has_no_totals(self):
        assert team_totals({"teams": {OWN: {}, RIVAL: {}}, "players": {}}, CFG) == {}


class TestAdvancedDeviation:
    @pytest.mark.parametrize("column", ["ts", "ftr"])
    def test_better_than_his_usual_is_positive_and_worse_negative(self, column):
        good = build(at_minute(1200, pts=24, fg2m=8, fg2a=8, ftm=8, fta=8), {"p1": BASELINE}, CFG)["p1"]["dev"][column]
        bad = build(at_minute(1200, pts=0, fg2m=0, fg2a=8, ftm=0, fta=0), {"p1": BASELINE}, CFG)["p1"]["dev"][column]
        assert good > 0 > bad

    def test_without_attempts_there_is_no_share_to_compare(self):
        dev = build(at_minute(1200, pts=0), {"p1": BASELINE}, CFG)["p1"]["dev"]
        assert "ts" not in dev and "ftr" not in dev
