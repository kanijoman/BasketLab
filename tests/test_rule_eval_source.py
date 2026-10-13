"""Where the rule evaluator reads games from (issue #238): in date order, without loading the season in memory."""
import gzip
import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.live_prep.eval_source import (
    game_code, games_from_dir, games_from_mongo, parse_starttime, same_start_groups,
)


def game(code, start, lines=1):
    return {"_id": code, "HEADER": {"starttime": start, "TEAM": []},
            "PLAYBYPLAY": {"LINES": [{"num": "1"}] * lines}}


def test_parse_starttime_reads_the_feb_format():
    assert parse_starttime("10-10-2026 - 17:00") == datetime(2026, 10, 10, 17, 0)
    assert parse_starttime(game("1", "05-10-2025 - 12:30")) == datetime(2025, 10, 5, 12, 30)
    assert parse_starttime("not a date") is None and parse_starttime(None) is None


def test_game_code_is_the_id_or_the_header_code():
    assert game_code(game("2524470", "10-10-2026 - 17:00")) == "2524470"
    assert game_code({"HEADER": {"game_code": 77}}) == "77"
    assert game_code({}) == ""


def test_games_from_a_directory_come_in_date_order_and_skip_games_without_play_by_play(tmp_path):
    (tmp_path / "b.json").write_text(json.dumps(game("B", "11-10-2026 - 12:00")), encoding="utf-8")
    (tmp_path / "a.json").write_text(json.dumps(game("A", "10-10-2026 - 17:00")), encoding="utf-8")
    (tmp_path / "c.json.gz").write_bytes(gzip.compress(json.dumps(game("C", "10-10-2026 - 12:00")).encode()))
    (tmp_path / "empty.json").write_text(json.dumps(game("E", "09-10-2026 - 12:00", lines=0)), encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a game", encoding="utf-8")
    assert [game_code(g) for g in games_from_dir(tmp_path)] == ["C", "A", "B"]


def test_games_without_a_date_go_last_in_code_order(tmp_path):
    for code, start in (("Z", "garbage"), ("A", "garbage"), ("M", "10-10-2026 - 12:00")):
        (tmp_path / f"{code}.json").write_text(json.dumps(game(code, start)), encoding="utf-8")
    assert [game_code(g) for g in games_from_dir(tmp_path)] == ["M", "A", "Z"]


def test_games_that_start_together_are_grouped_so_none_sees_the_other():
    games = [game("1", "10-10-2026 - 12:00"), game("2", "10-10-2026 - 12:00"), game("3", "10-10-2026 - 17:00")]
    assert [[game_code(g) for g in group] for group in same_start_groups(games)] == [["1", "2"], ["3"]]
    assert list(same_start_groups([])) == []


class FakeCollection:
    """The two calls the source makes: an aggregation of (id, start) and a find_one per game."""

    def __init__(self, docs):
        self.docs, self.pipelines, self.finds = {d["_id"]: d for d in docs}, [], []

    def aggregate(self, pipeline, allowDiskUse=False):
        self.pipelines.append((pipeline, allowDiskUse))
        rows = [{"_id": d["_id"], "start": parse_starttime(d)} for d in self.docs.values()]
        return iter(sorted(rows, key=lambda r: (r["start"] is None, r["start"], r["_id"])))

    def find_one(self, query, projection=None):
        self.finds.append((query, projection))
        return self.docs.get(query["_id"])


def handler_for(collection):
    handler = MagicMock()
    handler.repository.connection.get_collection.return_value = collection
    return handler


def test_games_from_mongo_ask_for_ids_first_and_fetch_one_game_at_a_time():
    coll = FakeCollection([game("B", "11-10-2026 - 12:00"), game("A", "10-10-2026 - 17:00")])
    out = list(games_from_mongo(handler_for(coll), "FEB_TEST"))
    assert [game_code(g) for g in out] == ["A", "B"]
    pipeline, disk = coll.pipelines[0]
    assert disk is True
    assert any("$match" in stage for stage in pipeline) and any("$sort" in stage for stage in pipeline)
    # the sort carries only ids and dates; whole games are fetched afterwards with the replay projection
    projection_stage = next(stage["$project"] for stage in pipeline if "$project" in stage)
    assert "PLAYBYPLAY.LINES" not in projection_stage
    assert [q for q, _ in coll.finds] == [{"_id": "A"}, {"_id": "B"}]
    assert all(p and "PLAYBYPLAY.LINES" in p and "SHOTCHART.SHOTS" in p for _, p in coll.finds)


def test_mongo_games_are_generated_lazily():
    coll = FakeCollection([game("A", "10-10-2026 - 17:00"), game("B", "11-10-2026 - 12:00")])
    it = games_from_mongo(handler_for(coll), "FEB_TEST")
    assert coll.finds == []
    next(it)
    assert len(coll.finds) == 1


def test_fbcyl_collections_are_not_supported_yet():
    with pytest.raises(NotImplementedError):
        list(games_from_mongo(handler_for(FakeCollection([])), "FBCYL_TEST"))


# --- recordings as games -----------------------------------------------------------------

class FakeFeed:
    """The two things the source needs from a recording: its match code and the document served at the end."""

    def __init__(self, code, start, lines=3):
        self.match, self._doc = code, {"HEADER": {"starttime": start, "TEAM": []}, "PLAYBYPLAY": {"LINES": [{"num": "1"}] * lines}}
        self.duration = 100.0

    def document_at(self, t, endpoint=None):
        return json.loads(json.dumps(self._doc))


def test_a_recording_that_is_not_in_the_source_takes_its_place_by_date():
    from src.live_prep.eval_source import merge_recordings

    source = [game("A", "10-10-2026 - 12:00"), game("C", "12-10-2026 - 12:00")]
    merged = list(merge_recordings(iter(source), {"B": FakeFeed("B", "11-10-2026 - 12:00")}))
    assert [game_code(g) for g in merged] == ["A", "B", "C"]


def test_a_recording_already_in_the_source_is_not_added_twice():
    from src.live_prep.eval_source import merge_recordings

    source = [game("A", "10-10-2026 - 12:00"), game("B", "11-10-2026 - 12:00")]
    merged = list(merge_recordings(iter(source), {"B": FakeFeed("B", "11-10-2026 - 12:00")}))
    assert [game_code(g) for g in merged] == ["A", "B"]
    assert "SHOTCHART" not in merged[1] and len(merged[1]["PLAYBYPLAY"]["LINES"]) == 1   # the stored game wins


def test_without_recordings_the_source_is_returned_as_it_is():
    from src.live_prep.eval_source import merge_recordings

    source = [game("A", "10-10-2026 - 12:00")]
    assert list(merge_recordings(iter(source), {})) == source
