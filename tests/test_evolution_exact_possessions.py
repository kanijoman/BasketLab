"""The game-by-game evolution reads the stored exact possessions and validated rebounds / turnovers (#372).

mongomock does not implement ``$dateFromString``, so the pipeline is checked structurally and the row conversion directly.
"""
from unittest.mock import MagicMock

import pytest

from src.services.evolution_service import EvolutionService


def _projection():
    coll = MagicMock()
    coll.aggregate.return_value = []
    EvolutionService(MagicMock())._evolution_feb(coll, "A")
    pipeline = coll.aggregate.call_args[0][0]
    return next(stage["$project"] for stage in pipeline if "$project" in stage and "pts" in stage["$project"])


def test_pipeline_reads_the_validated_rebounds_turnovers_and_exact_possessions():
    proj = _projection()

    for field in ("orb", "drb", "tov"):                     # own figures: derived-or-box through the match-level fields
        assert "BOXSCORE" not in str(proj[field])
    assert "DERIVED.TEAM.possessions" in str(proj["poss"]) and "DERIVED.TEAM.possessions" in str(proj["opp_poss"])


def test_possession_stats_use_the_exact_count_and_fall_back_to_the_estimate_without_it():
    service = EvolutionService(MagicMock())
    base = {"pts": 80, "fg2a": 40, "fg3a": 15, "fta": 20, "orb": 8, "tov": 10,
            "opp_pts": 70, "opp_fg2a": 40, "opp_fg3a": 15, "opp_fta": 20, "opp_orb": 6, "opp_tov": 12}
    exact = service._feb_doc_to_row({**base, "poss": 75.0, "opp_poss": 72.0})
    plain = service._feb_doc_to_row(base)

    assert service._compute_stat(exact, "possessions") == pytest.approx(75.0)
    assert service._compute_stat(exact, "offensive_rating") == pytest.approx(80 / 75.0 * 100)
    assert service._compute_stat(exact, "defensive_rating") == pytest.approx(70 / 72.0 * 100)
    assert plain["poss"] is None
    assert service._compute_stat(plain, "possessions") == pytest.approx(55 - 8 + 10 + 0.44 * 20)


def test_the_fbcyl_pipeline_reads_the_exact_possessions_too_regression():
    """#1155: Evolución FBCYL ignored ``DERIVED`` and always estimated, while the season tables of the same team read it (#432): the two pages disagreed."""
    coll = MagicMock()
    coll.aggregate.return_value = []
    EvolutionService(MagicMock())._evolution_fbcyl(coll, "1")
    pipeline = coll.aggregate.call_args[0][0]
    proj = next(stage["$project"] for stage in pipeline if "$project" in stage and "pts" in stage["$project"])

    assert "DERIVED.TEAM.possessions" in str(proj["poss"]) and "DERIVED.TEAM.possessions" in str(proj["opp_poss"])


def _row_of_the_real_game(drop_possessions=True):
    """The row Evolución reads for the real FEB sample game (the box totals of both teams), without the stored possessions: they are estimated."""
    import json
    from pathlib import Path

    sample = json.loads((Path(__file__).resolve().parents[1] / "src" / "JSON_samples" / "feb_game.json").read_text(encoding="utf-8"))
    own, rival = (t["TOTAL"] for t in sample["BOXSCORE"]["TEAM"])
    n = lambda box, key: int(float(box.get(key) or 0))  # noqa: E731
    doc = {"pts": n(own, "pts"), "fg2m": n(own, "p2m"), "fg2a": n(own, "p2a"), "fg3m": n(own, "p3m"), "fg3a": n(own, "p3a"), "ftm": n(own, "p1m"), "fta": n(own, "p1a"),
           "orb": n(own, "ro"), "drb": n(own, "rd"), "ast": n(own, "assist"), "stl": n(own, "st"), "tov": n(own, "to"), "blk": n(own, "bs"),
           "opp_pts": n(rival, "pts"), "opp_fg2a": n(rival, "p2a"), "opp_fg3a": n(rival, "p3a"), "opp_fta": n(rival, "p1a"), "opp_orb": n(rival, "ro"), "opp_drb": n(rival, "rd"),
           "opp_tov": n(rival, "to")}
    return EvolutionService._feb_doc_to_row(doc), doc


def test_the_turnover_rate_of_a_real_game_is_the_four_factors_one_regression():
    """#1153: Evolución divided the turnovers by the possessions; the Four Factors (and Multifase, Live and the consistency) by FGA + 0.44 FTA + TOV. The real sample game."""
    row, doc = _row_of_the_real_game()
    fga = doc["fg2a"] + doc["fg3a"]
    four_factors = doc["tov"] / (fga + 0.44 * doc["fta"] + doc["tov"]) * 100
    poss = fga + 0.44 * doc["fta"] + doc["tov"] - doc["orb"]

    assert EvolutionService(MagicMock())._compute_stat(row, "turnover_rate") == pytest.approx(four_factors)
    assert four_factors != pytest.approx(doc["tov"] / poss * 100)               # the old formula would not pass


def test_a_game_without_possessions_has_no_rating_instead_of_an_invented_one_regression():
    """CodeRabbit (#1198): the floor of 1 possession gave a DRtg of 0 (or an enormous ORtg) to a game whose box has no shots; the consistency says «no data» and so must Evolución."""
    service = EvolutionService(MagicMock())
    row, doc = _row_of_the_real_game()
    empty = service._feb_doc_to_row({**{k: 0 for k in doc}, "pts": 0, "opp_pts": 0})

    for stat in ("offensive_rating", "defensive_rating", "net_rating", "assist_rate", "steal_rate", "block_rate", "possessions"):
        assert service._compute_stat(empty, stat) is None, stat
    assert service._compute_stat(row, "defensive_rating") is not None
