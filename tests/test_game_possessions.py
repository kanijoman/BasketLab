"""Per-game possessions and rebounds of a FEB game, validated against its box score (#351).

Rebounds come from the play-by-play (players and teams) and are valid only if they are not fewer than the box score's
(``ro``/``rd``), checked for offensive and defensive separately; otherwise the box score value is used and flagged.
Possessions come from the tracker unless the feed is unreliable or disagrees with the estimate by more than 15 %.
"""
import pytest

from src.pbp.game_possessions import estimate_possessions, team_game_possessions


def _line(num, team, action, text, clock, player="p"):
    return {"num": str(num), "idTeam": team, "idPlayer": player, "action": action, "text": f"(X) {text}", "quarter": "1",
            "time": clock, "deleted": None}


def _box(**kw):
    base = {"p2m": 0, "p2a": 0, "p3m": 0, "p3a": 0, "p1m": 0, "p1a": 0, "ro": 0, "rd": 0, "to": 0, "pts": 0}
    base.update(kw)
    return {"TOTAL": {k: str(v) for k, v in base.items()}}


def _game(lines, a_box=None, b_box=None):
    return {"HEADER": {"TEAM": [{"id": "A", "name": "Local"}, {"id": "B", "name": "Visitante"}]},
            "BOXSCORE": {"TEAM": [{"id": "A", **_box(**(a_box or {}))}, {"id": "B", **_box(**(b_box or {}))}]},
            "PLAYBYPLAY": {"LINES": lines}}


def _clock(i):
    seconds = 590 - 10 * i
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _alternating(n, miss_then_rebound=False):
    """n made baskets alternating A, B, A, ..."""
    return [_line(i + 1, "AB"[i % 2], "shoot", "P: TIRO DE 2 ANOTADO (Puntos: 2)", _clock(i)) for i in range(n)]


# ---------------------------------------------------------------- formula

def test_estimate_possessions_uses_the_free_throw_cost_of_the_tracker():
    assert estimate_possessions(fga=60, orb=10, tov=12, fta=20) == pytest.approx(60 - 10 + 12 + 0.44 * 20)


# ---------------------------------------------------------------- rebounds validated against the box score

def _rebound_game(a_orb_player, a_orb_team, b_drb, box_ro, box_rd):
    """A misses and rebounds itself (a_orb_player players, a_orb_team team rebounds); B rebounds b_drb of A's other misses."""
    lines, n = [], 0

    def add(*a, **k):
        nonlocal n
        n += 1
        lines.append(_line(n, *a, _clock(n), **k))

    for _ in range(a_orb_player):
        add("A", "shoot", "P: TIRO DE 2 FALLADO")
        add("A", "rebound", "P: REBOTE (Rebotes: 1)")
    for _ in range(a_orb_team):
        add("A", "shoot", "P: TIRO DE 2 FALLADO")
        add("A", "rebound", "REBOTE (Rebotes: 1)", player=None)
    for _ in range(b_drb):
        add("A", "shoot", "P: TIRO DE 2 FALLADO")
        add("B", "rebound", "P: REBOTE (Rebotes: 1)")
    return _game(lines, a_box={"ro": box_ro, "p2a": a_orb_player + a_orb_team + b_drb}, b_box={"rd": box_rd})


def test_pbp_rebounds_with_team_rebounds_are_used_when_they_are_not_fewer_than_the_box_score():
    out = team_game_possessions(_rebound_game(a_orb_player=2, a_orb_team=1, b_drb=3, box_ro=2, box_rd=3))["A"]

    assert (out["orb"], out["orb_source"], out["team_orb"]) == (3, "pbp", 1)


def test_pbp_equal_to_the_box_score_is_valid():
    out = team_game_possessions(_rebound_game(a_orb_player=2, a_orb_team=0, b_drb=3, box_ro=2, box_rd=3))["A"]

    assert (out["orb"], out["orb_source"], out["team_orb"]) == (2, "pbp", 0)


def test_fewer_pbp_offensive_rebounds_than_the_box_score_fall_back_to_the_box_score_for_that_metric_only():
    game = _rebound_game(a_orb_player=2, a_orb_team=0, b_drb=3, box_ro=5, box_rd=3)
    teams = team_game_possessions(game)

    assert (teams["A"]["orb"], teams["A"]["orb_source"]) == (5, "boxscore")
    assert (teams["B"]["drb"], teams["B"]["drb_source"]) == (3, "pbp")


