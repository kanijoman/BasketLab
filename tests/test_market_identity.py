"""Person registry of the Mercado module (#873): one ``person_id`` per FEB ``idPlayer``.

The fixture is real: every game of six players of the archive seed (name spelling variants, players who move between
competitions and seasons, a player with two different surnames over time), reduced to ids, names and teams.
"""
import gzip
import json
from pathlib import Path

import pytest

from src.market.identity import build_registry, name_key, name_conflicts

FIXTURE = Path(__file__).parent / "fixtures" / "market_person_games.json.gz"


@pytest.fixture(scope="module")
def games():
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("name,key", [
    ("R. LLAMAS MARTINEZ", "LLAMAS MARTINEZ"),          # FEB: initial + surnames
    ("A. COSTA I VAZQUEZ", "COSTA I VAZQUEZ"),
    ("N. TREVIÑO QUINTILLA", "TREVINO QUINTILLA"),       # accents out
    ("J. SAENZ - DIAZ MURO", "SAENZ - DIAZ MURO"),
    ("", ""),
])
def test_name_key_drops_the_initial_and_the_accents(name, key):
    assert name_key(name) == key


def test_the_same_id_in_several_competitions_and_seasons_is_one_person(games):
    registry = build_registry(games)
    person = registry["feb:2017688"]
    assert person.feb_id == "2017688"
    assert len(person.collections) > 1
    assert sum(person.games_by_collection.values()) == len(person.games)


def test_the_registry_has_one_person_per_id_and_never_merges_by_name(games):
    registry = build_registry(games)
    assert set(registry) == {f"feb:{i}" for i in ("216888", "2017688", "2340025", "2736231", "2186563", "2230288")}


def test_name_spelling_variants_stay_one_person_and_are_not_a_conflict(games):
    registry = build_registry(games)
    assert len(registry["feb:216888"].names) > 1               # COSTA VAZQUEZ / COSTA I VAZQUEZ
    assert "feb:216888" not in name_conflicts(registry)


def test_a_player_whose_surnames_changed_is_listed_for_review(games):
    assert "feb:2736231" in name_conflicts(build_registry(games))   # JEAN-BAPTISTE / DJERY


def test_the_display_name_is_the_most_used_one_and_the_order_of_the_games_does_not_matter(games):
    forward = build_registry(games)
    backward = build_registry(list(reversed(games)))
    assert {k: v.display_name for k, v in forward.items()} == {k: v.display_name for k, v in backward.items()}
    assert forward["feb:216888"].display_name == "S. COSTA VAZQUEZ"        # 33 games against 8


def test_a_player_who_changes_team_keeps_every_team_of_his_career(games):
    person = build_registry(games)["feb:2017688"]
    assert len(person.teams) == 3
    assert all(isinstance(t, str) for t in person.teams)


def test_games_without_box_score_or_player_id_are_skipped():
    registry = build_registry([{"_id": "1"}, {"_id": "2", "BOXSCORE": {"TEAM": [{"id": "9", "PLAYER": [{"name": "X. Y"}]}]}}])
    assert registry == {}


def test_registry_is_idempotent(games):
    first = build_registry(games)
    second = build_registry(games)
    assert {k: (v.names, v.teams, v.collections) for k, v in first.items()} == {k: (v.names, v.teams, v.collections) for k, v in second.items()}
