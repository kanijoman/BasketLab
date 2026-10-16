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
