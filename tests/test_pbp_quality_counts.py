"""Per-team counts of the play-by-play used to audit it against the box score (#350).

The rebound rule is the tracker's: offensive when the rebounding team is the one that missed. The official FEB box
score does not credit team rebounds (lines without a player), so they are not counted here for FEB.
"""
import pytest

from src.pbp.possession_core import count_quality_pbp_metrics


def _line(num, team, action, text, clock="09:00", player="p"):
    return {"num": str(num), "idTeam": team, "idPlayer": player, "action": action, "text": f"(X) {text}", "quarter": "1", "time": clock}


def _count(*lines):
    game = {"PLAYBYPLAY": {"LINES": list(lines)}}
    return count_quality_pbp_metrics(game, False, ["A", "B"])


def test_shots_and_free_throws_are_counted_by_kind():
    counts = _count(
        _line(1, "A", "shoot", "P: TIRO DE 2 ANOTADO (Puntos: 2)", "09:50"),
        _line(2, "A", "shoot", "P: TIRO DE 2 FALLADO", "09:40"),
        _line(3, "A", "shoot", "P: TIRO DE 3 ANOTADO (Puntos: 5)", "09:30"),
        _line(4, "A", "shoot", "P: MATE ANOTADO (Puntos: 7)", "09:20"),
        _line(5, "A", "fthrow", "P: TIRO DE 1 ANOTADO (Puntos: 8)", "09:10"),
        _line(6, "A", "fthrow", "P: TIRO DE 1 FALLADO", "09:10"),
    )["A"]

    assert (counts["T2M"], counts["T2A"], counts["T3M"], counts["T3A"], counts["T1M"], counts["T1A"]) == (2, 3, 1, 1, 1, 2)


def test_rebound_of_the_team_that_missed_is_offensive_and_of_the_rival_defensive():
    counts = _count(
        _line(1, "A", "shoot", "P: TIRO DE 2 FALLADO", "09:50"),
        _line(2, "A", "rebound", "P: REBOTE (Rebotes: 1)", "09:49"),
        _line(3, "A", "shoot", "P: TIRO DE 3 FALLADO", "09:40"),
        _line(4, "B", "rebound", "P: REBOTE (Rebotes: 1)", "09:39", player="q"),
    )

    assert (counts["A"]["RebO"], counts["A"]["RebD"], counts["B"]["RebO"], counts["B"]["RebD"]) == (1, 0, 0, 1)


def test_rebound_after_a_missed_free_throw_follows_the_same_rule():
    counts = _count(
        _line(1, "A", "fthrow", "P: TIRO DE 1 FALLADO", "09:50"),
        _line(2, "A", "rebound", "P: REBOTE (Rebotes: 1)", "09:50"),
    )

    assert counts["A"]["RebO"] == 1


def test_team_rebounds_are_not_counted_for_feb_because_the_box_score_does_not_credit_them():
    counts = _count(
        _line(1, "A", "shoot", "P: TIRO DE 2 FALLADO", "09:50"),
        _line(2, "B", "rebound", "REBOTE (Rebotes: 5)", "09:49", player=None),
    )

    assert counts["B"]["RebD"] == 0


def test_rebound_without_a_missed_shot_is_not_counted():
    assert _count(_line(1, "A", "rebound", "P: REBOTE (Rebotes: 1)"))["A"]["RebO"] == 0


def test_all_turnovers_are_counted_including_team_turnovers():
    counts = _count(
        _line(1, "A", "lose", "P: PÉRDIDA (Pérdidas: 1)", "09:50"),
        _line(2, "A", "lose", "Equipo: PÉRDIDA (Pérdidas: 2)", "09:40", player=None),
    )

    assert counts["A"]["TOV"] == 2


def test_fbcyl_uses_the_labels_of_the_feed_for_rebounds_and_counts_the_clock_remaining():
    def move(text, team, **kw):
        return {"idTeam": team, "actorId": 7, "move": text, "period": 1, "min": 9, "sec": 50, **kw}

    game = {"moves": [move("Intento fallado de 2", 10), move("Rebote ofensivo", 10, sec=49), move("Intento fallado de 3", 10, sec=40),
                      move("Rebote defensivo", 11, sec=39), move("Pérdida", 11, sec=30)]}

    counts = count_quality_pbp_metrics(game, True, ["10", "11"])

    assert (counts["10"]["RebO"], counts["10"]["T2A"], counts["10"]["T3A"], counts["11"]["RebD"], counts["11"]["TOV"]) == (1, 1, 1, 1, 1)


def test_unknown_teams_are_ignored():
    counts = _count(_line(1, "Z", "shoot", "P: TIRO DE 2 ANOTADO (Puntos: 2)"))

    assert counts["A"]["T2M"] == counts["B"]["T2M"] == 0
