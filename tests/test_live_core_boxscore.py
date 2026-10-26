"""The box score of the live app (issue #593): the valuation, the advanced figures of the web computed while the game is played, and how far each player is from his own average.

* The advanced figures are the ones of the web (``AdvancedStatsCalculator``, in ``live_core`` since #593) fed with a game in progress: minutes of the team = what its players
  have played, not 200 per game.
* The valuation is the one of the FEB PDF without the blocks received (decision of the user): points + rebounds + assists + steals + blocks + fouls drawn - missed shots
  - missed free throws - turnovers - fouls committed.
* ``dev`` says how far a count is from what the package says the player usually does in his minutes, in [-1, 1] with the sign of GOOD (turnovers and fouls inverted):
  expected = rate per 40 x minutes / 40, noise of a count = sqrt(expected + 1), saturating at ``boxscore_z_max`` noises.
"""
import copy
import gzip
import json
import math
from pathlib import Path

import pytest

from src.live_core.boxscore import ADVANCED_KEYS, build
from src.live_core.config import RuleConfig
from src.live_core.engine import LiveEngine
from tests.builders import OWN, RIVAL, Match

CFG = RuleConfig()


def played():
    """A match of 10 minutes in which p1 and r1 do everything, through the real state machine."""
    m = Match().lineup(OWN, ["p1", "p2"], at=0).lineup(RIVAL, ["r1", "r2"], at=0)
    m.score(OWN, 2, at=60, player="p1").assist(OWN, at=60, player="p2").miss(OWN, at=120, kind="fg3", player="p1").rebound(RIVAL, at=121, player="r2")
    m.score(RIVAL, 3, at=180, player="r1").score(OWN, 1, at=240, player="p1").miss(OWN, at=240, kind="ft", player="p1").rebound(OWN, at=241, player="p2")
    m.turnover(RIVAL, at=300, player="r1").steal(OWN, at=300, player="p2").foul(OWN, "p2", at=360, drawn_by="r1").block(OWN, at=420, player="p2")
    m.score(OWN, 2, at=480, player="p1").score(RIVAL, 2, at=540, player="r2")
    m.period_end(1)
    return m.snapshot()


class TestValuation:
    def test_it_is_the_one_of_the_pdf_without_the_blocks_received(self):
        snap = played()
        p1, p2, r1 = (build(snap, {}, CFG)[pid]["val"] for pid in ("p1", "p2", "r1"))
        # p1: 5 pts + 0 reb + 0 ast - (1 fg3 missed + 1 ft missed) - 0 tov - 0 pf ; p2: 0 pts + 1 reb + 1 ast + 1 stl + 1 blk - 1 pf ; r1: 3 pts + 0 - 1 tov + 1 foul drawn
        assert (p1, p2, r1) == (5 - 2, 1 + 1 + 1 + 1 - 1, 3 - 1 + 1)

    def test_a_player_who_did_nothing_is_zero(self):
        assert build(Match().lineup(OWN, ["p1"], at=0).snapshot(), {}, CFG)["p1"]["val"] == 0


