"""The FBCYL player rows have no provisional ``usage`` and ``tov_pct`` (#1156): the radar reads the advanced figures (``usage_pct``, ``tov_pct_adv``: the formulas of Basketball
Reference, as FEB's) and ``prep_player_for_radar`` kept the provisional ones (plays per game, TO / FGA) because the key was already there."""
import json
from pathlib import Path

from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder
from src.services._scouting_formatters import prep_player_for_radar

VECTORS = Path(__file__).resolve().parent / "local_vectors" / "players_fbcyl.json"


def _keys(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from _keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _keys(inner)


def test_the_player_pipeline_does_not_define_the_provisional_fields_regression():
    stages = FBCYLPipelineBuilder.build_player_stats_pipeline()
    defined = {key for stage in stages for part in stage.values() if isinstance(part, dict) for key in part}

    assert "usage" not in defined and "tov_pct" not in defined


def test_the_player_rows_of_the_stored_answers_have_none_either_regression():
    players = [p for case in json.loads(VECTORS.read_text(encoding="utf-8"))["cases"] for p in case["players"]]

    assert players and not any("usage" in p or "tov_pct" in p for p in players)


def test_the_radar_of_an_fbcyl_player_reads_the_advanced_figures_regression():
    player = {"usage_pct": 21.4, "tov_pct_adv": 12.3, "true_shooting": 55.0}

    radar = prep_player_for_radar(player)

    assert (radar["usage"], radar["tov_pct"], radar["ts"]) == (21.4, 12.3, 55.0)
