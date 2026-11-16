"""The study of the pace of each team by its possessions (#938): ``scripts/pace_style_study.py``.

From the published per-possession CSV (the duration, the origin and the end of every possession of every game with play-by-play): how the duration and the origin of a possession go with what
it scores (the groundwork of the causal study, #942: a fast possession after a made basket is chosen, after a steal it is given), and whether the style of a team (how long its possessions
last, how many are fast, what each kind scores) is its own: the same in its odd and its even games. Tested on the CSV the publisher makes of a REAL game.
"""
import copy
import csv
import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pace_style_study as study  # noqa: E402
from src.local_data.possessions_export import export_possession_csv  # noqa: E402

SAMPLE = ROOT / "src" / "JSON_samples" / "feb_game.json"
LF2 = "L_F_-2_2025_2026_Liga_Regular_B"


@pytest.fixture(scope="module")
def text():
    """The per-possession CSV of two copies of a real game (so the odd and the even half are the same game)."""
    database = new_mock_db("pace-style")
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    database[LF2].insert_many([{**copy.deepcopy(sample), "_id": f"game-{n}"} for n in (1, 2)])
    handler = MagicMock()
    handler.repository.connection.get_collection.side_effect = lambda name: database[name]
    handler.connection.get_collection.side_effect = lambda name: database[name]
    return export_possession_csv(handler, LF2)["csv"]


def raw_rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_every_possession_of_the_csv_is_read_with_its_team_duration_origin_and_points(text):
    possessions = study.read_possessions(text)
    rows = raw_rows(text)
    assert len(possessions) == len(rows) > 100
    first = possessions[0]
    assert (first.game, first.team, first.rival) == (rows[0]["ID_Partido"], rows[0]["Equipo_ID"], rows[0]["Rival_ID"])
    assert (first.duration, first.points, first.origin) == (int(rows[0]["Duracion_posesion"]), int(rows[0]["Puntos_obtenidos"]), rows[0]["Origen_posesion"])
    assert {p.game for p in possessions} == {"game-1", "game-2"}


def test_duration_by_origin_shares_and_points_per_possession_by_hand(text):
    possessions = [p for p in study.read_possessions(text) if not p.controversial]
    table = study.origin_duration(possessions)
    for origin in {p.origin for p in possessions}:
        mine = [p for p in possessions if p.origin == origin]
        cells = [c for c in table if c["origin"] == origin]
        assert sum(c["share"] for c in cells) == pytest.approx(1)
        for c in cells:
            inside = [p for p in mine if study.bucket_of(p.duration) == c["bucket"]]
            assert c["possessions"] == len(inside)
            assert c["ppp"] == pytest.approx(sum(p.points for p in inside) / len(inside))


def test_the_buckets_are_those_of_the_possessions_page():
    assert [study.bucket_of(s) for s in (0, 8, 9, 16, 17, 40)] == ["rápida", "rápida", "media", "media", "lenta", "lenta"]


def test_the_style_of_a_team_is_measured_on_its_odd_and_its_even_games(text):
    halves = study.styles_by_half([p for p in study.read_possessions(text) if not p.controversial])
    assert set(halves) == {p.team for p in study.read_possessions(text)}
    for team, (odd, even) in halves.items():
        assert odd == even                                              # two copies of the same game
        assert set(odd) == set(study.STYLE_METRICS)
        assert 0 <= odd["fast_share"] <= 1 and odd["avg_duration"] > 0


def test_the_correlation_is_pearsons_by_hand():
    assert study.pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1)
    assert study.pearson([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(0.8)
    assert study.pearson([1, 1, 1], [1, 2, 3]) is None
