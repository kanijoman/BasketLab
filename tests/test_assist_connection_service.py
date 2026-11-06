"""Assist connections of a team (issue #773): who passes, who receives and from which zones the receiver scores, assisted against not assisted."""
import pytest

from src.services.assist_connection_service import AssistConnectionService, aggregate
from src.services.assist_links import GameLinks
from tests.db_helpers import new_mock_db
from tests.test_assist_links import _line, fb_doc, feb_doc, mv, shot


def basket(scorer, passer=None, zone="paint", team="10", points=2):
    return {"team_id": team, "scorer": scorer, "passer": passer, "zone": zone, "points": points}


def game(*baskets, unlinked=(), names=None):
    return GameLinks(baskets=list(baskets), unlinked_team_ids=list(unlinked), names=names or {"a": "ANA", "b": "BEA", "c": "CLARA", "z": "ZOE"})


def receivers(result):
    return {r["player_id"]: r for r in result["receivers"]}


def test_the_ranking_orders_receivers_by_their_share_of_the_assisted_baskets_of_the_team():
    result = aggregate([game(basket("a", "b"), basket("a", "c"), basket("a", "b"), basket("c", "a"))], "10")
    assert [(r["player_id"], r["received"], r["share_pct"]) for r in result["receivers"]] == [("a", 3, 75.0), ("c", 1, 25.0)]
    assert result["assisted_baskets"] == 4


def test_the_volume_of_scoring_that_comes_from_assists_is_measured_in_points_of_field_goals():
    row = receivers(aggregate([game(basket("a", "b", points=3), basket("a", None, points=2), basket("a", None, points=3), basket("a", "c", points=2))], "10"))["a"]
    assert (row["points"], row["assisted_points"], row["assisted_points_pct"]) == (10, 5, 50.0)


def test_a_player_with_no_assisted_points_has_zero_percent_not_none():
    row = receivers(aggregate([game(basket("a", None, points=3))], "10"))["a"]
    assert (row["points"], row["assisted_points"], row["assisted_points_pct"]) == (3, 0, 0.0)


def test_a_receiver_without_a_threshold_appears_even_with_one_assisted_basket():
    result = aggregate([game(basket("a", "b"))], "10")
    assert [r["player_id"] for r in result["receivers"]] == ["a"]


def test_a_player_who_only_scores_unassisted_is_listed_with_zero_received_so_the_user_can_sort_by_it():
    result = aggregate([game(basket("a", "b"), basket("c"))], "10")
    row = receivers(result)["c"]
    assert (row["received"], row["unassisted"], row["fgm"], row["assisted_pct"], row["share_pct"]) == (0, 1, 1, 0.0, 0.0)


def test_assisted_pct_is_the_share_of_the_players_own_baskets_that_were_assisted():
    row = receivers(aggregate([game(basket("a", "b"), basket("a"), basket("a"), basket("a"))], "10"))["a"]
    assert (row["received"], row["unassisted"], row["fgm"], row["assisted_pct"]) == (1, 3, 4, 25.0)


def test_the_zones_of_a_receiver_carry_assisted_and_unassisted_counts_side_by_side():
    result = aggregate([game(basket("a", "b", "paint"), basket("a", None, "paint"), basket("a", None, "paint"), basket("a", "c", "top_three"))], "10")
    zones = {z["zone"]: z for z in receivers(result)["a"]["zones"]}
    assert (zones["paint"]["assisted"], zones["paint"]["unassisted"], zones["paint"]["assisted_pct"]) == (1, 2, pytest.approx(33.3, abs=0.1))
    assert (zones["top_three"]["assisted"], zones["top_three"]["unassisted"], zones["top_three"]["assisted_pct"]) == (1, 0, 100.0)
    assert receivers(result)["a"]["without_zone"] == 0


def test_baskets_without_a_known_zone_are_counted_apart_not_dropped_nor_invented():
    row = receivers(aggregate([game(basket("a", "b", None), basket("a", None, None))], "10"))["a"]
    assert row["zones"] == [] and row["without_zone"] == 2 and row["fgm"] == 2


def test_who_passes_to_each_receiver_and_who_each_passer_finds():
    result = aggregate([game(basket("a", "b"), basket("a", "b"), basket("a", "c"), basket("c", "b"))], "10")
    assert receivers(result)["a"]["from"] == [{"player_id": "b", "name": "BEA", "count": 2}, {"player_id": "c", "name": "CLARA", "count": 1}]
    passers = {p["player_id"]: p for p in result["passers"]}
    assert passers["b"]["assists"] == 3 and passers["b"]["to"][0] == {"player_id": "a", "name": "ANA", "count": 2}
    assert [p["player_id"] for p in result["passers"]] == ["b", "c"]               # most assists first


def test_only_the_baskets_of_the_team_count():
    result = aggregate([game(basket("a", "b"), basket("z", "z2", team="20"))], "10")
    assert [r["player_id"] for r in result["receivers"]] == ["a"] and result["assisted_baskets"] == 1


def test_coverage_says_how_many_assists_were_tied_to_a_basket():
    result = aggregate([game(basket("a", "b"), basket("a", "b"), basket("a", "b"), unlinked=["10", "20"])], "10")
    assert (result["assists_total"], result["assists_linked"], result["linked_pct"]) == (4, 3, 75.0)