class TestAdvancedFigures:
    def test_the_simple_ones_are_the_formulas_of_the_web(self):
        adv = build(played(), {}, CFG)["p1"]["adv"]                 # p1: fg2 2/2, fg3 0/1, ft 1/2, 5 points
        assert adv["efg"] == pytest.approx(100 * 2 / 3) and adv["ts"] == pytest.approx(100 * 5 / (2 * (3 + 0.44 * 2)))
        assert adv["ftr"] == pytest.approx(100 * 2 / 3) and adv["three_pr"] == pytest.approx(100 * 1 / 3)
        assert adv["tov_pct"] == pytest.approx(0.0)

    def test_the_minutes_of_the_team_are_what_its_players_have_played_not_two_hundred_per_game(self):
        """A game in progress: usage of a player who is on court the whole time and takes 2 of the 3 plays of his team must be 2/3, as it would be after 40 minutes."""
        m = Match().lineup(OWN, ["p1", "p2", "p3", "p4", "p5"], at=0).lineup(RIVAL, ["r1"], at=0)
        m.miss(OWN, at=100, player="p1").rebound(RIVAL, at=101, player="r1").miss(OWN, at=200, player="p1").rebound(RIVAL, at=201, player="r1").miss(OWN, at=300, player="p2").rebound(RIVAL, at=301)
        m.period_end(1)
        usage = build(m.snapshot(), {}, CFG)["p1"]["adv"]["usage"]
        assert usage == pytest.approx(100 * 2 / 3, rel=0.01)           # (2 plays x team 5 x 600 s / 5) / (600 s x 3 plays)

    def test_little_game_says_nothing(self):
        snap = copy.deepcopy(played())
        snap["players"]["p1"]["minutes"] = CFG.boxscore_min_seconds - 1
        adv = build(snap, {}, CFG)["p1"]["adv"]
        assert all(adv[k] is None for k in ADVANCED_KEYS)

    def test_a_player_who_has_not_played_has_none(self):
        snap = Match().lineup(OWN, ["p1"], at=0).lineup(RIVAL, ["r1"], at=0).snapshot()
        snap["players"]["p1"]["minutes"] = 0
        assert all(v is None for v in build(snap, {}, CFG)["p1"]["adv"].values())

    def test_shooting_percentages_without_attempts_are_none_and_not_zero(self):
        adv = build(played(), {}, CFG)["p2"]["adv"]                  # p2 never shot
        assert adv["efg"] is None and adv["ts"] is None and adv["ftr"] is None and adv["three_pr"] is None

    def test_the_impact_of_all_the_players_of_both_teams_adds_up_to_a_hundred(self):
        impact = sum(v["adv"]["pie"] for v in build(played(), {}, CFG).values() if v["adv"]["pie"] is not None)
        assert impact == pytest.approx(100.0)

    def test_it_does_not_depend_on_the_order_of_the_players(self):
        snap = played()
        flipped = {**snap, "players": dict(reversed(list(snap["players"].items())))}
        assert build(snap, {}, CFG) == build(flipped, {}, CFG)


RATES = {"orb40": 2.0, "drb40": 6.0, "ast40": 4.0, "tov40": 2.0, "stl40": 1.0, "blk40": 0.5, "fg3a40": 4.0, "fg2a40": 8.0, "usage40": 20.0, "efg": 0.5, "ftr": 0.3}
BASELINE = {"rates": RATES, "impact40": {"pts": 16.0, "orb": 2.0, "stl": 1.0, "ast": 4.0, "fg3m": 1.5, "fta": 4.0}, "pf_per40": 3.0, "ft_pct": 0.75, "seconds": 20000, "games": 10}


def at_minute(seconds, **stats):
    """p1 with ``stats`` after ``seconds`` of game."""
    snap = Match().lineup(OWN, ["p1"], at=0).lineup(RIVAL, ["r1"], at=0).snapshot()
    snap["players"]["p1"]["minutes"] = seconds
    snap["elapsed"] = seconds
    for key, value in stats.items():
        if key in ("pts", "pf"):
            snap["players"]["p1"][key] = value
        else:
            snap["players"]["p1"]["stats"][key] = value
    return snap


