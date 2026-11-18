"""No external source is published without a reconciliation of its play-by-play against the official box (#884, D0; the common acceptance criterion of the epic).

For every team-game and statistic it counts what the play-by-play says and compares it with the box the source publishes. The NINE core statistics must match exactly or the game is **not reliable** (points, field
goals made and attempted, threes made and attempted, free throws made and attempted, offensive and defensive rebounds): it stays out of rates and percentiles and is never corrected by eye. Assists, steals, blocks,
turnovers and fouls are measured and reported by source but do not discard a game (FEB itself has known assist differences, #378); the minutes cannot be counted from the play-by-play yet and the report says so.

The tests run on the REAL game of the sample (play-by-play and box of FEB, which reconcile) and break it the way a source breaks: a line missing, a line out of order, no lines at all.
"""
import copy
import json
import random
from pathlib import Path

import pytest

from market_helpers import badged  # noqa: E402

from src.market.box_reconciliation import CORE_STATS, INFO_STATS, UNCHECKED, reconcile_game, summarize  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HOME, AWAY = "982047", "981204"             # the two teams of the real sample game


def _unwrap(node):
    if isinstance(node, dict):
        if len(node) == 1 and next(iter(node)) in ("$numberInt", "$numberLong"):
            return int(next(iter(node.values())))
        if len(node) == 1 and next(iter(node)) == "$oid":
            return next(iter(node.values()))
        return {k: _unwrap(v) for k, v in node.items()}
    return [_unwrap(v) for v in node] if isinstance(node, list) else node


@pytest.fixture(scope="module")
def sample():
    return _unwrap(json.loads((ROOT / "src" / "JSON_samples" / "feb_game.json").read_text(encoding="utf-8")))


def _drop(doc, predicate):
    """The game without the first line of the play-by-play that satisfies ``predicate`` (a source that lost it)."""
    broken = copy.deepcopy(doc)
    lines = broken["PLAYBYPLAY"]["LINES"]
    lines.remove(next(line for line in lines if predicate(line)))
    return broken


def _mismatches(result, stats=None):
    return {(c.team_id, c.stat) for c in result.mismatches(stats)}


def test_the_real_game_reconciles_on_every_core_statistic(sample):
    result = reconcile_game(sample)
    assert result.reliable and result.mismatches(CORE_STATS) == []
    assert {c.stat for c in result.checks} == set(CORE_STATS) | set(INFO_STATS)
    assert {c.team_id for c in result.checks} == {HOME, AWAY}


def test_the_real_game_has_one_difference_in_an_information_statistic_and_it_is_still_reliable(sample):
    """The play-by-play of this FEB game counts 13 turnovers of the home team and its official box 12: the kind of difference that is reported and does not discard the game."""
    result = reconcile_game(sample)
    assert [(c.team_id, c.stat, c.pbp, c.official) for c in result.mismatches()] == [(HOME, "TOV", 13, 12)] and result.reliable


def test_points_come_from_the_header_and_are_checked_against_the_shots_of_the_play_by_play(sample):
    points = {c.team_id: (c.pbp, c.official) for c in reconcile_game(sample).checks if c.stat == "PTS"}
    assert points == {HOME: (74, 74), AWAY: (56, 56)}                          # 11 + 2*15 + 3*11 and 7 + 2*11 + 3*9


def test_a_missing_made_two_makes_the_game_unreliable_and_says_which_statistics_of_which_team(sample):
    line = next(l for l in sample["PLAYBYPLAY"]["LINES"] if l.get("action") == "fgm" or "TIRO DE 2 ANOTADO" in (l.get("text") or "").upper())
    broken = _drop(sample, lambda l: l is not None and l.get("num") == line["num"])
    result = reconcile_game(broken)
    team = line["idTeam"]
    assert not result.reliable
    assert _mismatches(result, CORE_STATS) == {(team, "PTS"), (team, "FGM"), (team, "FGA")}
    pts = next(c for c in result.mismatches() if c.stat == "PTS")
    assert pts.official - pts.pbp == 2                                          # it is the two points that the line carried