def test_a_team_without_assists_gives_empty_lists_and_no_division_by_zero():
    result = aggregate([game(basket("a"))], "10")
    assert result["assisted_baskets"] == 0 and result["linked_pct"] is None and result["passers"] == []
    assert receivers(result)["a"]["share_pct"] == 0.0


def test_games_counts_only_the_games_the_team_played_not_every_game_read_from_the_competition_regression():
    """Found on real data: a whole competition is read once for every team, so ``games`` was the size of the competition (39) instead of the team's (about 5)."""
    ours = game(basket("a", "b"))
    others = game(basket("z", "z2", team="20"))
    assert aggregate([ours, others, others, ours], "10")["games"] == 2
    assert aggregate([others], "10")["games"] == 0


def test_no_games_gives_an_empty_answer():
    result = aggregate([], "10")
    assert result["receivers"] == [] and result["passers"] == [] and result["games"] == 0


def test_the_order_of_the_games_does_not_change_the_result():
    a = game(basket("a", "b"), basket("c", "a"))
    b = game(basket("a", "c", "top_three"), basket("b"))
    assert aggregate([a, b], "10") == aggregate([b, a], "10")


def test_the_player_filter_returns_the_detail_of_that_player_as_receiver_and_as_passer():
    result = aggregate([game(basket("a", "b"), basket("b", "a"), basket("b", "a"))], "10", player_id="a")
    assert result["focus"]["as_receiver"]["player_id"] == "a" and result["focus"]["as_passer"]["assists"] == 2
    assert aggregate([game(basket("a", "b"))], "10", player_id="nope")["focus"] == {"as_receiver": None, "as_passer": None}
    assert "focus" not in aggregate([game(basket("a", "b"))], "10")


# ------------------------------------------------------------------------------------------------ over stored games
class Handler:
    """The two calls of the real handler the service makes, over an in-memory database."""
    def __init__(self, db, teams=()):
        self.db, self.teams = db, list(teams)
        self.connection = self                      # the real handler reaches its collections through ``handler.connection.get_collection``

    def get_collection(self, name):
        return self.db[name]

    def get_teams_with_ids(self, name):
        return self.teams


FEB = "LF_CHALLENGE_2026_2027_Liga_Regular_Único"
FBCYL = "FBCYL_PRIMERA_2026_A-1_2026_"


def feb_game():
    doc = feb_doc([_line(1, "shoot", "1", "p2"), _line(2, "assist", "1", "p1"), _line(3, "shoot", "1", "p1", time="05:00")],
                  [shot(5, 4, 50), shot(4, 40, 5, time="05:00")])
    doc["_id"] = "g1"
    return doc


def test_the_service_reads_a_feb_collection_for_the_team_of_the_filter():
    db = new_mock_db()
    db[FEB].insert_one(feb_game())
    result = AssistConnectionService(Handler(db)).get_connections(FEB, "10")
    assert result["format"] == "feb" and result["games"] == 1
    assert receivers(result)["p2"]["from"] == [{"player_id": "p1", "name": "ANA", "count": 1}]
    assert receivers(result)["p1"]["unassisted"] == 1
    assert AssistConnectionService(Handler(db)).get_connections(FEB, "99")["receivers"] == []


def test_the_service_reads_an_fbcyl_collection_with_its_own_ids():
    db = new_mock_db()
    doc = fb_doc([mv("Canasta de 2", 1, 12, "e1"), mv("Asistencia", 1, 11, "e2")], [(12, "e1")])
    doc["uuid"] = "m1"
    db[FBCYL].insert_one(doc)
    result = AssistConnectionService(Handler(db)).get_connections(FBCYL, "100")
    assert result["format"] == "fbcyl"
    assert receivers(result)["u2"]["from"] == [{"player_id": "u1", "name": "ANA", "count": 1}]
    assert receivers(result)["u2"]["zones"][0]["assisted"] == 1


def test_the_service_never_loads_the_whole_collection_into_a_list(monkeypatch):
    """Memory (512 MB server): games are read one by one from the cursor."""
    db = new_mock_db()
    db[FEB].insert_one(feb_game())
    seen = []
    original = type(db[FEB]).find

    def spy(self, *a, **k):
        cursor = original(self, *a, **k)
        seen.append(k.get("projection") or (a[1] if len(a) > 1 else None))
        return cursor

    monkeypatch.setattr(type(db[FEB]), "find", spy)
    AssistConnectionService(Handler(db)).get_connections(FEB, "10")
    assert seen and seen[0] is not None, "a projection is always used on the games collection"


def test_every_team_of_a_competition_comes_from_one_pass_over_the_games():
    db = new_mock_db()
    doc = feb_game()
    db[FEB].insert_one(doc)
    handler = Handler(db, [{"id": "10", "name": "ALFA"}, {"id": "20", "name": "BETA"}])
    calls = []
    original = type(db[FEB]).find
    type(db[FEB]).find = lambda self, *a, **k: (calls.append(1), original(self, *a, **k))[1]
    try:
        rows = AssistConnectionService(handler).get_all_teams(FEB)
    finally:
        type(db[FEB]).find = original
    assert len(calls) == 1, "the competition is read once, not once per team"
    assert [r["team_id"] for r in rows] == ["10"], "a team with no baskets in the games is not listed"
    assert rows[0]["team_name"] == "ALFA" and rows[0]["analysis"]["assisted_baskets"] == 1