class TestDeviation:
    def test_what_he_does_in_his_minutes_is_zero(self):
        # 20 minutes: expected pts 8, assists 2, rebounds (orb 1 + drb 3) 4
        dev = build(at_minute(1200, pts=8, ast=2, orb=1, drb=3), {"p1": BASELINE}, CFG)["p1"]["dev"]
        assert dev["pts"] == pytest.approx(0, abs=0.05) and dev["ast"] == pytest.approx(0, abs=0.05) and dev["reb"] == pytest.approx(0, abs=0.05)

    def test_more_than_usual_is_positive_and_less_is_negative(self):
        better = build(at_minute(1200, pts=20), {"p1": BASELINE}, CFG)["p1"]["dev"]["pts"]
        worse = build(at_minute(1200, pts=0), {"p1": BASELINE}, CFG)["p1"]["dev"]["pts"]
        assert better > 0.5 > -0.5 > worse

    def test_it_saturates_at_the_limit(self):
        assert build(at_minute(1200, pts=80), {"p1": BASELINE}, CFG)["p1"]["dev"]["pts"] == 1.0
        assert build(at_minute(1200, ast=0, pts=0), {"p1": {**BASELINE, "rates": {**RATES, "ast40": 40.0}}}, CFG)["p1"]["dev"]["ast"] == -1.0

    def test_noise_is_that_of_a_count_with_a_floor(self):
        """One steal in two minutes when he usually makes 1 per 40 is not an event: the noise is sqrt(expected + 1)."""
        dev = build(at_minute(CFG.boxscore_min_seconds, stl=1), {"p1": BASELINE}, CFG)["p1"]["dev"]["stl"]
        expected = 1.0 * CFG.boxscore_min_seconds / 2400
        assert dev == pytest.approx((1 - expected) / math.sqrt(expected + 1) / CFG.boxscore_z_max)

    @pytest.mark.parametrize("key", ["tov", "pf"])
    def test_turnovers_and_fouls_are_inverted_more_than_usual_is_bad(self, key):
        dev = build(at_minute(1200, **{key: 10}), {"p1": BASELINE}, CFG)["p1"]["dev"]
        assert dev[key] < 0

    def test_free_throws_made_are_compared_with_his_percentage_of_the_season(self):
        good = build(at_minute(1200, ftm=4, fta=4), {"p1": BASELINE}, CFG)["p1"]["dev"]["ftm"]
        bad = build(at_minute(1200, ftm=0, fta=4), {"p1": BASELINE}, CFG)["p1"]["dev"]["ftm"]
        assert good > 0 > bad

    def test_effective_percentage_is_compared_with_his_own(self):
        good = build(at_minute(1200, fg2m=8, fg2a=8), {"p1": BASELINE}, CFG)["p1"]["dev"]["efg"]
        bad = build(at_minute(1200, fg2m=0, fg2a=8), {"p1": BASELINE}, CFG)["p1"]["dev"]["efg"]
        assert good > 0 > bad

    def test_a_player_without_a_baseline_has_no_deviation_at_all(self):
        dev = build(at_minute(1200, pts=20), {}, CFG)["p1"]["dev"]
        assert dev == {} or all(v is None for v in dev.values())

    def test_a_baseline_without_the_rates_is_the_same_as_none(self):
        dev = build(at_minute(1200, pts=20), {"p1": {"games": 1}}, CFG)["p1"]["dev"]
        assert dev == {} or all(v is None for v in dev.values())

    def test_before_the_minimum_of_minutes_there_is_no_deviation(self):
        dev = build(at_minute(CFG.boxscore_min_seconds - 1, pts=9), {"p1": BASELINE}, CFG)["p1"]["dev"]
        assert dev == {} or all(v is None for v in dev.values())

    def test_what_has_no_average_to_compare_with_is_never_coloured(self):
        dev = build(at_minute(1200, pts=8), {"p1": BASELINE}, CFG)["p1"]["dev"]
        assert not {"min", "pm", "fg2m", "val", "fd"} & set(dev)


class TestBothFormats:
    """FEB (a recorded match of 2ª FEB) and FBCYL (a real game through its adapter) give the same shape and the same invariants."""

    @pytest.fixture(scope="class")
    def feb(self):
        from src.live_core.recorded_feed import RecordedFeed
        feed, engine, snap = RecordedFeed.load(Path(__file__).parent / "recordings" / "2536311.rec.json.gz"), LiveEngine(), None
        for frame in feed.frames:
            snap = engine.update(feed.document_at(frame["t"]))
        return snap

    @pytest.fixture(scope="class")
    def fbcyl(self):
        from src.live_prep.fbcyl_adapter import to_feb_document
        raw = json.loads(gzip.open(Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz").read())
        return LiveEngine().update(to_feb_document(raw))

    @pytest.mark.parametrize("which", ["feb", "fbcyl"])
    def test_every_player_has_a_valuation_and_the_impact_adds_up(self, which, request):
        snap = request.getfixturevalue(which)
        box = build(snap, {}, CFG)
        assert set(box) == set(snap["players"]) and all(isinstance(v["val"], int) for v in box.values())
        # what is not a player's (rebounds and turnovers of the team) is in the impact of the game but in nobody's: a little under a hundred
        assert sum(v["adv"]["pie"] for v in box.values() if v["adv"]["pie"] is not None) == pytest.approx(100.0, abs=2.0)

    @pytest.mark.parametrize("which", ["feb", "fbcyl"])
    def test_the_figures_are_numbers_or_none_and_are_json(self, which, request):
        json.dumps(build(request.getfixturevalue(which), {}, CFG))


class TestInTheAnalysis:
    def test_the_engine_gives_it_with_the_baselines_of_both_teams(self):
        from tests.builders import engine
        snap = at_minute(1200, pts=20)
        snap["players"]["r1"]["minutes"] = 1200
        eng = engine(baselines={"p1": {**BASELINE, "z": {}}}, rival_baselines={"r1": BASELINE})
        box = eng.analyze(snap)["boxscore"]
        assert box["p1"]["dev"]["pts"] > 0 and box["r1"]["dev"]["pts"] < 0         # the rival too: its players come in ``rival_players``

    def test_without_a_package_there_is_a_box_score_and_no_deviations(self):
        from tests.builders import engine
        box = engine().analyze(played())["boxscore"]
        assert box["p1"]["val"] == 3 and box["p1"]["dev"] == {}
