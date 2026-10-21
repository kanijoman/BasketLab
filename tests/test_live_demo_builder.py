"""Demo matches made from finished games (issue #441): a recording the app can replay + the package its team would have had.

``recording_pack`` only packs what the CI recorder saved from a LIVE match, so a team that has not played live yet had no demo. The builder
turns a finished game stored in MongoDB into the same pack (``RecordedFeed`` format: what the app replays as if it were live, with FEB's latency)
and builds the package from ONLY the games played before it, which is what the staff would have had.
"""
import copy
import gzip
import json

import pytest

from src.live_core.engine import LiveEngine
from src.live_core.package import PreparationPackage
from src.live_core.recorded_feed import RecordedFeed
from src.live_prep import demo_builder
from src.live_prep.demo_builder import best_match, build_demo_package, build_recording, write_demo

OWN, RIVAL = "982047", "981204"


@pytest.fixture
def game(feb_game_doc):
    return copy.deepcopy(feb_game_doc)


class TestRecording:
    def test_it_is_a_pack_the_feed_player_reads(self, game):
        pack = build_recording(game)
        feed = RecordedFeed(pack)
        assert pack["v"] == 1 and pack["match"] == str(game["HEADER"].get("game_code") or game.get("_id"))
        assert feed.duration > 0 and pack["frames"]

    def test_the_times_start_at_zero_and_never_go_back(self, game):
        times = [f["t"] for f in build_recording(game)["frames"]]
        assert times[0] == 0 and times == sorted(times)

    def test_the_first_frame_is_a_match_in_progress_and_the_last_one_is_the_finished_game(self, game):
        feed = RecordedFeed(build_recording(game))
        first, last = feed.document_at(0), feed.document_at(feed.duration)
        assert str(first["HEADER"]["status"]) != "3"
        assert str(last["HEADER"]["status"]) == "3"
        assert [int(t["pts"]) for t in last["HEADER"]["TEAM"]] == [int(t["pts"]) for t in game["HEADER"]["TEAM"]]

    def test_the_last_document_has_every_line_of_the_game(self, game):
        feed = RecordedFeed(build_recording(game))
        assert len(feed.document_at(feed.duration)["PLAYBYPLAY"]["LINES"]) == len(game["PLAYBYPLAY"]["LINES"])

    def test_the_engine_digests_the_replay_up_to_the_final_score(self, game):
        feed = RecordedFeed(build_recording(game))
        engine, snap = LiveEngine(), None
        for t in range(0, int(feed.duration) + 1, 10):
            doc = feed.document_at(t)
            if doc is not None:
                snap = engine.update(doc)
        assert snap["score"] == {str(t["id"]): int(t["pts"]) for t in game["HEADER"]["TEAM"]}

    def test_the_lines_appear_over_time_not_all_at_once(self, game):
        feed = RecordedFeed(build_recording(game))
        counts = [len(feed.document_at(t)["PLAYBYPLAY"]["LINES"]) for t in (feed.duration / 4, feed.duration / 2, feed.duration - 1)]
        assert 0 < counts[0] < counts[1] < counts[2]

    def test_a_game_without_log_times_is_replayed_with_its_game_clock(self, game):
        for line in game["PLAYBYPLAY"]["LINES"]:
            line.pop("LogTimeUtc", None)
        pack = build_recording(game)
        assert RecordedFeed(pack).duration > 0

    def test_a_game_without_play_by_play_cannot_be_a_demo(self, game):
        game["PLAYBYPLAY"]["LINES"] = []
        with pytest.raises(ValueError, match="play-by-play"):
            build_recording(game)

    def test_the_pack_is_small_enough_to_ship_in_the_app(self, game):
        assert len(gzip.compress(json.dumps(build_recording(game), separators=(",", ":")).encode())) < 120_000


