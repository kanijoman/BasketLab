"""The parity vectors of the local team tables (#327) are kept honest: any change in the season pipelines shows up as a diff of the file.

``python tests/local_vectors/generate.py`` regenerates ``team_stats_feb.json``; the web (``frontend/src/localdata/aggregateTeams.test.ts``) must
reproduce its figures from its rows. Corner cases the filters tell apart are asserted here so that the file cannot go blind.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402


@pytest.fixture(scope="module")
def vectors():
    return generate.build_vectors()


def test_the_stored_vectors_are_the_current_reference(vectors):
    stored = json.loads(generate.OUT.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(vectors, sort_keys=True)) == stored


def test_the_filters_tell_something_apart(vectors):
    by_name = {c["name"]: c for c in vectors["cases"]}
    games = lambda case: sum(t["total_games"] for t in case["team_stats"])  # noqa: E731
    assert games(by_name["all"]) == 24
    assert games(by_name["home"]) == games(by_name["away"]) == 12
    assert games(by_name["won"]) == games(by_name["lost"]) == 12
    assert 0 < games(by_name["date range"]) < 24
    assert games(by_name["empty range"]) == 0
    assert 0 < games(by_name["to date (the games of the last day are in)"]) < games(by_name["all"])


@pytest.fixture(scope="module")
def player_vectors():
    return generate.build_player_vectors()


def test_the_stored_player_vectors_are_the_current_reference(player_vectors):
    stored = json.loads(generate.PLAYERS_OUT.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(player_vectors, sort_keys=True)) == stored


def test_the_player_filters_tell_something_apart(player_vectors):
    by_name = {c["name"]: c["players"] for c in player_vectors["cases"]}
    games = lambda case: sum(p["games_played"] for p in case)  # noqa: E731
    assert games(by_name["home"]) + games(by_name["away"]) == games(by_name["all"]) > 0
    assert games(by_name["won"]) + games(by_name["lost"]) == games(by_name["all"])
    assert {p["team_name"] for p in by_name["one team"]} == {"BRAVO"} and by_name["unknown team"] == []
    assert all("usage_pct" in p and "pie" in p for p in by_name["all"])                  # enriched from the whole season even when filtered
    ids = [(p["team_id"], p["player_id"]) for p in by_name["all"]]
    assert len(ids) == len(set(ids))                                                       # one row per player within his team, whatever name he was written under (#652)


@pytest.fixture(scope="module")
def fbcyl_vectors():
    return generate.build_fbcyl_vectors()


def test_the_stored_fbcyl_vectors_are_the_current_reference(fbcyl_vectors):
    stored = json.loads(generate.FBCYL_OUT.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(fbcyl_vectors, sort_keys=True)) == stored


def test_the_fbcyl_filters_tell_something_apart_and_the_day_bound_is_inclusive(fbcyl_vectors):
    by_name = {c["name"]: c["team_stats"] for c in fbcyl_vectors["cases"]}
    games = lambda case: sum(t["total_games"] for t in case)  # noqa: E731
    assert games(by_name["all"]) == 24 and games(by_name["empty range"]) == 0
    assert games(by_name["won"]) + games(by_name["lost"]) == 22                         # the tied game is in neither
    assert games(by_name["to date (the games of the last day are in)"]) > 0


# FBCYL players (#644): the rows are regenerated everywhere (the exporter runs on mongomock); the API side of the vectors needs the real season
# pipeline, which uses operators mongomock does not have (``$substrCP``, ``$reduce``, ``$getField``), so it is generated on a real mongod, committed,
# and only recomputed here when one is reachable.
import generate_fbcyl_players as fbcyl_players  # noqa: E402


@pytest.fixture(scope="module")
def stored_fbcyl_players():
    return json.loads(fbcyl_players.OUT.read_text(encoding="utf-8"))


def test_the_stored_fbcyl_player_rows_are_the_current_exporter_output(stored_fbcyl_players):
    assert json.loads(json.dumps(fbcyl_players.build_rows(), sort_keys=True, default=str)) == stored_fbcyl_players["rows"]


def test_the_fbcyl_player_filters_tell_something_apart(stored_fbcyl_players):
    by_name = {c["name"]: c["players"] for c in stored_fbcyl_players["cases"]}
    games = lambda case: sum(p["games_played"] for p in case)  # noqa: E731
    assert games(by_name["home"]) + games(by_name["away"]) == games(by_name["all"]) > 0
    assert games(by_name["won"]) + games(by_name["lost"]) < games(by_name["all"])        # the tied game is neither
    assert {p["team_name"] for p in by_name["one team"]} == {"BRAVO"} and by_name["unknown team"] == []
    assert all("usage_pct" in p and "pie" in p and p["player_uuid"] for p in by_name["all"])
    assert any(" " in str(p["player_uuid"]) for c in stored_fbcyl_players["cases"] for p in c["players"])   # the divergence of the date filter is in the file


def _real_mongod():
    try:
        from pymongo import MongoClient

        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=1000)
        client.admin.command("ping")
        return client
    except Exception:  # noqa: BLE001
        return None


def test_the_stored_fbcyl_player_cases_are_what_the_real_pipeline_answers(stored_fbcyl_players):
    client = _real_mongod()
    if client is None:
        pytest.skip("needs a real mongod: FBCYL's player pipeline uses operators mongomock does not implement")
    assert json.loads(json.dumps(fbcyl_players.build_cases(client), sort_keys=True, default=str)) == stored_fbcyl_players["cases"]


# Comparativas (#670): both groups of the season through ``TeamComparisonService``, the reference of ``frontend/src/localdata/comparison.test.ts``.
@pytest.mark.parametrize("builder, path", [("build_comparison_vectors", "COMPARISON_OUT"), ("build_fbcyl_comparison_vectors", "COMPARISON_FBCYL_OUT")])
def test_the_stored_comparison_vectors_are_the_current_reference(builder, path):
    stored = json.loads(getattr(generate, path).read_text(encoding="utf-8"))
    assert json.loads(json.dumps(getattr(generate, builder)(), sort_keys=True)) == stored


@pytest.mark.parametrize("builder", ["build_comparison_vectors", "build_fbcyl_comparison_vectors"])
def test_the_comparisons_tell_something_apart(builder):
    cases = {c["name"]: c["expected"] for c in getattr(generate, builder)()["cases"]}
    games = {row["team_name"]: row["games_a"] + row["games_b"] for row in cases["home vs away"]["team"]}
    assert set(games.values()) == {6}
    for name, comparison in cases.items():
        for row in comparison["team"]:
            both = row["games_a"] + row["games_b"]
            if name == "won vs lost":
                assert both <= games[row["team_name"]], name              # FBCYL: a tied game is neither won nor lost
            else:
                assert both == games[row["team_name"]], name              # every game is in one group or the other (the rest of a stretch is its complement)
    empty = cases["stretch that holds no game"]["team"]
    assert all(row["games_a"] == 0 and row["a"] is None and row["diff"] == {} for row in empty)      # a group with no game has no figures, so no difference
    assert any(0 < row["games_a"] < 6 for row in cases["stretch between two dates"]["team"])


# Multifase (#671): ``MultiPhaseService`` over two phases (the home and the away games of each league) and the sibling collections of a name, the reference of
# ``frontend/src/localdata/multiPhase.test.ts``.
def test_the_stored_multi_phase_vectors_are_the_current_reference():
    stored = json.loads(generate.MULTI_OUT.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(generate.build_multi_vectors(), sort_keys=True)) == stored


@pytest.mark.parametrize("league", ["feb", "fbcyl"])
def test_the_merged_tables_add_the_phases_up(league):
    vectors = json.loads(generate.MULTI_OUT.read_text(encoding="utf-8"))[league]
    phases = vectors["phases"].values()
    games = {t["team_name"]: sum(next(r for r in p["team_stats"] if r["team_name"] == t["team_name"]).get("total_games", next(r for r in p["team_stats"] if r["team_name"] == t["team_name"]).get("games_played")) for p in phases) for t in vectors["team_stats"]}
    assert all(row["games_played"] == games[row["team_name"]] > 0 for row in vectors["team_stats"])        # every team is in both phases: its games are the sum
    assert len(vectors["players"]) > 0


def test_the_siblings_of_a_collection_are_those_of_its_competition_and_season():
    siblings = json.loads(generate.MULTI_OUT.read_text(encoding="utf-8"))["siblings"]["expected"]
    assert siblings["L_F_-2_2025_2026_Liga_Regular_A"] == sorted(siblings["L_F_-2_2025_2026_Liga_Regular_A"]) and len(siblings["L_F_-2_2025_2026_Liga_Regular_A"]) == 4
    assert siblings["L_F_-2_2024_2025_Liga_Regular_A"] == ["L_F_-2_2024_2025_Liga_Regular_A"]              # another season is not a phase
    assert "L_F_-2_2025_2026_Otra_Fase_C" in siblings["L_F_-2_2025_2026_Otra_Fase_C"]                    # a collection that is not in the pool is its own sibling
    assert "PRIMERA_FEB_2025_2026_Liga_Regular_Unico" not in siblings["L_F_-2_2025_2026_Liga_Regular_A"]     # another competition


# Evolución (#672): ``EvolutionService.get_competition_evolution`` over the real per-game pipelines of each league, the reference of ``frontend/src/localdata/evolution.test.ts``.
@pytest.mark.parametrize("builder, path", [("build_evolution_vectors", "EVOLUTION_OUT"), ("build_fbcyl_evolution_vectors", "EVOLUTION_FBCYL_OUT")])
def test_the_stored_evolution_vectors_are_the_current_reference(builder, path):
    stored = json.loads(getattr(generate, path).read_text(encoding="utf-8"))
    assert json.loads(json.dumps(getattr(generate, builder)(), sort_keys=True)) == stored


@pytest.mark.parametrize("path", ["EVOLUTION_OUT", "EVOLUTION_FBCYL_OUT"])
def test_the_evolution_vectors_cover_every_stat_and_tell_something(path):
    from src.services.evolution_service import EVOLUTION_STAT_KEYS

    cases = json.loads(getattr(generate, path).read_text(encoding="utf-8"))["cases"]
    assert {c["stat"] for c in cases} == set(EVOLUTION_STAT_KEYS)
    points = next(c for c in cases if c["stat"] == "points" and c["window"] == 3)["points"]
    assert [p["game_number"] for p in points] == list(range(1, len(points) + 1)) and len(points) > 3
    assert any(p["competition_rolling"] != p["competition_cumulative"] for p in points)          # the window matters once a team has played more games than it


# Análisis PBP (#676): the five pbp tables as the real services answer them over the ``DERIVED`` of the fixture games, the reference of ``frontend/src/localdata/pbp.test.ts``.
@pytest.mark.parametrize("builder, path", [("build_pbp_vectors", "PBP_OUT"), ("build_fbcyl_pbp_vectors", "PBP_FBCYL_OUT")])
def test_the_stored_pbp_vectors_are_the_current_reference(builder, path):
    stored = json.loads(getattr(generate, path).read_text(encoding="utf-8"))
    assert json.loads(json.dumps(getattr(generate, builder)(), sort_keys=True)) == stored


@pytest.mark.parametrize("path", ["PBP_OUT", "PBP_FBCYL_OUT"])
def test_the_pbp_vectors_cover_the_branches_of_the_tables(path):
    vectors = json.loads(getattr(generate, path).read_text(encoding="utf-8"))
    origin = vectors["expected"]["origin"]
    assert any(r["games"] == 0 and r["games_unreliable"] > 0 for r in origin)               # a team whose only game is not reliable
    assert any(r["games"] > 0 and r["games_paint"] < r["games"] for r in origin)             # a game without SHOTCHART: no paint points
    assert {g["v"] for g in vectors["derived"]["rows"]} == {5, 6}                              # v5 is left out of the origin tables (they need v6) but not of the periods
    assert any("OT" in t["periods"] for t in vectors["expected"]["periods"])                  # an overtime bucket
    assert vectors["expected"]["coverage"]["pending"] == vectors["derived"]["total"] - 2 and vectors["derived"]["without_derived"]   # the v5 game is pending too
    assert any(t["own"]["n"] == 0 for t in vectors["expected"]["timeouts"])                    # a team with no timeouts to analyse
