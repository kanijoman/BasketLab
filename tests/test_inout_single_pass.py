"""The IN/OUT of every player of a competition in ONE pass over its games (found on 23/11/2026 profiling the publication of NCAA).

``export_inout`` asked the repository for each player in turn, and for each player the repository walked ALL the games of the competition, loaded every document, and built a new analyzer for each game of
the player's team: the cost grew with players x games (10 games, 18 s; 30 games, 134 s) and a conference of 370 games took hours. Now a game is read once and its analyzer is shared by all the players
that need it. The result for each player must be EXACTLY what the per-player query gives: its scenarios (a real FBCYL match with every player, two games, a team without players, a phantom, a player without
minutes, the surnames fallback; FEB with every format of minutes, a rival without players, a player that is not found, no games, no connection) are the oracle here.
"""
import copy
import json

import pytest

from tests import inout_repo_corpus as corpus

COLLECTIONS = {"fbcyl": corpus.FBCYL_COLLECTION, "feb": corpus.FEB_COLLECTION}


def repo_for(games, collection, player_doc=None, connected=True):
    return corpus._fake_repo(games, collection, player_doc, connected)


def alone(games, collection, player_id, player_doc=None, connected=True):
    return repo_for(games, collection, player_doc, connected).get_player_in_out_stats(collection, player_id)


def batch(games, collection, player_ids, player_doc=None, connected=True):
    return repo_for(games, collection, player_doc, connected).get_players_in_out_stats(collection, player_ids)


def same(a, b):
    return json.loads(json.dumps(a, default=str, sort_keys=True)) == json.loads(json.dumps(b, default=str, sort_keys=True))


class TestEveryPlayerOfARealMatchOfFbcyl:
    def test_the_result_of_each_player_is_the_one_of_the_query_for_that_player(self):
        game = corpus.fbcyl_game()
        ids = [p["uuid"] for p in corpus.fbcyl_players(game)]
        got = batch([game], corpus.FBCYL_COLLECTION, ids)
        assert set(got) == set(ids) and len(ids) >= 10
        assert all(same(got[i], alone([game], corpus.FBCYL_COLLECTION, i)) for i in ids)

    def test_two_games_of_the_same_team_add_up_as_they_did(self):
        game = corpus.fbcyl_game()
        ids = [p["uuid"] for p in corpus.fbcyl_players(game)]
        got = batch([game, game], corpus.FBCYL_COLLECTION, ids)
        assert all(same(got[i], alone([game, game], corpus.FBCYL_COLLECTION, i)) for i in ids)
        assert got[ids[0]]["games_analyzed"] == 2

    def test_the_odd_cases_of_the_corpus_give_the_same_in_a_batch_as_alone(self):
        real = corpus.fbcyl_game()
        uuid = corpus.fbcyl_players(real)[0]["uuid"]
        no_team = copy.deepcopy(real)
        next(t for t in no_team["stats"]["teams"] if any(p["uuid"] == uuid for p in t["players"]))["players"] = []
        phantom = copy.deepcopy(real)
        for p in corpus.fbcyl_players(phantom):
            if p["uuid"] == uuid:
                p["timePlayed"], p["data"] = 40.0, {}
        no_minutes = copy.deepcopy(real)
        for p in corpus.fbcyl_players(no_minutes):
            if p["uuid"] == uuid:
                p["timePlayed"] = None
        named = corpus.fbcyl_players(real)[0]["name"]
        for games, who in (([no_team], uuid), ([phantom], uuid), ([no_minutes], uuid), ([real], named), ([real], "no-such-player"), ([], uuid)):
            assert same(batch(games, corpus.FBCYL_COLLECTION, [who])[who], alone(games, corpus.FBCYL_COLLECTION, who))