def test_a_missing_missed_shot_only_breaks_the_attempts(sample):
    line = next(l for l in sample["PLAYBYPLAY"]["LINES"] if "TIRO DE 3 FALLADO" in (l.get("text") or "").upper())
    result = reconcile_game(_drop(sample, lambda l: l.get("num") == line["num"]))
    assert not result.reliable and _mismatches(result, CORE_STATS) == {(line["idTeam"], "FGA"), (line["idTeam"], "3PA")}


def test_a_difference_in_an_information_statistic_does_not_discard_the_game(sample):
    line = next(l for l in sample["PLAYBYPLAY"]["LINES"] if l.get("action") == "assist")
    result = reconcile_game(_drop(sample, lambda l: l.get("num") == line["num"]))
    assert result.reliable and result.mismatches(CORE_STATS) == []
    assert _mismatches(result) - _mismatches(reconcile_game(sample)) == {(line["idTeam"], "AST")}      # reported (the turnover of the real game was already there), not a reason to discard


def test_a_line_the_table_deleted_is_not_counted_it_is_a_correction_that_the_official_box_does_not_have(sample):
    """Data corrected late: FEB keeps a corrected line in the play-by-play marked ``deleted``. A made two that was deleted must not add points or attempts, or the game would be discarded for a shot that never was."""
    corrected = copy.deepcopy(sample)
    line = next(l for l in corrected["PLAYBYPLAY"]["LINES"] if "TIRO DE 2 ANOTADO" in (l.get("text") or "").upper())
    ghost = {**line, "num": "9999", "deleted": "1"}
    corrected["PLAYBYPLAY"]["LINES"].append(ghost)
    assert reconcile_game(corrected).checks == reconcile_game(sample).checks


def test_the_order_of_the_lines_does_not_change_the_answer(sample):
    shuffled = copy.deepcopy(sample)
    random.Random(7).shuffle(shuffled["PLAYBYPLAY"]["LINES"])
    assert reconcile_game(shuffled).checks == reconcile_game(sample).checks


def test_reconciling_twice_gives_the_same_and_does_not_touch_the_game(sample):
    before = copy.deepcopy(sample)
    assert reconcile_game(sample) == reconcile_game(sample)
    assert sample == before


def test_a_game_with_no_play_by_play_is_unreliable_on_every_core_statistic_not_an_error(sample):
    empty = copy.deepcopy(sample)
    empty["PLAYBYPLAY"]["LINES"] = []
    result = reconcile_game(empty)
    assert not result.reliable
    assert {c.stat for c in result.mismatches(CORE_STATS)} >= {"PTS", "FGM", "FGA", "ORB", "DRB"}


def test_a_game_without_the_official_box_cannot_be_reconciled(sample):
    no_box = copy.deepcopy(sample)
    no_box["BOXSCORE"]["TEAM"] = []
    with pytest.raises(ValueError, match="box"):
        reconcile_game(no_box)


@pytest.mark.parametrize("source", ["acb", "fiba", "ncaa"])
def test_a_canonical_game_reconciles_like_the_feb_one_it_comes_from(sample, source):
    result = reconcile_game(badged(sample, source))
    assert result.reliable and {c.team_id for c in result.checks} == {f"{source}:{HOME}", f"{source}:{AWAY}"}
    assert [(c.stat, c.pbp, c.official) for c in result.mismatches()] == [("TOV", 13, 12)]


def test_a_canonical_game_whose_lines_forgot_the_prefix_is_unreliable_not_silently_empty(sample):
    doc = badged(sample, "fiba")
    for line in doc["PLAYBYPLAY"]["LINES"]:
        if line.get("idTeam"):
            line["idTeam"] = line["idTeam"].split(":")[1]
    assert not reconcile_game(doc).reliable                                      # every count is zero against a real box: it shows, it does not pass


def test_the_periods_do_not_matter_the_last_quarter_written_as_an_overtime_reconciles_the_same(sample):
    """Period boundary: the same real game with its fourth quarter numbered 5 (an overtime) and the header saying so."""
    overtime = copy.deepcopy(sample)
    for line in overtime["PLAYBYPLAY"]["LINES"]:
        if str(line.get("quarter")) == "4":
            line["quarter"] = "5"
    overtime["HEADER"]["QUARTERS"]["QUARTER"].append({"n": "5", "scoreA": "0", "scoreB": "0"})
    assert reconcile_game(overtime).checks == reconcile_game(sample).checks


