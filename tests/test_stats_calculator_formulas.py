"""The API's calculator of one game (``StatsCalculator``, used by the weekly report) says what the registry says (#1153): its TOV% was TOV / possessions while every other page uses
TOV / (FGA + 0.44 FTA + TOV). The real sample game of FEB (box of both teams) and its estimated possessions."""
import json
from pathlib import Path

import pytest

from src.pbp.game_possessions import estimate_possessions
from src.stats.formulas import FORMULAS, evaluate
from src.stats.stats_calculator import StatsCalculator

SAMPLE = json.loads((Path(__file__).resolve().parents[1] / "src" / "JSON_samples" / "feb_game.json").read_text(encoding="utf-8"))


def _boxes():
    teams = SAMPLE["BOXSCORE"]["TEAM"]
    return teams[0]["TOTAL"], teams[1]["TOTAL"]


def _counters(team, rival):
    n = lambda box, key: float(box.get(key) or 0)  # noqa: E731
    own_fga, riv_fga = n(team, "p2a") + n(team, "p3a"), n(rival, "p2a") + n(rival, "p3a")
    return {"points": n(team, "pts"), "points_against": n(rival, "pts"), "fg2m": n(team, "p2m"), "fg2a": n(team, "p2a"), "fg3m": n(team, "p3m"), "fg3a": n(team, "p3a"),
            "fta": n(team, "p1a"), "ast": n(team, "assist"), "stl": n(team, "st"), "blk": n(team, "bs"), "tov": n(team, "to"), "orb": n(team, "ro"), "drb": n(team, "rd"),
            "opp_orb": n(rival, "ro"), "opp_drb": n(rival, "rd"),
            "poss": estimate_possessions(own_fga, n(team, "ro"), n(team, "to"), n(team, "p1a")), "opp_poss": estimate_possessions(riv_fga, n(rival, "ro"), n(rival, "to"), n(rival, "p1a"))}


def test_the_single_match_stats_say_what_the_registry_says_regression():
    team, rival = _boxes()
    stats = StatsCalculator().calculate_single_match_stats(team, rival)
    counters = _counters(team, rival)

    for name in FORMULAS:
        want = evaluate(name, counters)
        assert stats[name] == pytest.approx(0 if want is None else want, rel=1e-9), name


@pytest.mark.parametrize("name", sorted(FORMULAS))
def test_each_stat_value_says_what_the_registry_says_regression(name):
    team, rival = _boxes()
    counters = _counters(team, rival)
    want = evaluate(name, counters)

    assert StatsCalculator().calculate_stat_value(team, rival, name) == pytest.approx(0 if want is None else want, rel=1e-9)
