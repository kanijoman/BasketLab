"""Every column of the Boxscore tab is coloured against what the player usually does (feedback of the 0.5.2, after #699).

«Sigue habiendo campos no coloreados en el boxscore, revisar básicos y avanzados.» T2, TC, FR, +/- and Val, and the advanced Usg%, ORtg, DRtg, NetRtg, 3Pr and PIE%, had no
reference in the package. The package now carries the player's season for them (``live_prep.season_figures``) and the box score compares the game with it on the same
scale as the rest: [-1, 1] with the sign of good (DRtg inverted; Usg% and 3Pr, which have no good side, are positive above his usual). A package of before has no such
reference and those columns stay without colour, as they were. The totals row of a team gets T2, TC, FR and Val against the rival's.
"""
import pytest

from src.live_core.boxscore import build, team_totals
from src.live_core.config import RuleConfig
from tests.builders import OWN, RIVAL, Match
from tests.test_live_core_boxscore import BASELINE

CFG = RuleConfig()
SEASON = {**BASELINE, "fd_per40": 4.0, "pm_per40": 0.0, "val_per40": 12.0, "val_gross_per40": 40.0, "fg2_pct": 0.48, "fg_pct": 0.42, "min_share": 0.5,
          "adv": {"usage": 30.0, "orating": 100.0, "drating": 100.0, "net_rtg": 0.0, "three_pr": 35.0, "pie": 10.0}}
NEW_COLUMNS = ["fg2", "fg", "fd", "pm", "val", "usage", "orating", "drating", "net_rtg", "three_pr", "pie"]


def quarter():
    return Match().lineup(OWN, ["p1", "p2", "p3", "p4", "p5"], at=0).lineup(RIVAL, ["r1", "r2", "r3", "r4", "r5"], at=0)


def great():
    """p1 scores 3 of 4 threes, 2 of 2 twos and 2 of 2 free throws, draws two fouls, rebounds and steals; the rival barely scores while she is on court."""
    m = quarter()
    m.score(OWN, 3, at=30, player="p1").assist(OWN, at=30, player="p2").miss(RIVAL, at=60, player="r1").rebound(OWN, at=61, player="p1")
    m.score(OWN, 3, at=90, player="p1").miss(RIVAL, at=120, kind="fg3", player="r2").rebound(OWN, at=121, player="p2").score(OWN, 2, at=150, player="p1")
    m.turnover(RIVAL, at=180, player="r1").steal(OWN, at=180, player="p1").score(OWN, 3, at=200, player="p1")
    m.foul(RIVAL, "r1", at=240, drawn_by="p1").score(OWN, 1, at=240, player="p1").score(OWN, 1, at=241, player="p1")
    m.miss(RIVAL, at=270, player="r3").rebound(OWN, at=271, player="p1").miss(OWN, at=300, kind="fg3", player="p1").rebound(OWN, at=301, player="p3")
    m.score(OWN, 2, at=320, player="p1").assist(OWN, at=320, player="p3").score(RIVAL, 2, at=360, player="r1")
    m.foul(OWN, "p2", at=380, drawn_by="r2").score(RIVAL, 1, at=380, player="r2").miss(RIVAL, at=381, kind="ft", player="r2").rebound(OWN, at=382, player="p1")
    m.foul(RIVAL, "r2", at=400, drawn_by="p1").score(OWN, 2, at=420, player="p2").miss(RIVAL, at=450, player="r4").rebound(OWN, at=451, player="p1")
    return m.period_end(1).snapshot()


def poor():
    """p1 misses her only shot, loses a ball and fouls; her teammates take the shots and the rival scores while she is on court."""
    m = quarter()
    m.score(RIVAL, 3, at=30, player="r1").miss(OWN, at=60, player="p1").rebound(RIVAL, at=61, player="r2").score(RIVAL, 2, at=90, player="r2")
    m.turnover(OWN, at=120, player="p1").steal(RIVAL, at=120, player="r1").score(RIVAL, 2, at=130, player="r1").score(OWN, 2, at=180, player="p2")
    m.score(RIVAL, 3, at=220, player="r3").foul(OWN, "p1", at=260, drawn_by="r1").score(RIVAL, 1, at=260, player="r1").score(RIVAL, 1, at=261, player="r1")
    m.score(OWN, 2, at=300, player="p3").assist(OWN, at=300, player="p2").score(RIVAL, 2, at=340, player="r4")
    m.miss(RIVAL, at=350, player="r5").rebound(RIVAL, at=351, player="r5").score(RIVAL, 2, at=355, player="r5")     # a second chance of the rival
    m.miss(OWN, at=380, player="p2").rebound(RIVAL, at=381, player="r5").score(RIVAL, 2, at=420, player="r2")
    m.miss(RIVAL, at=440, kind="fg3", player="r3").rebound(OWN, at=441, player="p3").score(OWN, 2, at=470, player="p4")
    m.foul(RIVAL, "r3", at=490, drawn_by="p2").score(OWN, 1, at=490, player="p2").score(OWN, 1, at=491, player="p2").score(OWN, 2, at=500, player="p5")
    m.miss(OWN, at=520, player="p3").rebound(RIVAL, at=521, player="r1").score(OWN, 3, at=550, player="p4").score(OWN, 2, at=580, player="p2")
    return m.period_end(1).snapshot()


@pytest.fixture(scope="module")
def deviations():
    return {name: build(game(), {"p1": SEASON}, CFG)["p1"]["dev"] for name, game in (("great", great), ("poor", poor))}


@pytest.mark.parametrize("column", NEW_COLUMNS)
def test_a_great_game_is_above_her_usual_and_a_poor_one_below(deviations, column):
    assert deviations["great"][column] > 0 > deviations["poor"][column], column


def test_the_deviation_keeps_the_scale_of_the_rest_of_the_table(deviations):
    assert all(-1.0 <= value <= 1.0 for dev in deviations.values() for value in dev.values() if value is not None)


def test_a_package_of_before_without_her_season_leaves_those_columns_without_colour_and_the_rest_as_they_were():
    dev = build(great(), {"p1": BASELINE}, CFG)["p1"]["dev"]
    assert not set(NEW_COLUMNS) & set(dev)
    assert dev == {k: v for k, v in build(great(), {"p1": SEASON}, CFG)["p1"]["dev"].items() if k not in NEW_COLUMNS}


@pytest.mark.parametrize("column", ["fg2", "fg", "fd", "val"])
def test_the_totals_of_the_team_are_coloured_against_the_rival_in_the_new_columns_too(column):
    totals = team_totals(great(), CFG)
    assert totals[OWN][column] > 0 > totals[RIVAL][column], column
