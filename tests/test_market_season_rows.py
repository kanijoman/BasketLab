"""The Talent row (B2, #878): the games of a player summed per competition, season AND team. A transfer inside a competition is two rows (the team is part of the statistics: the context
changes), the phases and groups of one competition are one row, and the minutes are seconds for FEB and FBCYL alike (FBCYL's ``timePlayed`` is whole minutes: measured on the archive,
a team adds up to 200 there and to 12,000 in FEB for 5 x 40 minutes)."""
import random
import sys
from collections import defaultdict
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent))

from local_vectors import fbcyl_games  # noqa: E402
from local_vectors.games import build_games  # noqa: E402
from src.local_data.export import export_collection  # noqa: E402
from src.market.season_rows import season_player_rows  # noqa: E402

COUNTS = ("pts", "p1m", "p1a", "p2m", "p2a", "p3m", "p3a", "assist", "ro", "rd", "rt", "st", "to", "bs", "pf", "rf", "val", "pllss")


def _payload(name, games):
    collection = new_mock_db(name)[name]
    collection.insert_many(games)
    return export_collection(collection, name)


@pytest.fixture(scope="module")
def feb():
    return _payload("LEAGUE", build_games())


@pytest.fixture(scope="module")
def fbcyl():
    return _payload("FBCYL_X_2026_", fbcyl_games.build_games())


def test_one_row_per_player_and_team_with_the_games_summed(feb):
    rows = season_player_rows([("Liga Regular", feb)])
    expected = defaultdict(lambda: defaultdict(int))
    for r in feb["player_rows"]:
        e = expected[(f"feb:{r['player_id']}", str(r["team_id"]))]
        e["games"] += 1
        for field in ("minutes", *COUNTS):
            e[field] += r[field]
    assert {(r["person_id"], r["team_id"]) for r in rows} == set(expected)
    for r in rows:
        want = expected[(r["person_id"], r["team_id"])]
        assert r["games"] == want["games"] and r["minutes"] == want["minutes"]          # FEB minutes are seconds already
        assert all(r[f] == want[f] for f in COUNTS)


def test_fbcyl_minutes_become_seconds_and_the_person_is_the_uuid(fbcyl):
    rows = season_player_rows([("1ª FASE-GRUPO A-1", fbcyl)])
    raw = defaultdict(int)
    for r in fbcyl["player_rows"]:
        raw[(f"fbcyl:{r['player_uuid']}", str(r["team_id"]))] += r["minutes"]
    assert {(r["person_id"], r["team_id"]): r["minutes"] for r in rows} == {k: v * 60 for k, v in raw.items()}
    assert all(r["league"] == "fbcyl" and isinstance(r["team_id"], str) for r in rows)


@pytest.mark.parametrize("payload_name", ["feb", "fbcyl"])
def test_a_team_plays_about_five_times_forty_minutes_a_game_in_both_formats(payload_name, request):
    """The unit check of the measured archive: a team is on court 5 x 2400 s = 12,000 s a game. The fixtures vary (players without minutes, overtime), so the band is wide, but a
    unit that was wrong would be 60 times off in either direction (200 s or 720,000 s)."""
    payload = request.getfixturevalue(payload_name)
    by_team, games = defaultdict(int), defaultdict(set)
    for row in season_player_rows([("g", payload)]):
        by_team[row["team_id"]] += row["minutes"]
    for pr in payload["player_rows"]:
        games[str(pr["team_id"])].add(pr["match_id"])
    assert by_team and all(8000 <= total / len(games[team]) <= 14000 for team, total in by_team.items())


def test_a_player_in_two_groups_of_the_competition_is_one_row_with_both_groups(feb):
    half = len(feb["player_rows"]) // 2
    first = {**feb, "player_rows": feb["player_rows"][:half]}
    second = {**feb, "player_rows": feb["player_rows"][half:]}
    together = season_player_rows([("Liga Regular · A", first), ("Play-offs", second)])
    whole = season_player_rows([("Liga Regular", feb)])
    assert [(r["person_id"], r["team_id"], r["games"], r["minutes"], r["pts"]) for r in together] == [(r["person_id"], r["team_id"], r["games"], r["minutes"], r["pts"]) for r in whole]
    assert any(r["groups"] == ["Liga Regular · A", "Play-offs"] for r in together) or any(len(r["groups"]) == 2 for r in together)
    assert all(set(r["groups"]) <= {"Liga Regular · A", "Play-offs"} for r in together)


def test_a_transfer_inside_a_competition_is_two_rows():
    row = {"is_local": True, "won": True, "player_name": "J. MOVER", "minutes": 1200, "pts": 10, "match_id": 1, "starttime": "03-10-2025 - 12:30",
           **{f: 0 for f in COUNTS if f != "pts"}}
    payload = {"league": "feb", "collection": "X", "player_rows": [
        {**row, "player_id": "77", "team_id": "101", "team_name": "ALPHA"},
        {**row, "player_id": "77", "team_id": "102", "team_name": "BRAVO", "match_id": 2},
        {**row, "player_id": "77", "team_id": "102", "team_name": "BRAVO", "match_id": 3}], "team_rows": []}
    rows = season_player_rows([("g", payload)])
    assert [(r["person_id"], r["team_id"], r["team_name"], r["games"], r["pts"]) for r in rows] == [("feb:77", "101", "ALPHA", 1, 10), ("feb:77", "102", "BRAVO", 2, 20)]


def test_missing_values_count_as_zero_and_a_row_without_minutes_is_not_a_game():
    base = {"player_id": "5", "team_id": "9", "team_name": "T", "player_name": "A. B C", "match_id": 1, "is_local": True, "won": False, "starttime": "x"}
    payload = {"league": "feb", "collection": "X", "team_rows": [], "player_rows": [
        {**base, "minutes": 600, "pts": None, "p3m": 2, "p3a": None},
        {**base, "match_id": 2, "minutes": 0, "pts": 99}]}
    (row,) = season_player_rows([("g", payload)])
    assert (row["games"], row["minutes"], row["pts"], row["p3m"], row["p3a"], row["assist"]) == (1, 600, 0, 2, 0, 0)


def test_the_name_is_the_most_used_one_and_the_order_of_the_rows_does_not_matter(feb):
    renamed = [dict(r) for r in feb["player_rows"]]
    target = next(r for r in renamed)
    for r in renamed:
        if (r["player_id"], r["team_id"]) == (target["player_id"], target["team_id"]):
            r["player_name"] = "Z. LATE SPELLING"
    first = season_player_rows([("g", {**feb, "player_rows": renamed})])
    shuffled = renamed[:]
    random.Random(3).shuffle(shuffled)
    second = season_player_rows([("g", {**feb, "player_rows": shuffled})])
    assert first == second == sorted(first, key=lambda r: (r["person_id"], r["team_id"]))
    assert next(r for r in first if r["person_id"] == f"feb:{target['player_id']}" and r["team_id"] == target["team_id"])["name"] == "Z. LATE SPELLING"


def test_no_payloads_no_rows_and_the_same_run_twice_is_identical(feb):
    assert season_player_rows([]) == [] and season_player_rows([("g", {"league": "feb", "collection": "X", "player_rows": [], "team_rows": []})]) == []
    assert season_player_rows([("g", feb)]) == season_player_rows([("g", feb)])
