"""``team_game_possessions`` on real FEB games (#351): the reduced pbp of the tracker fixture plus the official PDF.

For the 16 games of LF Challenge 2026-27 the official PDF gives the total rebounds (team rebounds included) and the
total turnovers: the pbp-based figures must equal them. The offensive/defensive split of team rebounds can differ by
a rebound or two from the PDF of that season, which labels some of them the other way (see the PDF evaluation).
"""
import gzip
import json
from pathlib import Path

import pytest

from src.pbp.game_possessions import team_game_possessions

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    with gzip.open(_FIXTURES / name, "rt", encoding="utf-8") if name.endswith(".gz") else open(_FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


GAMES = [g for g in _load("pbp_possessions.json.gz")["games"] if g.get("format") != "fbcyl"]
PDF = _load("feb_pdf_ground_truth.json")["games"]
_IDS = [f"{g['group']}-{g['game']}" for g in GAMES]


def _doc(game):
    return {
        "HEADER": {"TEAM": [{"id": t} for t in game["teams"]]},
        "BOXSCORE": {"TEAM": [{"id": t, "TOTAL": box} for t, box in zip(game["teams"], game["box"])]},
        "PLAYBYPLAY": {"LINES": game["lines"]},
    }


@pytest.mark.parametrize("game", GAMES, ids=_IDS)
def test_validated_rebounds_and_turnovers_are_never_fewer_than_the_box_score(game):
    teams = team_game_possessions(_doc(game))

    for tid, box in zip(game["teams"], game["box"]):
        team = teams[tid]
        assert team["orb"] >= int(box["ro"]) and team["drb"] >= int(box["rd"]) and team["tov"] >= int(box["to"])
        for metric, key in (("orb", "ro"), ("drb", "rd"), ("tov", "to")):
            if team[f"{metric}_source"] == "boxscore":
                assert team[metric] == int(box[key])


@pytest.mark.parametrize("game", [g for g in GAMES if g["group"].startswith("2026-27")], ids=lambda g: g["game"])
def test_totals_with_team_rebounds_and_turnovers_equal_the_official_pdf(game):
    teams = team_game_possessions(_doc(game))

    for pdf in PDF[game["game"]]["teams"]:
        team = teams[pdf["team_id"]]
        assert team["orb"] + team["drb"] == pdf["reb_total"]["t"], "total rebounds (team ones included)"
        assert team["tov"] == pdf["turnovers_total"], "total turnovers (team ones included)"
        assert abs(team["orb"] - pdf["reb_total"]["o"]) <= 2          # the PDF of 2026-27 mislabels some team rebounds


@pytest.mark.parametrize("game", GAMES, ids=_IDS)
def test_possessions_follow_the_reliability_of_the_game(game):
    teams = team_game_possessions(_doc(game))
    first = teams[game["teams"][0]]

    assert first["possessions_source"] == ("pbp" if first["reliable"] else "estimate")
    for team in teams.values():
        assert team["possessions_source"] == first["possessions_source"]            # both teams use the same source
        assert team["possessions"] == (team["possessions_pbp"] if team["possessions_source"] == "pbp" else team["possessions_estimate"])
        assert team["reliable"] == (team["unknown_pts_pct"] <= 10 and team["possessions_reason"] is None)


def test_the_leon_zamora_game_is_reliable_although_its_feed_has_many_alternation_breaks():
    """2524470: 10 breaks (annotation errors that need video to be solved) but only 4 % of its points have an unknown origin."""
    team = next(iter(team_game_possessions(_doc(next(g for g in GAMES if g["game"] == "2524470"))).values()))

    assert team["quality_level"] == "unreliable" and team["reliable"] is True
    assert team["unknown_pts_pct"] < 5 and team["possessions_source"] == "pbp"


def test_the_pbp_stays_close_to_the_estimate_when_it_is_used():
    ratios = [t["possessions"] / t["possessions_estimate"] for g in GAMES for t in team_game_possessions(_doc(g)).values()]

    assert 0.9 < sum(ratios) / len(ratios) < 1.1 and all(0.8 < r < 1.2 for r in ratios)