class TestPackage:
    def test_it_uses_only_the_games_before_the_match(self, feb_game_doc):
        earlier = [copy.deepcopy(feb_game_doc) for _ in range(2)]
        for n, g in enumerate(earlier):
            g["_id"] = 1000 + n
            g["HEADER"]["starttime"] = f"0{n + 1}-10-2026 - 18:00"
        match = copy.deepcopy(feb_game_doc)
        match["_id"] = 2000
        match["HEADER"]["starttime"] = "10-10-2026 - 18:00"
        later = copy.deepcopy(feb_game_doc)
        later["_id"] = 3000
        later["HEADER"]["starttime"] = "20-10-2026 - 18:00"
        package = build_demo_package([*earlier, match, later], match, "COL", "2026/2027", OWN, RIVAL, roster=None)
        assert package.baselines["sample_games"]["league"] == 2 and package.baselines["sample_games"]["own"] == 2

    def test_it_carries_the_match_in_the_competition_meta(self, feb_game_doc):
        match = copy.deepcopy(feb_game_doc)
        match["_id"] = 2000
        package = build_demo_package([match], match, "COL", "2026/2027", OWN, RIVAL, roster=None)
        meta = package.competition_meta["match"]
        assert meta["code"] == "2000" and meta["home"]["id"] and meta["away"]["id"] and meta["start"]
        assert PreparationPackage.loads(package.dumps()) == package

    def test_a_package_of_the_first_game_of_the_season_is_valid_with_no_history(self, feb_game_doc):
        match = copy.deepcopy(feb_game_doc)
        match["_id"] = 2000
        package = build_demo_package([match], match, "COL", "2026/2027", OWN, RIVAL, roster=None)
        assert package.baselines["sample_games"]["own"] == 0

    def test_the_rule_config_of_the_competition_goes_in(self, feb_game_doc):
        match = copy.deepcopy(feb_game_doc)
        match["_id"] = 2000
        package = build_demo_package([match], match, "COL", "2026/2027", OWN, RIVAL, roster=None, rule_config={"rules_off": ["formation_lineup"]})
        assert package.rule_config == {"rules_off": ["formation_lineup"]}


class TestBestMatch:
    def test_the_match_with_the_most_kinds_of_alerts_after_enough_history_wins(self, monkeypatch):
        evaluation = type("E", (), {})()
        evaluation.team_games = [{"game": str(c), "team": OWN, "prior": p} for c, p in ((1, 1), (2, 5), (3, 6), (4, 7))]
        rows = [{"game": g, "team": OWN, "id": i, "severity": s} for g, i, s in
                [("1", "a", "warning"), ("1", "b", "warning"), ("1", "c", "warning"), ("2", "a", "warning"), ("3", "a", "warning"),
                 ("3", "b", "critical"), ("3", "c", "warning"), ("4", "a", "info"), ("4", "b", "info")]]
        evaluation.rows = rows
        assert best_match(evaluation, OWN, min_prior=3) == "3"    # game 1 has no history; 4 only information

    def test_without_enough_history_it_takes_the_best_of_what_there_is(self):
        evaluation = type("E", (), {})()
        evaluation.team_games = [{"game": "1", "team": OWN, "prior": 0}, {"game": "2", "team": OWN, "prior": 1}]
        evaluation.rows = [{"game": "2", "team": OWN, "id": "a", "severity": "warning"}]
        assert best_match(evaluation, OWN, min_prior=3) == "2"

    def test_a_team_with_little_history_gets_the_game_with_the_most_of_it_not_the_first_one_regression(self):
        """Llíria on 21/10/2026 had played 3 games: the pick was its first one (no history: an empty package)."""
        evaluation = type("E", (), {})()
        evaluation.team_games = [{"game": str(c), "team": OWN, "prior": c - 1} for c in (1, 2, 3)]
        evaluation.rows = [{"game": g, "team": OWN, "id": "a", "severity": "warning"} for g in ("1", "2", "3")]
        assert best_match(evaluation, OWN, min_prior=5) == "3"

    def test_no_games_of_the_team_is_an_error(self):
        evaluation = type("E", (), {})()
        evaluation.team_games, evaluation.rows = [], []
        with pytest.raises(ValueError, match="team"):
            best_match(evaluation, OWN)


class TestWrite:
    def test_it_writes_the_two_files_the_app_bundles(self, tmp_path, feb_game_doc):
        game = copy.deepcopy(feb_game_doc)
        game["_id"] = 2000
        package = build_demo_package([game], game, "COL", "2026/2027", OWN, RIVAL, roster=None)
        write_demo(tmp_path, "2000", build_recording(game), package)
        assert RecordedFeed.load(tmp_path / "2000.rec.json.gz").duration > 0
        assert PreparationPackage.loads((tmp_path / "2000.package.json").read_text(encoding="utf-8")) == package

    def test_the_module_has_a_command_line(self):
        assert callable(demo_builder.main)