class TestFeb:
    def test_every_player_of_a_game_gives_what_the_query_gives_for_him(self):
        ids = ["P1", "P2", "Q1"]
        got = batch([corpus.feb_game(), corpus.feb_game()], corpus.FEB_COLLECTION, ids, corpus.FEB_PLAYER_DOC)
        assert all(same(got[i], alone([corpus.feb_game(), corpus.feb_game()], corpus.FEB_COLLECTION, i, corpus.FEB_PLAYER_DOC)) for i in ids)
        assert got["P1"]["games_analyzed"] == 2 and got["P1"]["player_team_id"] == "A" and got["Q1"]["player_team_id"] == "B"

    @pytest.mark.parametrize("label,minutes", [("string", {}), ("number", {"P1": 5}), ("zero", {"P1": "0:00"}), ("none", {"P1": None}), ("plain", {"P1": "5"}), ("broken", {"P1": "x:y"}), ("seconds only", {"P1": "5:"}), ("text", {"P1": "abc"})])
    def test_every_format_of_minutes_counts_the_games_of_the_player_the_same(self, label, minutes):
        games = [corpus.feb_game(minutes)]
        assert same(batch(games, corpus.FEB_COLLECTION, ["P1"], corpus.FEB_PLAYER_DOC)["P1"], alone(games, corpus.FEB_COLLECTION, "P1", corpus.FEB_PLAYER_DOC))

    def test_a_player_who_is_not_found_gives_an_empty_result_and_the_others_are_not_affected(self):
        got = batch([corpus.feb_game()], corpus.FEB_COLLECTION, ["P1", "P9"], {"BOXSCORE": {"TEAM": [{"id": "A", "PLAYER": [{"id": "P1"}]}]}})
        assert got["P9"] == {} and same(got["P1"], alone([corpus.feb_game()], corpus.FEB_COLLECTION, "P1", {"BOXSCORE": {"TEAM": [{"id": "A", "PLAYER": [{"id": "P1"}]}]}}))

    def test_the_rival_without_players_and_no_games_are_as_before(self):
        games = [corpus.feb_game(team_b_players=False)]
        assert same(batch(games, corpus.FEB_COLLECTION, ["P1"], corpus.FEB_PLAYER_DOC)["P1"], alone(games, corpus.FEB_COLLECTION, "P1", corpus.FEB_PLAYER_DOC))
        assert same(batch([], corpus.FEB_COLLECTION, ["P1"], corpus.FEB_PLAYER_DOC)["P1"], alone([], corpus.FEB_COLLECTION, "P1", corpus.FEB_PLAYER_DOC))

    def test_without_a_connection_every_player_is_empty(self):
        assert batch([corpus.feb_game()], corpus.FEB_COLLECTION, ["P1", "P2"], corpus.FEB_PLAYER_DOC, connected=False) == {"P1": {}, "P2": {}}


class TestTheWorkIsDoneOnce:
    def test_the_games_are_read_once_however_many_players_ask(self):
        repo = repo_for([corpus.feb_game(), corpus.feb_game()], corpus.FEB_COLLECTION, corpus.FEB_PLAYER_DOC)
        reads = []
        original = repo.get_games_with_playbyplay
        repo.get_games_with_playbyplay = lambda *a, **k: reads.append(1) or original(*a, **k)
        repo.get_players_in_out_stats(corpus.FEB_COLLECTION, ["P1", "P2", "Q1"])
        assert len(reads) == 1

    def test_the_analyzer_of_a_game_is_built_once_and_shared_by_its_players(self, monkeypatch):
        import src.database.playbyplay_analyzer as module

        built = []

        class Counting(module.PlayByPlayAnalyzer):
            def __init__(self, *a, **k):
                built.append(1)
                super().__init__(*a, **k)

        monkeypatch.setattr(module, "PlayByPlayAnalyzer", Counting)
        repo_for([corpus.feb_game(), corpus.feb_game()], corpus.FEB_COLLECTION, corpus.FEB_PLAYER_DOC).get_players_in_out_stats(corpus.FEB_COLLECTION, ["P1", "P2", "Q1"])
        assert len(built) == 2                                                                 # two games, three players: not six
        built.clear()
        game = corpus.fbcyl_game()
        repo_for([game], corpus.FBCYL_COLLECTION).get_players_in_out_stats(corpus.FBCYL_COLLECTION, [p["uuid"] for p in corpus.fbcyl_players(game)])
        assert len(built) == 1

    def test_the_order_of_the_players_and_a_player_listed_twice_change_nothing(self):
        games = [corpus.feb_game()]
        one = batch(games, corpus.FEB_COLLECTION, ["P1", "P2", "Q1"], corpus.FEB_PLAYER_DOC)
        other = batch(games, corpus.FEB_COLLECTION, ["Q1", "P2", "P1", "P1"], corpus.FEB_PLAYER_DOC)
        assert same(one, other) and set(other) == {"P1", "P2", "Q1"}


class TestThePublicationUsesIt:
    def test_the_inout_of_a_competition_is_the_same_as_asking_for_each_player(self):
        """``export_inout`` is the section of ``web-data``: its rows, in the same order, with the same analysis for each player as the per-player service gave."""
        import pathlib
        import sys

        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "local_vectors"))
        import games
        from mongomock_handler import mongomock_handler

        from src.local_data.inout_export import export_inout
        from src.services.inout_service import inout_analysis

        name = "L_F_-2_2025_2026_Liga_Regular_B"
        handler = mongomock_handler()
        handler.connection.client["BASKETBALL"][name].insert_many(games.build_games())
        got = export_inout(handler, name)
        assert len(got["players"]) == 36
        for entry in got["players"]:
            expected = json.loads(json.dumps(inout_analysis(handler, name, entry["player_id"]) or {}, default=str))
            assert entry["analysis"] == expected