class TestSummary:
    def test_the_report_says_how_many_match_by_statistic_and_lists_what_does_not(self, sample):
        good, line = sample, next(l for l in sample["PLAYBYPLAY"]["LINES"] if "TIRO DE 3 FALLADO" in (l.get("text") or "").upper())
        bad = _drop(sample, lambda l: l.get("num") == line["num"])
        bad["_id"] = "bad-game"
        report = summarize([reconcile_game(good), reconcile_game(bad)])
        assert report["games"] == 2 and report["reliable"] == 1 and report["unreliable"] == ["bad-game"]
        assert report["stats"]["PTS"] == {"checked": 4, "match": 4, "mismatches": []}
        fga = report["stats"]["FGA"]
        assert (fga["checked"], fga["match"]) == (4, 3)
        assert [(m["game"], m["team"]) for m in fga["mismatches"]] == [("bad-game", line["idTeam"])]

    def test_the_report_says_what_it_could_not_check(self, sample):
        assert summarize([reconcile_game(sample)])["unchecked"] == list(UNCHECKED) == ["MIN"]

    def test_the_summary_of_nothing_is_empty_not_an_error(self):
        report = summarize([])
        assert report["games"] == 0 and report["reliable"] == 0 and report["unreliable"] == []


class TestRebounds:
    """A source that says in each rebound line whether it is offensive or defensive (FIBA's ``REBOTE OFENSIVO``) is counted by what its lines say; one that does not (FEB's ``REBOTE (Rebotes: n)``) by the rule of the
    possession tracker: offensive when the rebounding team is the one that missed the last shot. The label wins because the official box of such a source counts by the same labels, and an event written late can
    break the inference: a rebound before the missed shot it follows (#887)."""

    def _doc(self, texts, order):
        def line(num, action, text, team, player=None, made=None):
            return {"num": str(num), "quarter": "1", "time": "09:00", "idTeam": team, "idPlayer": player, "idLicense": player, "action": action, "text": text, "deleted": None, "scoreA": "0", "scoreB": "0"}
        shot = line(2, "shoot", "(A) X: TIRO DE 2 FALLADO", "a", "pa")
        rebound = line(1, "rebound", texts, "b", "pb")                 # the rebound is written BEFORE the missed shot it follows, with the same clock
        lines = [rebound, shot] if order == "late" else [shot, rebound]
        for i, item in enumerate(lines, start=1):
            item["num"] = str(i)
        box = lambda team, **extra: {"id": team, "name": team.upper(), "TOTAL": {"p1m": "0", "p1a": "0", "p2m": "0", "p2a": "1" if team == "a" else "0", "p3m": "0", "p3a": "0", **extra}, "PLAYER": []}  # noqa: E731
        return {"_id": "x", "HEADER": {"TEAM": [{"id": "a", "pts": "0"}, {"id": "b", "pts": "0"}]},
                "BOXSCORE": {"TEAM": [box("a"), box("b", rd="1", ro="0")]}, "PLAYBYPLAY": {"LINES": lines}}

    def test_a_label_in_the_line_wins_over_the_order_of_the_lines(self):
        stats = {c.stat: (c.pbp, c.official) for c in reconcile_game(self._doc("(B) Y: REBOTE DEFENSIVO", "late")).checks if c.team_id == "b"}
        assert stats["DRB"] == (1, 1) and stats["ORB"] == (0, 0)

    def test_without_a_label_the_rule_of_the_tracker_decides_as_before(self):
        stats = {c.stat: c.pbp for c in reconcile_game(self._doc("(B) Y: REBOTE (Rebotes: 1)", "in order")).checks if c.team_id == "b"}
        assert stats["DRB"] == 1 and stats["ORB"] == 0                                    # the other team missed: it is defensive
        late = {c.stat: c.pbp for c in reconcile_game(self._doc("(B) Y: REBOTE (Rebotes: 1)", "late")).checks if c.team_id == "b"}
        assert late["DRB"] == 0                                                           # and a rebound before its miss is, without a label, not counted: the case the label exists for

    def test_the_real_feb_game_is_counted_as_it_always_was(self, sample):
        result = reconcile_game(sample)
        assert result.reliable and [(c.stat, c.pbp, c.official) for c in result.mismatches()] == [("TOV", 13, 12)]