def test_fewer_pbp_defensive_rebounds_than_the_box_score_fall_back_to_the_box_score():
    game = _rebound_game(a_orb_player=2, a_orb_team=0, b_drb=3, box_ro=2, box_rd=7)
    teams = team_game_possessions(game)

    assert (teams["B"]["drb"], teams["B"]["drb_source"]) == (7, "boxscore")
    assert (teams["A"]["orb"], teams["A"]["orb_source"]) == (2, "pbp")


def test_turnovers_include_team_turnovers_and_fall_back_when_the_pbp_has_fewer():
    lines = [_line(1, "A", "lose", "P: PÉRDIDA (Pérdidas: 1)", "09:50"), _line(2, "A", "lose", "Equipo: PÉRDIDA (Pérdidas: 2)", "09:40", None)]

    more = team_game_possessions(_game(lines, a_box={"to": 1}))["A"]
    fewer = team_game_possessions(_game(lines, a_box={"to": 5}))["A"]

    assert (more["tov"], more["tov_source"]) == (2, "pbp") and (fewer["tov"], fewer["tov_source"]) == (5, "boxscore")


# ---------------------------------------------------------------- possessions: pbp or estimate

def test_possessions_come_from_the_pbp_when_it_is_reliable_and_agrees_with_the_estimate():
    lines = _alternating(10)
    out = team_game_possessions(_game(lines, a_box={"p2a": 5, "p2m": 5, "pts": 10}, b_box={"p2a": 5, "p2m": 5, "pts": 10}))

    assert (out["A"]["possessions"], out["A"]["possessions_source"], out["A"]["quality_level"]) == (5, "pbp", "ok")
    assert out["B"]["possessions"] == 5 and out["A"]["possessions_estimate"] == pytest.approx(5)


def test_unreliable_feed_falls_back_to_the_estimate_for_both_teams():
    """One team scores 12 times in a row: the alternation breaks and the quality level is unreliable."""
    lines = [_line(i + 1, "A", "shoot", "P: TIRO DE 2 ANOTADO (Puntos: 2)", _clock(i)) for i in range(12)]
    lines += [_line(13, "B", "shoot", "P: TIRO DE 2 ANOTADO (Puntos: 2)", _clock(12))]
    out = team_game_possessions(_game(lines, a_box={"p2a": 12, "p2m": 12}, b_box={"p2a": 13, "p2m": 13}))

    assert out["A"]["quality_level"] == "unreliable"
    assert (out["A"]["possessions_source"], out["A"]["possessions_reason"]) == ("estimate", "quality")
    assert out["B"]["possessions_source"] == "estimate" and out["A"]["possessions"] == pytest.approx(12)


def test_disagreement_with_the_estimate_above_15_percent_falls_back_to_the_estimate():
    """The pbp is complete enough to alternate but the box score says the teams shot four times more."""
    out = team_game_possessions(_game(_alternating(10), a_box={"p2a": 20, "p2m": 5}, b_box={"p2a": 20, "p2m": 5}))

    assert out["A"]["quality_level"] == "ok"
    assert (out["A"]["possessions_source"], out["A"]["possessions_reason"]) == ("estimate", "reconciliation")
    assert out["A"]["possessions"] == pytest.approx(20) and out["A"]["possessions_pbp"] == 5


def test_the_estimate_uses_the_validated_rebounds_and_turnovers():
    game = _rebound_game(a_orb_player=2, a_orb_team=2, b_drb=1, box_ro=2, box_rd=1)
    out = team_game_possessions(game)["A"]

    assert out["possessions_estimate"] == pytest.approx(estimate_possessions(fga=5, orb=4, tov=0, fta=0))


# ---------------------------------------------------------------- missing data

def test_a_game_without_pbp_or_box_score_gives_nothing():
    assert team_game_possessions({"HEADER": {"TEAM": [{"id": "A"}, {"id": "B"}]}, "BOXSCORE": {"TEAM": []}}) is None
    assert team_game_possessions(_game([])) is None


def test_fbcyl_documents_are_not_handled_yet():
    assert team_game_possessions({"moves": [{"move": "Canasta de 2"}], "stats": {"teams": []}}) is None


def test_game_minutes_count_the_overtimes():
    regulation = team_game_possessions(_game(_alternating(10), a_box={"p2a": 5}, b_box={"p2a": 5}))
    lines = _alternating(10) + [{**_line(11, "A", "shoot", "P: TIRO DE 2 ANOTADO (Puntos: 2)", "04:00"), "quarter": "5"}]
    overtime = team_game_possessions(_game(lines, a_box={"p2a": 6}, b_box={"p2a": 5}))

    assert regulation["A"]["game_minutes"] == 40 and overtime["A"]["game_minutes"] == 45
